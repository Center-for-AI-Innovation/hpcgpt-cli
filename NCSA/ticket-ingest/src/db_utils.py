"""
The "database" here is the JSON file ticket_server.src.store.TicketStore loads
at startup and indexes into an in-memory SQLite FTS5 table. There is no on-disk
.db file: updating the knowledge base means writing a new version of this JSON.
"""

import os
import json
import logging
from typing import Any, Dict, List, Tuple

from src.stages import _load_llmflux_output


def load_database(path: str) -> List[Dict[str, Any]]:
    """Load a knowledge-base JSON file as a flat list of entries.
    Mirrors TicketStore._load's flexible parsing so this stays in sync with
    whatever shape ticket_server actually accepts.
    """
    with open(path) as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    entries: List[Dict[str, Any]] = []
    clusters = data.get("clusters", data) if isinstance(data, dict) else []
    if isinstance(clusters, list):
        for c in clusters:
            if isinstance(c, dict) and "items" in c:
                label = c.get("label") or c.get("name") or "unclustered"
                for item in c["items"]:
                    item.setdefault("cluster", label)
                    entries.append(item)
            else:
                entries.append(c)
    elif isinstance(clusters, dict):
        for name, items in clusters.items():
            for item in items:
                item.setdefault("cluster", name)
                entries.append(item)
    return entries


def filter_pii_failures(sum_results_path: str, label: str, output_path: str) -> int:
    """Drop tickets that failed the PII judge before they reach dedup/merge.

    evaluate_summarization() -> stages.summarize_results() already writes
    logs/<label>_evaluation_failures.json when there are failures. This reads that file back rather than
    re-parsing judge output so PII-verdict parsing lives in exactly one place.

    Returns the number of tickets dropped.
    """
    failures_path = f"logs/{label}_evaluation_failures.json"
    failed_ids = set()
    if os.path.exists(failures_path):
        with open(failures_path) as f:
            failed_ids = {entry["id"] for entry in json.load(f)}

    sum_data = _load_llmflux_output(sum_results_path)
    clean = [item for item in sum_data if item["input"]["custom_id"] not in failed_ids]

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(clean, f, indent=2)

    dropped = len(sum_data) - len(clean)
    if dropped:
        logging.warning(f"Dropped {dropped} ticket(s) that failed the PII judge: {sorted(failed_ids)}")
    return dropped


def merge_into_database(
    existing: List[Dict[str, Any]],
    new_items: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int, int]:
    """Append deduplicated new Q/A pairs ({custom_id, content} from
    remove_duplicates' output) into an existing knowledge-base list.
    Tickets whose custom_id is already present are skipped instead of being
    overwritten, making re-running the same CSV twice a no-op instead of a
    duplicate entry. New entries are tagged cluster="unclustered" (matching
    TicketStore's default) since clustering is not run incrementally here.

    Returns (merged_list, num_added, num_skipped).
    """
    existing_ids = {e.get("custom_id") or e.get("id") for e in existing}
    merged = list(existing)
    added = 0
    skipped = 0

    for item in new_items:
        cid = item.get("custom_id")
        if cid in existing_ids:
            logging.warning(f"Skipping \"{cid}\": already present in the database")
            skipped += 1
            continue
        merged.append({
            "custom_id": cid,
            "content": item.get("content", ""),
            "cluster": item.get("cluster", "unclustered"),
        })
        existing_ids.add(cid)
        added += 1

    return merged, added, skipped