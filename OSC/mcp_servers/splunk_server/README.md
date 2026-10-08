# Splunk MCP Server (Python)

A [Model Context Protocol](https://modelcontextprotocol.io/) server built with [FastMCP](https://github.com/jlowin/fastmcp). It exposes wrappers around the **Splunk API** so an assistant can query OSC Splunk data for ReFrame application test results, performance logs, and Lmod module usage statistics.

Clients connect via **stdio** (default) or **Streamable HTTP** (`-t streamable-http`).

## Tools

| Tool | Purpose |
|------|---------|
| `splunk_search` | Execute arbitrary Splunk queries with optional time range filters. |
| `reframe_apptests` | Query Reframe application test results from Splunk. |
| `reframe_perflogs` | Analyze Reframe performance logs from Splunk. |
| `lmod_module_usage` | Report Lmod module usage statistics from Splunk. |
| `software_install_report` | Generate a report of software installations from Splunk logs. |

Each tool supports time range filtering via `earliest`, `latest`, or `days` parameters. Returned data is formatted as text or JSON depending on the tool.

## Requirements

- **Python** 3.10+ (tested with 3.12)
- **Network access** to Splunk endpoint (default: `splunk.example.com:8089`)
- **Splunk authentication** via environment variables or token:
  - `SPLUNK_TOKEN` (preferred, JWT token)
  - `SPLUNK_USERNAME` and `SPLUNK_PASSWORD` (alternative)
- Python packages (from the server directory):

```bash
pip install -r requirements.txt
```

## Configuration

Create or edit `config.json` in the server directory (or pass `-c /path/to/config.json`).

| Field | Description | Default |
|--------|-------------|---------|
| `transport` | Transport mode (`stdio` or `streamable-http`) | `stdio` |
| `host` | Bind address (HTTP only) | `127.0.0.1` |
| `port` | Listen port (HTTP only) | `8002` |
| `log_file` | Append-only log path | `logs/Latest.log` |
| `splunk_host` | Splunk server hostname | `splunk.example.com` |
| `splunk_port` | Splunk API port | `8089` |

Command-line flags override the file: `--host`, `--port`, `--log-file`, `-v` / `--verbose`. See `python server.py --help`.

Example `config.json`:

```json
{
  "transport": "stdio",
  "log_file": "logs/Latest.log",
  "splunk_host": "splunk.example.com",
  "splunk_port": 8089
}
```

## Run

From `OSC/mcp_servers/splunk_server`:

```bash
# Set authentication (required)
export SPLUNK_TOKEN=your_splunk_token

# Run server (stdio is default)
python server.py
python server.py -c /path/to/config.json -v

# Or use HTTP transport
python server.py -t streamable-http --port 8002
```

**Transport modes:**
- **stdio** (default): Direct stdin/stdout, no network exposure
- **streamable-http**: HTTP server at `http://<host>:<port>/mcp`

**Security:** This process executes Splunk queries that may access sensitive data. Use stdio for local MCP clients, or bind HTTP to localhost and place behind authentication if exposed to a network.

## Project layout

```
splunk_server/
├── server.py              # MCP server and tools
├── requirements.txt       # Python dependencies
├── config.json            # Configuration file
├── src/
│   ├── __init__.py
│   ├── config.py          # Pydantic config loading
│   └── logging.py         # File logging and FastMCP log routing
└── logs/                  # Typical location for log_file (optional)
```

## Tool usage examples

### splunk_search
```
Search recent Splunk events with custom query and time filters.
```

### reframe_apptests
```
Query Reframe application test results with optional cluster, partition, and time range.
```

### reframe_perflogs
```
Analyze Reframe performance metrics (runtime, memory, etc.) with filters.
```

### lmod_module_usage
```
Report Lmod module load statistics by module name, user, or time period.
```

### software_install_report
```
Report software installations (install-script, spack-install) by system and package. Default: last 14 days.
```

## Troubleshooting

- **Authentication errors:** Verify `SPLUNK_TOKEN` or `SPLUNK_USERNAME`/`SPLUNK_PASSWORD` are set and valid. Check token expiration.
- **Connection refused:** Confirm network access to your Splunk server and that `splunk_host`/`splunk_port` in config are correct.
- **Empty tool output:** The Splunk query may have returned no results; check time range filters and query syntax in `log_file`.
- **SSL/TLS errors:** Splunk may require certificate verification; check Splunk server configuration.

## License

Same as the parent repository (see root `LICENSE`).
