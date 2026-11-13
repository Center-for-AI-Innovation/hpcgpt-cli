# hpcGPT Chat MCP Server (Python)

A [Model Context Protocol](https://modelcontextprotocol.io/) server 
written in Python with [FastMCP](https://github.com/jlowin/fastmcp). It
forwards tool calls to the hpcGPT Chat HTTP API so its agents can answer
questions grounded in pre-loaded documentation via retrieval augmented 
generation (RAG).

Clients connect to a URL such as `http://127.0.0.1:8001/mcp`.

## Tools

Tools are defined by the `courses` list in `config.json`. Each entry is
verified against the hpcGPT Chat API at startup; successful entries 
become one MCP tool named `query_<name>` that takes a single string 
argument: `query`.

Example tools (from `config.json`):

| Tool         | Purpose                                                  |
| ------------ |--------------------------------------------------------- |
| `query_docs` | Retrieve general HPC documentation for the hpcGPT agent. |

To add a course, append an object to `courses` and restart the server—no
code changes required: Tools use static course names once the server
starts so clients cannot select arbitrary hpcGPT Chat courses.

```json
{
  "name": "My-Course-Name",
  "description": "When the model should use this tool.",
  "model": "Optional model override for this course",
  "system_prompt": "Optional system prompt override for this course"
}
```

| Field           | Required | Description                                                                        |
| --------------- | -------- | ---------------------------------------------------------------------------------- |
| `name`          | Yes      | `course_name` sent upstream. Also used to form the MCP tool name (`query_<name>`). |
| `description`   | Yes      | Tool description for the model (when to call this tool).                           |
| `model`         | No       | Model for this course; defaults to top-level `model`.                              |
| `system_prompt` | No       | System message for this course; defaults to top-level `system_prompt`.             |

An empty `courses` list is rejected at startup. If every course fails
verification, the server exits instead of running with no tools.

## Requirements

- Python 3.10+ (tested with 3.12)
- Network access to your hpcGPT Chat API endpoint
- Packages:

```bash
pip install fastmcp requests rich-argparse
```

## Configuration

1. Copy the example config and edit values:

```bash
cd SDSC/mcp/chat
cp config.json config.json
```

2. Set at least `url`, `api_key`, and `model` in `config.json`. Optional
fields use defaults from `src/config.py` if omitted (`host`, `port`, 
`log_file`, `system_prompt`, `timeout`).

| Field           | Description                                                                               |
| --------------- | ----------------------------------------------------------------------------------------- |
| `host`          | Bind address (default `127.0.0.1`).                                                       |
| `port`          | Listen port (default `8001`).                                                             |
| `log_file`      | Append-only log path; parent directory is created if needed.                              |
| `url`           | Full URL of the chat/completions endpoint (organization-specific).                        |
| `api_key`       | API key sent in the JSON body as `api_key`.                                               |
| `model`         | Default model name for the upstream API (per-course `model` overrides this).              |
| `system_prompt` | Default system message prepended to requests (per-course `system_prompt` overrides this). |
| `timeout`       | HTTP timeout in seconds for hpcGPT Chat requests (default `60`).                          |
| `courses`       | List of course tool entries; each verified course becomes an MCP tool.                    |

Command-line flags exist for host/port/API settings (`--host`, `--port`,
`--url`, etc.); see `python server.py --help`. Course tools are config-file
only. The default config file path is `-c config.json`.

## Run

```bash
python server.py
# or
python server.py -c /path/to/config.json -v
```

On startup the server runs `_verify_course()` for **each** configured
course (a minimal `retrieval_only` request). Courses that fail verification
are logged and skipped. At least one course must verify and register; 
otherwise the process raises and exits. Tool calls also use retrieval-only
mode: hpcGPT Chat returns relevant contexts and the active hpcGPT model 
synthesizes the answer, avoiding a second upstream model generation and
its latency.

- **MCP endpoint:** `http://<host>:<port>/mcp` (FastMCP default
  Streamable HTTP path is `/mcp` unless overridden by FastMCP settings).

Point your MCP client at that URL with Streamable HTTP transport.

## Behavior notes

- Upstream requests use `temperature` **0.3**, `stream: false`, and 
  `retrieval_only: true` for normal tool calls.
- Retrieval contexts are returned as JSON for the active hpcGPT model to
  synthesize. Legacy response shapes (`message`, OpenAI-style `choices[0].message.content`,
  or `response`) remain supported.
- After adding or renaming tools in config, update any agent prompts that
  list specific tool names (for example `hpcgpt.md`) if you want the model
  guided to use the new tools.

## Project layout

```
chat/
├── server.py           # MCP server and dynamic tool registration
├── config.json         # Template for config.json
├── src/
│   ├── config.py       # Pydantic config loading (including courses)
│   └── logging.py      # File logging and FastMCP log routing
└── logs/               # Typical location for log_file (optional)
```

## Troubleshooting

- **Startup fails with “No course tools were verified and registered”:**
  Every course failed verification. Check `url`, API key, model name, and
  that each `courses[].name` exists upstream; confirm HTTP 200 and JSON
  from the hpcGPT Chat API.
- **Course skipped with “Failed to verify course …”:** That course was
  not registered; others may still start the server if at least one 
  succeeds.
- **401 / 403 on verify:** Key rejected by the upstream service.
- **404 on verify:** Wrong path in `url`.
- **No courses configured:** Ensure `courses` is non-empty in `config.json`.

## License

Same as the parent repository (see root `LICENSE`).
