<p align="center">
  <img src="favicon.png" alt="hpcGPT" width="640" />
</p>

![Status](https://img.shields.io/badge/status-active-brightgreen)
![Tech](https://img.shields.io/badge/AI-Opencode%20Agent%20%7C%20MCP%20Servers%20%7C%20Slurm%20%7C%20OpenAI-blueviolet)

hpcGPT is a shared CLI foundation built on top of the [OpenCode](https://opencode.ai) agent for HPC centers. Each center keeps its own deployment code, configuration, prompts, MCP servers, and site-install artifacts in its own top-level directory.

## Current Deployments

- [`NCSA/`](NCSA/) — NCSA deployment for Delta (support assistant, MCP servers, site module install)
- [`OSC/`](OSC/) - OSC-specific deployment

## TL;DR - Getting Started

**On a deployed cluster (end users):**

```bash
module load hpc-gpt/1.15.13
opencode
```

**Local development:**

```bash
curl -fsSL https://opencode.ai/install | bash
export OPENCODE_CONFIG=/absolute/path/to/this/repo/NCSA/client-deployment/opencode.jsonc
export NCSA_LLM_URL=https://your-endpoint/v1
opencode
```

Pick the center deployment you want to run by setting `OPENCODE_CONFIG` to that center's config file. See the center's README for environment variables, MCP setup, and site-admin instructions.

## Repository Layout

```text
hpcgpt-cli/
  README.md
  LICENSE
  favicon.png
  NCSA/
    README.md
    client-deployment/     # Site install: installer, modulefile, config, prompts
    mcp_servers/           # Slurm, Illinois Chat, report, ticket knowledge-base MCP servers
    ticket-ingest/         # Support ticket → Q&A dataset pipeline
    doc-scraping/
    example.env
  OSC/
    README.md
    client-deployment/     # Site install: installer, modulefile, config, prompts
    example.env
    prompts/
    mcp_servers/
```

## Contribution Model (Per Center)

When adding support for another university or supercomputing center, create a new top-level directory (for example `CenterName/`) and keep center-specific content scoped there.

### Required in each center folder

- `README.md` describing architecture, tools, setup, and operations
- `client-deployment/` (or equivalent) with site-install artifacts: config, prompts, installer, and modulefile templates
- `mcp_servers/` for MCP servers owned by that center
- `example.env` and optional additional env examples
- OpenCode config (`opencode.jsonc`) with that center's providers, agents, models, and MCP wiring

### Guidelines

- Keep secrets out of git; commit only example env files.
- Keep center-specific naming and endpoints inside that center folder.
- Keep root-level docs and files generic and reusable across centers.
- Update this root `README.md` when adding a new center directory.
- Prefer shared patterns, but allow center-specific implementation details.

## Shared Expectations

- Deployments can use OpenAI-compatible providers; exact provider configuration is center-specific.
- MCP servers and permissions should be documented in each center's `README.md`.
- Site-admin install runbooks belong in each center's `client-deployment/` (or equivalent) directory.
- Operational runbooks, support flows, and escalation contacts belong in each center folder.

## NCSA Deployment

For architecture, MCP servers, development setup, and Delta site-admin instructions, see [`NCSA/README.md`](NCSA/README.md).

Site-admin install steps: [`NCSA/client-deployment/README.md`](NCSA/client-deployment/README.md).

## License

MIT — see [`LICENSE`](LICENSE).
