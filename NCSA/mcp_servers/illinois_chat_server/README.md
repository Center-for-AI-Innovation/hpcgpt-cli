# Illinois Chat MCP Server (Python)

A [Model Context Protocol](https://modelcontextprotocol.io/) server written in Python with [FastMCP](https://github.com/jlowin/fastmcp). It forwards tool calls to the Illinois Chat HTTP API so assistants can answer questions grounded in **Delta** and **Delta AI** documentation (retrieval-augmented courses `Delta-Documentation` and `DeltaAI-Documentation`).

clients connect to a URL such as `http://127.0.0.1:8000/mcp`.

## Tools

| Tool | Purpose |
|------|---------|
| `query_delta_documentation` | Retrieve relevant general Delta / HPC documentation (`Delta-Documentation`) for the active hpcGPT model. |
| `query_delta_ai_documentation` | Retrieve relevant Delta AI documentation (`DeltaAI-Documentation`) for the active hpcGPT model. |
| `query_hpcgpt_cuda_docs` | Retrieve relevant CUDA documentation (`hpcgpt-cuda-documentation`) for CUDA API and programming questions. |

Each tool takes a single string argument: `query`. Collection names are fixed
server-side so clients cannot select arbitrary Illinois Chat courses.

## Requirements

- Python 3.10+ (tested with 3.12)
- Network access to your Illinois Chat API endpoint
- Packages:

```bash
pip install fastmcp requests pydantic rich-argparse
```

## Configuration

1. Copy the example config and edit values:

```bash
cd NCSA/mcp_servers/illinois_chat_server
cp example.config.json config.json
```

2. Set at least `illinois_chat_url`, `illinois_chat_api_key`, and `illinois_chat_model` in `config.json`. Optional fields use defaults from `src/config.py` if omitted (`host`, `port`, `log_file`, `illinois_chat_system_prompt`).

| Field | Description |
|--------|-------------|
| `host` | Bind address (default `0.0.0.0`). |
| `port` | Listen port (default `8000`). |
| `log_file` | Append-only log path; parent directory is created if needed. |
| `illinois_chat_url` | Full URL of the chat/completions endpoint (organization-specific). |
| `illinois_chat_api_key` | API key sent in the JSON body as `api_key`. |
| `illinois_chat_model` | Model name for the upstream API. |
| `illinois_chat_system_prompt` | System message prepended to every request (has a sensible HPC default if unset in schema). |

Command-line flags exist for the same settings (`--host`, `--port`, `--illinois-chat-url`, etc.); see `python server.py --help`. The default config file path is `-c config.json`.

## Run

```bash
python server.py
# or
python server.py -c /path/to/config.json -v
```

On startup the server calls `verify_chat_connection()` (a minimal `retrieval_only` request) so misconfigured URLs or keys fail fast. Tool calls also use retrieval-only mode: Illinois Chat returns relevant contexts and the active hpcGPT model synthesizes the answer, avoiding a second upstream model generation and its latency.

- **MCP endpoint:** `http://<host>:<port>/mcp` (FastMCP default Streamable HTTP path is `/mcp` unless overridden by FastMCP settings).

Point your MCP client at that URL with Streamable HTTP transport.

## Behavior notes

- Upstream requests use `temperature` **0.3**, `stream: false`, and `retrieval_only: true` for normal tool calls.
- Retrieval contexts are returned as JSON for the active hpcGPT model to synthesize. Legacy response shapes (`message`, OpenAI-style `choices[0].message.content`, or `response`) remain supported.

## Project layout

```
illinois_chat_server/
├── server.py          # MCP server and tools
├── example.config.json # Template for config.json
├── src/
│   ├── config.py      # Pydantic config loading
│   └── logging.py     # File logging and FastMCP log routing
└── logs/              # Typical location for log_file (optional)
```

## Troubleshooting

- **Startup fails after “verify”:** Check `illinois_chat_url`, API key, and model name; confirm HTTP 200 and JSON from the Illinois Chat API.
- **401 / 403 on verify:** Key rejected by the upstream service.
- **404 on verify:** Wrong path in `illinois_chat_url`.

## License

Same as the parent repository (see root `LICENSE`).
