# Slurm MCP Server (Python)

A [Model Context Protocol](https://modelcontextprotocol.io/) server built with [FastMCP](https://github.com/jlowin/fastmcp). It exposes thin wrappers around local **Slurm** and **`accounts`** commands plus a read-only structured job tracker.

Clients connect through **Streamable HTTP** or run the server as a local **stdio** sidecar.

## Tools

| Tool | Purpose |
|------|---------|
| `accounts` | Runs `accounts -u <username>` and returns stdout (site-specific accounting utility; must exist on `PATH`). |
| `sinfo` | Runs `sinfo` with optional extra arguments as a single string (e.g. `-N`, `-o "..."`). |
| `squeue` | Runs `squeue` with optional extra arguments as a single string. |
| `scontrol` | Runs `scontrol show job <job_id>` with optional extra arguments. |
| `list_jobs` | Merges active `squeue --json` data with recent `sacct --json` history and returns normalized jobs. |
| `get_job` | Returns normalized status, resources, exit code, and log paths for one job. |
| `get_job_usage` | Returns available Slurm accounting data for a job and its steps. |

The tracker is read-only. It cannot submit, cancel, hold, release, or otherwise modify jobs. The four legacy wrappers return command text; the tracker tools return structured objects and surface command failures.

## Requirements

- **Python** 3.10+ (tested in line with other MCP servers in this repo)
- **Slurm client tools** (`sinfo`, `squeue`, `scontrol`) on `PATH` if you use those tools
- **Slurm accounting tools** (`sacct`) if you use recent history or usage tracking
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
| `transport` | `streamable-http` (default) or `stdio`. |
| `identity_mode` | `explicit` requires a tool username; `process` always uses the MCP process's effective Unix account. |

Command-line flags override the file: `--host`, `--port`, `--log-file`, `--transport`, `--identity-mode`, `-v` / `--verbose`. See `python server.py --help`.

Example `config.json`:

```json
{
  "host": "127.0.0.1",
  "port": 8001,
  "log_file": "logs/Latest.log",
  "transport": "streamable-http",
  "identity_mode": "explicit"
}
```

## Run

From `NCSA/mcp_servers/slurm_server`:

```bash
python server.py
python server.py -c /path/to/config.json -v
python server.py --transport stdio --identity-mode process
```

- **MCP endpoint:** `http://<host>:<port>/mcp`

Point your MCP client at that URL with **Streamable HTTP** transport.

For a per-user OpenCode deployment, prefer `stdio` with `identity_mode=process`. The server then inherits the user's Unix identity and ignores any username supplied by the model. A shared HTTP deployment has no authenticated Unix caller identity, so it must use `explicit` mode and should be restricted to a trusted network.

## Tracker examples

The equivalent scheduler commands are:

```bash
squeue --json -u "$USER"
sacct -X --json -u "$USER" -S now-24hours
sacct --json -u "$USER" -j 123456
```

`list_jobs` defaults to 24 hours of completed history, accepts compact lookbacks such as `30m`, `24h`, `7d`, or `12w`, caps history at 90 days, and caps returned results at 200 jobs. Scheduler commands time out after 20 seconds. Historical visibility still depends on the cluster's Slurm accounting retention.

Run the fixture-based tests without contacting Slurm:

```bash
python -m unittest discover -s tests -v
```

**Security:** The legacy `sinfo` / `squeue` / `scontrol` tools accept argument strings. Tracker tools use fixed argument vectors and validate usernames, job IDs, lookbacks, and limits. Bind HTTP deployments to localhost or place them behind authentication and a trusted network; do not expose them directly to the public internet.

## Project layout

```
slurm_server/
├── server.py           # MCP server and tools
├── requirements.txt    # Python dependencies
├── config.json         # Local config (optional; create from example above)
├── src/
│   ├── config.py       # Pydantic config loading
│   ├── tracker.py      # Structured read-only job tracker
│   └── logging.py      # File logging and FastMCP log routing
├── tests/              # Fixture-based tracker tests
└── logs/               # Typical location for log_file (optional)
```

## Troubleshooting

- **Empty tool output:** The Slurm binary may have written to stderr, or the command failed silently from the tool’s perspective; inspect `log_file` and run the same command in a shell on the host.
- **`accounts` not found:** Install or load the site module that provides `accounts`, or avoid that tool.
- **Permission errors:** Slurm commands enforce the same permissions as for your Unix account; the MCP server does not elevate privileges.

## License

Same as the parent repository (see root `LICENSE`).
