# OSC Chat MCP Server (Python)

A [Model Context Protocol](https://modelcontextprotocol.io/) server written in Python with [FastMCP](https://github.com/jlowin/fastmcp). It forwards tool calls to the OSC Chat HTTP API so assistants can answer questions grounded in OSC documentation (retrieval-augmented courses `OSCDocs`).

clients connect to a URL such as `http://127.0.0.1:8000/mcp`.

## Tools

| Tool | Purpose |
|------|---------|
| `osc-docs` | Query OSC documentation (`OSCDocs`). |

Each tool takes a single string argument: `query`.

## Requirements

- Python 3.10+ (tested with 3.12)
- Network access to your OSC Chat API endpoint
- Packages:

```bash
pip install fastmcp requests pydantic rich-argparse
```

## Configuration

1. Copy the example config and edit values:

```bash
cd OSC/mcp_servers/osc_chat_server
cp example.config.json config.json
```

2. Set at least `osc_chat_url`, `osc_chat_api_key`, and `osc_chat_model` in `config.json`. Optional fields use defaults from `src/config.py` if omitted (`host`, `port`, `log_file`, `osc_chat_system_prompt`).

| Field | Description |
|--------|-------------|
| `host` | Bind address (default `0.0.0.0`). |
| `port` | Listen port (default `8000`). |
| `log_file` | Append-only log path; parent directory is created if needed. |
| osc_chat_url` | Full URL of the chat/completions endpoint (organization-specific). |
| `osc_chat_api_key` | API key sent in the JSON body as `api_key`. |
| `osc_chat_model` | Model name for the upstream API. |
| `osc_chat_system_prompt` | System message prepended to every request (has a sensible HPC default if unset in schema). |

Command-line flags exist for the same settings (`--host`, `--port`, `--illinois-chat-url`, etc.); see `python server.py --help`. The default config file path is `-c config.json`.

## Run

```bash
python server.py
# or
python server.py -c /path/to/config.json -v
```

On startup the server calls `verify_chat_connection()` (a minimal `retrieval_only` request) so misconfigured URLs or keys fail fast.

- **MCP endpoint:** `http://<host>:<port>/mcp` (FastMCP default Streamable HTTP path is `/mcp` unless overridden by FastMCP settings).

Point your MCP client at that URL with Streamable HTTP transport.

## Behavior notes

- Upstream requests use `temperature` **0.3**, `stream: false`, and `retrieval_only: false` for normal tool calls.
- Responses are normalized from several possible JSON shapes (`message`, OpenAI-style `choices[0].message.content`, or `response`).

## Project layout

```
pychat_server/
├── server.py          # MCP server and tools
├── config.example     # Template for config.json
├── src/
│   ├── config.py      # Pydantic config loading
│   └── logging.py     # File logging and FastMCP log routing
└── logs/              # Typical location for log_file (optional)
```

## Troubleshooting

- **Startup fails after “verify”:** Check `osc_chat_url`, API key, and model name; confirm HTTP 200 and JSON from the OSC Chat API.
- **401 / 403 on verify:** Key rejected by the upstream service.
- **404 on verify:** Wrong path in `osc_chat_url`.

## License

Same as the parent repository (see root `LICENSE`).
