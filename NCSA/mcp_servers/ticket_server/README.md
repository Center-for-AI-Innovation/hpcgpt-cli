# Ticket Knowledge Base MCP Server (Python)

A [Model Context Protocol](https://modelcontextprotocol.io/) server built with
[FastMCP](https://github.com/jlowin/fastmcp) that exposes the NCSA
support-ticket Q&A knowledge base to hpcGPT. Retrieval uses an in-memory SQLite
**FTS5** index with **bm25** ranking (Porter stemming, IDF, length
normalization).

When run in normal server mode, clients connect with Streamable HTTP to a URL
like `http://0.0.0.0:8000/mcp`.

## Tools

| Tool | Purpose |
|------|---------|
| `search_tickets` | bm25 search over the Q&A pairs; optional cluster filter. |
| `get_ticket` | Fetch one ticket's full Q&A by `custom_id` (e.g. `SUP-21267`). |
| `list_clusters` | List clusters/topics with pair counts. |
| `get_cluster` | Return the Q&A pairs in a cluster/topic. |
| `stats` | Backend, total pairs, cluster count, source file. |

## Requirements

- Python 3.10+
- A knowledge-base JSON file produced by the ticket-ingest pipeline (see below)
- Python dependencies:

```bash
pip install -r requirements.txt
```

Current `requirements.txt`:

- `fastmcp==3.0.2`
- `pydantic==2.12.5`
- `rich-argparse>=1.6.0`

## Producing the data this server needs

The server does **not** ship with ticket data. It indexes a JSON knowledge-base
file produced by the ticket-ingest pipeline (`NCSA/ticket-ingest/`). Generate it
first, then point the server at it.

Resolution order: `data_file` from config (if set), then `clustered.json`, then
`dedup/deduplicated.json` under `data_dir`. Prefer `clustered.json` -- it carries
cluster labels, which `list_clusters`, `get_cluster` and the cluster filter
depend on. `deduplicated.json` works too, but every ticket reports as
`unclustered`.

Pipeline steps:

1. **Input.** Place exported raw tickets as a JSONL file in `data/input/`
   (e.g. `Delta-25.jsonl`), one ticket per line.
2. **Summarize.** Submit the summarization job (LLM on a GPU node via SLURM) to
   turn each raw ticket into a clean `Q:`/`A:` pair under `data/output/`. Track
   it with `watch squeue -j <job_id>`.
3. **Deduplicate.** Run the dedup step to write `data/dedup/deduplicated.json`.
4. **Cluster.** Run the clustering step to write `data/clustered.json` -- the
   file the server should index.

Restart the server after any re-ingest so it rebuilds the index.

> **Data-quality note.** If summaries contain leaked `<think>` reasoning or
> entries with no `A:`, fix the summarize step rather than relying on the
> server. The server strips closed `<think>` blocks defensively, but entries
> that are pure reasoning with no answer cannot be repaired at read time and
> should be regenerated upstream.

## Configuration

Use `example.config.json` as a template (the real `config.json` is gitignored):

```bash
cp example.config.json config.json
```

| Field | Description |
|------|-------------|
| `host` | Bind address. `0.0.0.0` makes it reachable remotely. |
| `port` | Listen port. |
| `log_file` | Log output path. `logs/Latest.log` rotates the previous run. |
| `log_level` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `data_dir` | Directory holding `clustered.json` / `dedup/deduplicated.json`. |
| `data_file` | Explicit path to the JSON to index (overrides `data_dir`). |
| `db_path` | SQLite path. `:memory:` rebuilds the index on each start. |

## Run

From `NCSA/mcp_servers/ticket_server`:

```bash
python server.py
python server.py -c /path/to/config.json --port 8000 -v
python server.py --data-file /path/to/clustered.json
```

Useful flags:

- `-c, --config`: config file path (default `config.json`)
- `--host`, `--port`, `--data-file`, `--log-file`: override config file values
- `-v, --verbose`: set file logging to DEBUG

> `0.0.0.0` exposes the server to anything that can reach the host and port and
> the tools read the full ticket KB. Run it on a host hpcGPT can reach with
> access controls in front, not on a shared login node long-term.

## Project layout

```text
ticket_server/
├── server.py              # CLI entrypoint and startup behavior
├── requirements.txt       # Python dependencies
├── example.config.json    # Config template
└── src/
    ├── config.py          # Pydantic config model + validation
    ├── ticket_mcp.py      # MCP server/tool implementation
    ├── store.py           # Data loading, cleaning, FTS5 index, search
    └── logging.py         # Shared logging setup
```

## Smoke test with curl

Streamable-http needs an `initialize` handshake to get a session id and every
request must send `Accept: application/json, text/event-stream`. Responses are
SSE (`data: {...}` lines).

```bash
URL=http://127.0.0.1:8000/mcp
CT="Content-Type: application/json"
AC="Accept: application/json, text/event-stream"

SID=$(curl -s -D - -o /dev/null -X POST $URL -H "$CT" -H "$AC" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}' \
  | grep -i mcp-session-id | awk '{print $2}' | tr -d '\r')

curl -s -o /dev/null -X POST $URL -H "$CT" -H "$AC" -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'

curl -s -X POST $URL -H "$CT" -H "$AC" -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"search_tickets","arguments":{"query":"how do I request a gpu node","limit":3}}}'
```

## Troubleshooting

- **Config validation error**: check `log_level` is valid and the data file
  resolves (set `data_file` or ensure `data_dir` holds the JSON).
- **Every ticket is `unclustered`**: the server loaded `deduplicated.json`.
  Point `data_file` at the real `clustered.json`.
- **No MCP endpoint**: confirm the process is running, check host/port in
  `config.json` and use Streamable HTTP against `/mcp`.

## License

Same as the parent repository (see root `LICENSE`).