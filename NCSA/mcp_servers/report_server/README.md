# Report MCP Server (Python)

A [Model Context Protocol](https://modelcontextprotocol.io/) server built with [FastMCP](https://github.com/jlowin/fastmcp) for submitting HPC-GPT support reports. It currently targets **Jira** issue creation and includes a scaffolded (not yet implemented) **email** mode.

When run in normal server mode, clients should connect with Streamable HTTP to a URL like `http://127.0.0.1:8003/mcp`.

## Tool

| Tool | Purpose |
|------|---------|
| `send_support_report` | Create a support report using structured metadata (title, description, conversation history, hostname, user, working directory). In Jira mode, this creates a Jira issue and adds an internal staff comment with host/user context. |

### `send_support_report` input fields

- `title`: short ticket title
- `description`: one-paragraph issue description
- `conversation_history`: list of role/content messages that led to reporting
- `hostname`: system host where the issue occurred
- `user`: reporting username
- `current_working_directory`: reporter's current working directory

## Requirements

- Python 3.10+
- Access to a Jira instance (for `mode: "jira"`)
- Site utility `userinfo` on `PATH` (used to enrich ticket metadata; if unavailable the server falls back to minimal user context)
- Python dependencies:

```bash
pip install -r requirements.txt
```

Current `requirements.txt` contains:

- `fastmcp==3.0.2`
- `pydantic==2.12.5`
- `jira>=3.8.0`
- `rich-argparse>=1.6.0`

## Configuration

Use `example.config.json` as a template:

```bash
cp example.config.json config.json
```

Top-level fields:

| Field | Description |
|------|-------------|
| `host` | Bind address (default in schema: `127.0.0.1`). |
| `port` | Listen port (default in schema: `8003`). |
| `log_file` | Log output file path. |
| `log_level` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `mode` | `jira` or `email`. |
| `jira` | Jira connection/issue defaults (required when `mode` is `jira`). |
| `email` | Email metadata (required when `mode` is `email`, but email sending is not implemented yet). |

### Jira config (`mode: "jira"`)

- `url`: Jira base URL
- `authentication_method`: `personal_access_token` or `api_key`
- `personal_access_token`: required for token auth
- `username` + `api_key`: required for API-key auth
- `project`: Jira project key/name
- `issue_type`: Jira issue type
- `default_fields`: optional map of additional default fields to set post-creation

## Run

From `NCSA/mcp_servers/report_server`:

```bash
python server.py
python server.py -c /path/to/config.json -v
```

Useful flags:

- `-c, --config`: config file path (default `config.json`)
- `--host`, `--port`, `--log-file`: override config file values
- `-v, --verbose`: set file logging to DEBUG

## Project layout

```text
report_server/
├── server.py              # CLI entrypoint and startup behavior
├── requirements.txt       # Python dependencies
├── example.config.json    # Config template
└── src/
    ├── config.py          # Pydantic config models + validation
    ├── report_mcp.py      # MCP server/tool implementation
    ├── jira_connector.py  # Jira API connection and issue helpers
    └── logging.py         # Shared logging setup
```

## Troubleshooting

- **Config validation error**: ensure `mode` is valid and required nested blocks/credentials are present.
- **Jira auth failure**: verify `authentication_method` matches supplied credentials.
- **User lookup issues**: if `userinfo` is missing or returns an error, ticket creation still attempts fallback reporter handling.
- **No MCP endpoint exposed**: verify the process is running, confirm host/port in `config.json`, and check that your client is using Streamable HTTP against `/mcp`.

## License

Same as the parent repository (see root `LICENSE`).
