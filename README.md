<p align="center">
  <img src="favicon.png" alt="hpcGPT" width="640" />
</p>

![Status](https://img.shields.io/badge/status-active-brightgreen)
![Tech](https://img.shields.io/badge/AI-Opencode%20Agent%20%7C%20MCP%20Servers%20%7C%20Slurm%20%7C%20Illinois%20Chat%20%7C%20Atlassian-blueviolet)

hpcGPT is a customized CLI built on top of the `Opencode` agent that integrates Model Context Protocol (MCP) servers for Slurm-based HPC environments, Illinois Chat documentation Q&A, reporting, and Atlassian.

## TL;DR – Getting Started

```bash
curl -fsSL https://opencode.ai/install | bash
export OPENCODE_CONFIG=/absolute/path/to/this/repo/opencode.jsonc
opencode
```

Set environment variables as needed (see Env section below), then pick a model and use tools from the TUI.

## Features

- Slurm integration (MCP): `sinfo`, `squeue`, `scontrol`, and `accounts` via `slurm-mcp-server`.
- Docs Q&A (MCP): Illinois Chat tools `delta-docs`, `delta-ai-docs` for Delta/Delta AI documentation.
- Atlassian integration (MCP): Containerized Jira/Confluence tools with flexible auth modes.
- Support reporting: `report-server` sends concise support reports with context.
- Multiple providers: NCSA Hosted and NCSA Ollama providers selectable in `opencode.jsonc`.
- Config-driven: Everything wired through `opencode.jsonc` for reproducibility.

## System Architecture

```mermaid
graph TD
  U[User] -->|TUI| OC[Opencode Agent]

  OC --> P1[NCSA Hosted Provider]
  OC --> P2[NCSA Ollama Provider]

  subgraph MCP_Servers
    M1[slurm-mcp-server]
    M2[illinois-chat-server]
    M3[report-server]
    M4[atlassian-mcp-server container]
  end

  OC -. tools .-> M1
  OC -. tools .-> M2
  OC -. tools .-> M3
  OC -. tools .-> M4

  M1 --> SLURM[Slurm CLI]
  M2 --> ICHAT[Illinois Chat API]
  M4 --> JIRA[Jira]
  M4 --> CONF[Confluence]
  M3 --> SUPPORT[Delta Support]
```

### How things fit together

- Opencode reads `opencode.jsonc` for providers, models, and MCP servers.
- MCP servers expose tools over stdio; the agent calls them when the model chooses a tool.
- `slurm-mcp-server` shells out to local Slurm commands.
- `illinois-chat-server` calls the Illinois Chat API to answer questions from Delta/Delta AI docs.
- `atlassian-mcp-server` runs via Apptainer and exposes Jira/Confluence tools.
- `report-server` can send a compact support report with session context.

## Project Structure

```
hpcgpt/
  mcp_servers/
    illinois_chat_server/
      src/index.ts
      package.json
    slurm_mcp_server/
      src/index.ts
      package.json
  prompts/
    support.txt
  opencode.jsonc
  example.env
  example.env.atlassian
  README.md
  favicon.png
```

## MCP Servers & Tools

- slurm-mcp (local)
  - Tools: `accounts`, `sinfo`, `squeue`, `scontrol`
  - Purpose: query accounts, node/partition status, user jobs, and job details.

- illinois-chat-mcp (local)
  - Tools: `delta-docs`, `delta-ai-docs`
  - Purpose: answer questions from Delta and Delta AI documentation (requires `ILLINOIS_CHAT_API_KEY`).

- report-server (local)
  - Tools: `send_support_report`
  - Purpose: email a concise support report with conversation history and system info to the Delta support team.

- atlassian-mcp-server (container)
  - Tools (examples): Jira — `jira_get_issue`, `jira_search_issues`, `jira_create_issue`, `jira_add_comment`, `jira_transition_issue`; Confluence — `confluence_search`, `confluence_get_page`, `confluence_create_page`, `confluence_update_page` (availability depends on config/read-only mode).
  - Purpose: interact with Jira and Confluence for tickets and docs. See the Atlassian MCP project for details: `https://github.com/sooperset/mcp-atlassian`

## Installation

Install Opencode and point it at this repo’s config:

```bash
curl -fsSL https://opencode.ai/install | bash
export OPENCODE_CONFIG=/absolute/path/to/this/repo/opencode.jsonc
opencode
```

### Optional: Local MCP server setup

MCP servers in `mcp_servers/*` use Bun/Node. From each server directory:

```bash
bun install
bun run build
bun run start
```

Opencode will also launch them automatically from the `opencode.jsonc` `mcp` section when enabled.

## Environment Configuration

Use `example.env` and `example.env.atlassian` as references. Export directly or create a `.env`/`.env.atlassian`.

### Core variables

- `NCSA_LLM_URL` – Base URL for NCSA Hosted models provider
- `ILLINOIS_CHAT_API_KEY` – Required for `illinois-chat-server`

### Atlassian (containerized MCP)

Configure `.env.atlassian` (see `example.env.atlassian`). Common options:

- `JIRA_URL`, `CONFLUENCE_URL`
- One of: personal token, API token, or OAuth BYOT
- Optional: `READ_ONLY_MODE`, `ENABLED_TOOLS`, proxy settings

## Usage Examples

Inside the Opencode TUI, pick a model (e.g., `ncsahosted/Qwen/Qwen3-VL-32B-Instruct`) and ask the assistant to use tools.

### Slurm status

"Check the Delta GPU partitions and my running jobs."

The assistant will call `sinfo` and `squeue` via `slurm-mcp-server`.

### Delta/Delta AI docs Q&A

"How do I submit a Slurm job on Delta?"

The assistant will call `delta-docs` with your question and return a synthesized answer with citations when available.

### File a support report

Run the `report` command in Opencode. This uses the `send_support_report` tool to email a concise summary to Delta support.

## Configuration Reference

See `opencode.jsonc` for providers, models, and MCP server commands. Example provider entries:

```json
{
  "provider": {
    "ncsahosted": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "my_provider_name",
      "options": {
        "baseURL": "{env:my_url}" // load the url from a environment variable
      },
      "models": {
        "Qwen/Qwen3-VL-32B-Instruct": {
          "name": "my_model_name",
          "options": {
            "stream":true
          }
        }
      }
    }
  }
}
```

## Links

- Delta Chatbot: `https://uiuc.chat/Delta-Documentation` (course: Delta-Documentation)
- Delta AI Chatbot: `https://uiuc.chat/DeltaAI-Documentation` (course: DeltaAI-Documentation)

## License

MIT – see `LICENSE`.

