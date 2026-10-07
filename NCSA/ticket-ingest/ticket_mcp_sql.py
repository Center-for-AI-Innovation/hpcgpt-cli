#!/usr/bin/env python3
"""
Ticket MCP Server

Exposes the deduplicated/clustered Jira ticket knowledge base via FastMCP using 
an in-memory SQLite FTS5 index with BM25 ranking. 

USAGE:
  export TICKET_DATA_DIR=/u/rsingal/hpcgpt-cli/NCSA/ticket-ingest/data
  python ticket_mcp_sql.py
  python ticket_mcp_sql.py search "gpu" 
  python ticket_mcp_sql.py stats
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DATA_DIR = Path(os.environ.get("TICKET_DATA_DIR", "/u/rsingal/hpcgpt-cli/NCSA/ticket-ingest/data"))
DEFAULT_HOST = os.environ.get("TICKET_HTTP_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("TICKET_HTTP_PORT", "8888"))

_JSON_CANDIDATES = [
    Path(os.environ["TICKET_DATA_FILE"]) if os.environ.get("TICKET_DATA_FILE") else None,
    DATA_DIR / "clustered.json",
    DATA_DIR / "dedup" / "deduplicated.json",
    DATA_DIR / "deduplicated.json",
]

_ID_KEYS = ("custom_id", "id", "ticket_id", "key")
_CONTENT_KEYS = ("content", "text", "qa", "body")
_QUESTION_KEYS = ("question", "q")
_ANSWER_KEYS = ("answer", "a")
_CLUSTER_KEYS = ("cluster", "cluster_id", "cluster_label", "topic", "category", "label")
_QA_RE = re.compile(r"Q:\s*(.*?)\s*(?:\n|^)\s*A:\s*(.*)", re.IGNORECASE | re.DOTALL)
_TOKEN = re.compile(r"[A-Za-z0-9]+")

_THINK_PAIR = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
_THINK_OPEN = re.compile(r"<think>.*?(?=\bQ:)", re.IGNORECASE | re.DOTALL)
_THINK_TAG = re.compile(r"</?think>", re.IGNORECASE)


@dataclass
class Ticket:
    custom_id: str
    question: str
    answer: str
    content: str
    cluster: str = "unclustered"
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def public(self, include_raw: bool = False) -> dict[str, Any]:
        d = {"custom_id": self.custom_id, "question": self.question,
             "answer": self.answer, "cluster": self.cluster}
        if include_raw:
            d["raw"] = self.raw
        return d


def _first(d: dict, keys: tuple[str, ...], default: str = "") -> str:
    for k in keys:
        v = d.get(k)
        if v is not None and v != "":
            return str(v)
    return default


def _strip_think(text: str) -> str:
    if not text or "<think" not in text.lower():
        return text
    text = _THINK_PAIR.sub("", text)
    text = _THINK_OPEN.sub("", text)
    text = _THINK_TAG.sub("", text)
    return text.strip()


def _split_qa(content: str) -> tuple[str, str]:
    m = _QA_RE.search(content or "")
    return (m.group(1).strip(), m.group(2).strip()) if m else ((content or "").strip(), "")


def _normalize(record: Any, cluster_hint: str = "") -> Ticket | None:
    if not isinstance(record, dict):
        return None
    cid = _first(record, _ID_KEYS, "UNKNOWN")
    content = _strip_think(_first(record, _CONTENT_KEYS))
    question = _strip_think(_first(record, _QUESTION_KEYS))
    answer = _strip_think(_first(record, _ANSWER_KEYS))
    if content and not (question or answer):
        question, answer = _split_qa(content)
    if not content:
        content = f"Q: {question}\nA: {answer}".strip()
    cluster = _first(record, _CLUSTER_KEYS, cluster_hint or "unclustered")
    return Ticket(cid, question, answer, content, cluster, record)


def _iter_records(data: Any):
    if isinstance(data, list):
        for r in data:
            yield r, ""
    elif isinstance(data, dict):
        clusters = data.get("clusters", data)
        if isinstance(clusters, dict):
            for name, items in clusters.items():
                if isinstance(items, list):
                    for r in items:
                        yield r, str(name)
                else:
                    yield items, ""
        elif isinstance(clusters, list):
            for c in clusters:
                if isinstance(c, dict) and "items" in c:
                    name = _first(c, ("label", "name", "cluster", "topic"), "unclustered")
                    for r in c["items"]:
                        yield r, name
                else:
                    yield c, ""


def _resolve_json() -> Path:
    p = next((x for x in _JSON_CANDIDATES if x and x.exists()), None)
    if p is None:
        searched = ", ".join(str(x) for x in _JSON_CANDIDATES if x)
        raise FileNotFoundError(f"No JSON source found. Looked at: {searched}")
    return p


def load_tickets() -> list[Ticket]:
    with _resolve_json().open() as f:
        data = json.load(f)
    return [t for r, hint in _iter_records(data) if (t := _normalize(r, hint))]

_SOURCE = _resolve_json()
_TICKETS: list[Ticket] = load_tickets()
_BY_ID = {t.custom_id.lower(): t for t in _TICKETS}

_DB_PATH = os.environ.get("TICKET_DB", ":memory:")
_DB = sqlite3.connect(_DB_PATH, check_same_thread=False)
_DB.execute("DROP TABLE IF EXISTS tickets")
_DB.execute(
    "CREATE VIRTUAL TABLE tickets USING fts5("
    "custom_id UNINDEXED, cluster UNINDEXED, content, tokenize='porter unicode61')"
)
_DB.executemany(
    "INSERT INTO tickets(custom_id, cluster, content) VALUES (?,?,?)",
    [(t.custom_id, t.cluster, t.content) for t in _TICKETS],
)
_DB.commit()


def _snippet(content: str, query: str, width: int = 160) -> str:
    text = content.replace("\n", " ")
    idx = text.lower().find(query.lower()) if query else -1
    if idx == -1:
        return text[:width] + ("..." if len(text) > width else "")
    start = max(0, idx - width // 3)
    end = min(len(text), start + width)
    return f"{'...' if start else ''}{text[start:end]}{'...' if end < len(text) else ''}"


def _match_expr(query: str) -> str:
    terms = [t for t in _TOKEN.findall(query.lower()) if len(t) > 1]
    return " OR ".join(f'"{t}"' for t in terms)


def _search(query: str, limit: int = 10, cluster: str = "") -> list[dict]:
    expr = _match_expr(query)
    if not expr:
        return []
    sql = ("SELECT custom_id, cluster, content, bm25(tickets) AS rank "
           "FROM tickets WHERE tickets MATCH ?")
    params: list[Any] = [expr]
    if cluster:
        sql += " AND cluster = ?"
        params.append(cluster)
    sql += " ORDER BY rank LIMIT ?"
    params.append(max(1, limit))
    rows = _DB.execute(sql, params).fetchall()
    return [{"custom_id": cid, "cluster": cl, "snippet": _snippet(content, query),
             "score": round(-rank, 3)}
            for cid, cl, content, rank in rows]


def _get(custom_id: str) -> dict:
    t = _BY_ID.get(custom_id.strip().lower())
    return t.public(include_raw=True) if t else {"error": f"No ticket '{custom_id}'"}


def _list_clusters() -> list[dict]:
    counts: dict[str, int] = {}
    for t in _TICKETS:
        counts[t.cluster] = counts.get(t.cluster, 0) + 1
    return [{"cluster": k, "count": v}
            for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)]


def _get_cluster(cluster: str, limit: int = 20) -> list[dict]:
    name = cluster.strip().lower()
    out = [t.public() for t in _TICKETS if t.cluster.lower() == name]
    return out[: max(1, limit)] if out else [{"error": f"No cluster '{cluster}'"}]


def _stats() -> dict:
    return {"backend": "sql-fts5", "total_pairs": len(_TICKETS),
            "clusters": len({t.cluster for t in _TICKETS}), "source": str(_SOURCE),
            "db": _DB_PATH}


def _build_mcp():
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("hpcgpt-tickets-sql")

    @mcp.tool()
    def search_tickets(query: str, limit: int = 10, cluster: str = "") -> list[dict]:
        """FTS5/bm25 search of the ticket Q&A knowledge base. Optionally restrict to a cluster.
        Returns custom_id, cluster, a snippet and a relevance score (higher = better)."""
        return _search(query, limit, cluster)

    @mcp.tool()
    def get_ticket(custom_id: str) -> dict:
        """Fetch a ticket's full Q&A by custom_id (e.g. SUP-21267)."""
        return _get(custom_id)

    @mcp.tool()
    def list_clusters() -> list[dict]:
        """List clusters/topics with Q&A pair counts, largest first."""
        return _list_clusters()

    @mcp.tool()
    def get_cluster(cluster: str, limit: int = 20) -> list[dict]:
        """Return Q&A pairs in a given cluster/topic (case-insensitive)."""
        return _get_cluster(cluster, limit)

    @mcp.tool()
    def stats() -> dict:
        """KB summary: backend, total pairs, cluster count, source, db path."""
        return _stats()

    return mcp


def _run_http(host: str, port: int) -> None:
    mcp = _build_mcp()
    mcp.settings.host = host
    mcp.settings.port = port
    print(f"[sql] serving MCP over streamable-http at http://{host}:{port}/mcp",
          file=sys.stderr)
    mcp.run(transport="streamable-http")


def _cli(argv: list[str]) -> bool:
    if not argv:
        return False
    cmd = argv[0]
    if cmd == "search":
        for r in _search(" ".join(argv[1:]), limit=10):
            print(f"{r['score']:>8}  {r['custom_id']:<12} [{r['cluster']}]  {r['snippet']}")
    elif cmd == "get":
        print(json.dumps(_get(argv[1]), indent=2))
    elif cmd == "clusters":
        for c in _list_clusters():
            print(f"{c['count']:>5}  {c['cluster']}")
    elif cmd == "stats":
        print(json.dumps(_stats(), indent=2))
    elif cmd == "stdio":
        _build_mcp().run(transport="stdio")
    else:
        print(f"unknown command '{cmd}' (search|get|clusters|stats|stdio)")
    return True


if __name__ == "__main__":
    if sys.argv[1:]:
        _cli(sys.argv[1:])
    else:
        _run_http(DEFAULT_HOST, DEFAULT_PORT)