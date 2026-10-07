#!/usr/bin/env python3
"""
Ticket knowledge-base store.

Loads the deduplicated/clustered ticket Q&A pairs and indexes them in an
in-memory SQLite FTS5 table for bm25-ranked search.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_QA_RE = re.compile(r"Q:\s*(.*?)\s*(?:\n|^)\s*A:\s*(.*)", re.IGNORECASE | re.DOTALL)
_TOKEN = re.compile(r"[A-Za-z0-9]+")


@dataclass
class Ticket:
    custom_id: str
    question: str
    answer: str
    content: str
    cluster: str = "unclustered"
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def public(self, include_raw: bool = False) -> dict[str, Any]:
        d = {"custom_id": self.custom_id, "question": self.question, "answer": self.answer, "cluster": self.cluster}
        if include_raw:
            d["raw"] = self.raw
        return d


def _split_qa(content: str) -> tuple[str, str]:
    m = _QA_RE.search(content or "")
    return (m.group(1).strip(), m.group(2).strip()) if m else ((content or "").strip(), "")


def _snippet(content: str, query: str, width: int = 160) -> str:
    text = content.replace("\n", " ")
    idx = text.lower().find(query.lower()) if query else -1
    if idx == -1:
        return text[:width] + ("..." if len(text) > width else "")
    start = max(0, idx - width // 3)
    end = min(len(text), start + width)
    return f"{'...' if start else ''}{text[start:end]}{'...' if end < len(text) else ''}"


class TicketStore:
    """In-memory FTS5 index over the ticket Q&A knowledge base."""

    def __init__(self, source: Path, db_path: str = ":memory:"):
        self.source = Path(source)
        self.tickets = self._load()
        self._by_id = {t.custom_id.lower(): t for t in self.tickets}
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._build_index()
        log.info("Indexed %d ticket Q&A pairs from %s", len(self.tickets), self.source)

    def _load(self) -> list[Ticket]:
        with self.source.open() as f:
            data = json.load(f)

        # Flatten the source into (record, cluster_hint) pairs across the shapes of the json
        raw_items: list[tuple[dict, str]] = []
        if isinstance(data, list):
            raw_items = [(r, "") for r in data]
        elif isinstance(data, dict):
            clusters = data.get("clusters", data)
            if isinstance(clusters, list):
                for c in clusters:
                    if isinstance(c, dict) and "items" in c:
                        hint = c.get("label") or c.get("name") or "unclustered"
                        raw_items += [(item, hint) for item in c["items"]]
                    else:
                        raw_items.append((c, ""))
            elif isinstance(clusters, dict):
                for name, items in clusters.items():
                    if isinstance(items, list):
                        raw_items += [(item, name) for item in items]

        tickets: list[Ticket] = []
        for r, hint in raw_items:
            if not isinstance(r, dict):
                continue
            cid = r.get("custom_id") or r.get("id") or r.get("ticket_id") or r.get("key") or "UNKNOWN"
            content = r.get("content") or r.get("text") or r.get("qa") or ""
            question = r.get("question") or r.get("q") or ""
            answer = r.get("answer") or r.get("a") or ""
            if content and not (question or answer):
                question, answer = _split_qa(content)
            if not content:
                content = f"Q: {question}\nA: {answer}".strip()
            cluster = r.get("cluster") or r.get("label") or hint or "unclustered"
            tickets.append(Ticket(cid, question, answer, content, cluster, r))

        return tickets

    def _build_index(self) -> None:
        self._db.execute("DROP TABLE IF EXISTS tickets")
        self._db.execute(
            "CREATE VIRTUAL TABLE tickets USING fts5("
            "custom_id UNINDEXED, cluster UNINDEXED, content, tokenize='porter unicode61')"
        )
        self._db.executemany(
            "INSERT INTO tickets(custom_id, cluster, content) VALUES (?,?,?)",
            [(t.custom_id, t.cluster, t.content) for t in self.tickets],
        )
        self._db.commit()

    @staticmethod
    def _match_expr(query: str) -> str:
        terms = [t for t in _TOKEN.findall(query.lower()) if len(t) > 1]
        return " OR ".join(f'"{t}"' for t in terms)

    def search(self, query: str, limit: int = 10, cluster: str = "") -> list[dict]:
        expr = self._match_expr(query)
        if not expr:
            return []
        sql = ("SELECT custom_id, cluster, content, bm25(tickets) AS rank " "FROM tickets WHERE tickets MATCH ?")
        params: list[Any] = [expr]
        if cluster:
            sql += " AND cluster = ?"
            params.append(cluster)
        sql += " ORDER BY rank LIMIT ?"
        params.append(max(1, limit))
        rows = self._db.execute(sql, params).fetchall()
        # bm25 returns lower = better
        # negate so higher = better for readers.
        return [{"custom_id": cid, "cluster": cl, "snippet": _snippet(content, query), "score": round(-rank, 3)}
        
        for cid, cl, content, rank in rows]

    def get(self, custom_id: str) -> dict:
        t = self._by_id.get(custom_id.strip().lower())
        return t.public(include_raw=True) if t else {"error": f"No ticket '{custom_id}'"}

    def list_clusters(self) -> list[dict]:
        counts: dict[str, int] = {}
        for t in self.tickets:
            counts[t.cluster] = counts.get(t.cluster, 0) + 1
        return [{"cluster": k, "count": v}
                for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)]

    def get_cluster(self, cluster: str, limit: int = 20) -> list[dict]:
        name = cluster.strip().lower()
        out = [t.public() for t in self.tickets if t.cluster.lower() == name]
        return out[: max(1, limit)] if out else [{"error": f"No cluster '{cluster}'"}]

    def stats(self) -> dict:
        return {"backend": "sql-fts5", "total_pairs": len(self.tickets),
                "clusters": len({t.cluster for t in self.tickets}),
                "source": str(self.source)}