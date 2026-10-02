# Slurm MCP Server (Python)

A [Model Context Protocol](https://modelcontextprotocol.io/) server built with [FastMCP](https://github.com/jlowin/fastmcp). It exposes thin wrappers around local cluster commands — **Slurm** tools and site utilities such as **`accounts`** — so an assistant can inspect partitions, queues, and account usage on a cluster node where those binaries exist and your user has permission to run them.

Clients connect with **Streamable HTTP** to a URL such as `http://127.0.0.1:8001/mcp`.

## Tools

Tools are **generated from the `commands` list in `config.json`** — one tool per command, named after the command. Nothing is hard-coded, so adding a command to the cluster's toolbox is a config change and a restart.

At startup, for each configured command the server:

1. Looks the command up on `PATH`. If it is not there, the command is **skipped** and a warning is logged. Any other registration error is logged as an error, and startup continues with the remaining commands.
2. Runs `<command> --help` (falling back to `-h`) and uses that output — the usage line and the list of flags — as the tool description, so the model sees the same flags the command actually supports.
3. Logs the registration, and logs a summary of how many of the configured commands were registered.

If none of the configured commands could be registered, the server exits with an error rather than starting with no tools.

Each generated tool takes a single optional `args` parameter: a shell-style argument string appended to the command (for example `-N -l`, or `show job 12345`). It is split with `shlex`, not run through a shell, so no pipes, redirection, or globbing. Empty `args` runs the bare command.

The default command set is `sinfo`, `squeue`, `scontrol`, `accounts`, and `jobcharge`.

Returned text is the command's **standard output**. If the command exits non-zero, the tool returns an `Error (<code>) running <command>: <details>` string built from stderr (or stdout when stderr is empty).

## Requirements

- **Python** 3.10+ (tested in line with other MCP servers in this repo)
- The commands you list in `commands` on `PATH` — typically **Slurm client tools** (`sinfo`, `squeue`, `scontrol`) and site utilities (`accounts`, `jobcharge`)
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
| `commands` | Commands to expose as tools (default `sinfo`, `squeue`, `scontrol`, `accounts`, `jobcharge`). |
| `command_timeout` | Seconds before a command is killed, including the startup `--help` probe (default `30`). |
| `max_help_chars` | Cap on how much `--help` output goes into one tool description; `0` means no limit (default `4000`). |

Command-line flags override the file: `--host`, `--port`, `--log-file`, `--command-timeout`, `-v` / `--verbose`. See `python server.py --help`.

Example `config.json`:

```json
{
  "host": "127.0.0.1",
  "port": 8001,
  "log_file": "logs/Latest.log",
  "command_timeout": 30,
  "max_help_chars": 4000,
  "commands": [
    "sinfo",
    "squeue",
    "scontrol",
    "accounts",
    "jobcharge"
  ]
}
```

A command may instead be written as an object to add a summary line above its `--help` output in the tool description. Use this when the command's own help does not make clear *when* the model should reach for it:

```json
"commands": [
  "sinfo",
  {
    "name": "jobcharge",
    "description": "Report the service-unit charges for a user's completed jobs. Use for questions about allocation usage and job cost."
  }
]
```

## Run

From `NCSA/mcp_servers/slurm_server`:

```bash
python server.py
python server.py -c /path/to/config.json -v
```

- **MCP endpoint:** `http://<host>:<port>/mcp`

Point your MCP client at that URL with **Streamable HTTP** transport.

**Security:** This process executes arbitrary argument strings against every command in `commands`. That list is the allowlist — keep it to read-only query commands, and do not add anything that submits, cancels, or modifies work unless you intend the model to be able to do that. Bind to localhost or place behind authentication and a trusted network; do not expose directly to the public internet.

## Project layout

```
slurm_server/
├── server.py           # MCP server and per-command tool registration
├── requirements.txt    # Python dependencies
├── config.json         # Local config (optional; create from example above)
├── src/
│   ├── config.py       # Pydantic config loading
│   └── logging.py      # File logging and FastMCP log routing
└── logs/               # Typical location for log_file (optional)
```

## Troubleshooting

- **A tool is missing:** Check `log_file` for `Failed to register tool for command <name>`. The usual cause is the command not being on `PATH` for the user running the server — load the site module that provides it, or drop it from `commands`.
- **Generic tool description:** If the log says `No help output from <name>`, that command answered neither `--help` nor `-h`. The tool still works; add a `description` for it in `config.json` so the model knows what it does.
- **Truncated help:** `Truncated help output for <name>` in the log means the command's help exceeded `max_help_chars`. Raise it (or set `0`) if the model needs the flags that got cut.
- **Empty tool output:** The command may have succeeded with nothing to report; run the same command in a shell on the host to confirm.
- **Permission errors:** Commands enforce the same permissions as for your Unix account; the MCP server does not elevate privileges.

## License

Same as the parent repository (see root `LICENSE`).
