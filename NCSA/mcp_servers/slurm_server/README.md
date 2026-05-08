# Slurm MCP Server (Python)

A [Model Context Protocol](https://modelcontextprotocol.io/) server built with [FastMCP](https://github.com/jlowin/fastmcp). It exposes thin wrappers around local **Slurm** and **`accounts`** commands so an assistant can inspect partitions, queues, and account usage on a cluster node where those binaries exist and your user has permission to run them.

Clients connect with **Streamable HTTP** to a URL such as `http://127.0.0.1:8001/mcp`.

## Tools

| Tool | Purpose |
|------|---------|
| `accounts` | Runs `accounts -u <username>` and returns stdout (site-specific accounting utility; must exist on `PATH`). |
| `sinfo` | Runs `sinfo` with optional extra arguments as a single string (e.g. `-N`, `-o "..."`). |
| `squeue` | Runs `squeue` with optional extra arguments as a single string. |
| `scontrol` | Runs `scontrol` with optional `scontrol_args` (the `job_id` parameter is currently unused in the implementation). |

Returned text is **standard output only**; stderr is not merged into the tool result. Failed commands may still return empty output—check cluster policies and the server log file.

## Requirements

- **Python** 3.10+ (tested in line with other MCP servers in this repo)
- **Slurm client tools** (`sinfo`, `squeue`, `scontrol`) on `PATH` if you use those tools
- **`accounts`** on `PATH` if you use `accounts` (many sites use a custom or scheduler-specific binary)
- Python packages (from the repo directory):

```bash
pip install -r requirements.txt
```

## Configuration

Create or edit `config.json` in the server directory (or pass `-c /path/to/config.json`). Defaults match `src/config.py`.

| Field | Description |
|--------|-------------|
| `host` | Bind address (default `127.0.0.1`). |
| `port` | Listen port (default `8001`). |
| `log_file` | Append-only log path; parent directory is created if needed. |

Command-line flags override the file: `--host`, `--port`, `--log-file`, `-v` / `--verbose`. See `python server.py --help`.

Example `config.json`:

```json
{
  "host": "127.0.0.1",
  "port": 8001,
  "log_file": "logs/Latest.log"
}
```

## Run

From `NCSA/mcp_servers/slurm_server`:

```bash
python server.py
python server.py -c /path/to/config.json -v
```

- **MCP endpoint:** `http://<host>:<port>/mcp`

Point your MCP client at that URL with **Streamable HTTP** transport.

**Security:** This process executes arbitrary argument strings passed into `sinfo` / `squeue` / `scontrol` (and fixed `accounts -u`). Bind to localhost or place behind authentication and a trusted network; do not expose directly to the public internet.

## Project layout

```
slurm_server/
├── server.py           # MCP server and tools
├── requirements.txt    # Python dependencies
├── config.json         # Local config (optional; create from example above)
├── src/
│   ├── config.py       # Pydantic config loading
│   └── logging.py      # File logging and FastMCP log routing
└── logs/               # Typical location for log_file (optional)
```

## Troubleshooting

- **Empty tool output:** The Slurm binary may have written to stderr, or the command failed silently from the tool’s perspective; inspect `log_file` and run the same command in a shell on the host.
- **`accounts` not found:** Install or load the site module that provides `accounts`, or avoid that tool.
- **Permission errors:** Slurm commands enforce the same permissions as for your Unix account; the MCP server does not elevate privileges.

## License

Same as the parent repository (see root `LICENSE`).
