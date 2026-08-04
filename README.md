<p align="center">
  <img src="favicon.png" alt="hpcGPT" width="640" />
</p>

![Status](https://img.shields.io/badge/status-active-brightgreen)
![Tech](https://img.shields.io/badge/AI-Opencode%20Agent%20%7C%20MCP%20Servers%20%7C%20Slurm%20%7C%20OpenAI-blueviolet)

hpcGPT is a shared CLI foundation built on top of the `Opencode` agent for HPC centers. Each center keeps its own deployment code, configuration, prompts, and integrations in its own top-level directory.

## Current Deployments

- `NCSA/` - NCSA-specific deployment (Delta-focused prototype and tooling)

## TL;DR - Getting Started

```bash
curl -fsSL https://opencode.ai/install | bash
export OPENCODE_CONFIG=/absolute/path/to/this/repo/NCSA/opencode.jsonc
opencode
```

Pick the center deployment you want to run by setting `OPENCODE_CONFIG` to that center's config file.

## Repository Layout

```text
hpcgpt-cli/
  README.md
  LICENSE
  favicon.png
  NCSA/
    README.md
    opencode.jsonc
    example.env
    example.env.atlassian
    prompts/
    mcp_servers/
    doc-scraping/
```

## Contribution Model (Per Center)

When adding support for another university or supercomputing center, create a new top-level directory (for example `CenterName/`) and keep center-specific content scoped there.

### Required in each center folder

- `opencode.jsonc` with that center's providers, models, and MCP wiring
- `prompts/` for center-specific assistant behavior
- `mcp_servers/` for local MCP servers owned by that center
- `example.env` and optional additional env examples (e.g., Atlassian)
- `README.md` describing architecture, tools, setup, and operations

### Guidelines

- Keep secrets out of git; commit only example env files.
- Keep center-specific naming and endpoints inside that center folder.
- Keep root-level docs and files generic and reusable across centers.
- Update this root `README.md` when adding a new center directory.
- Prefer shared patterns, but allow center-specific implementation details.

## Shared Expectations

- Deployments can use OpenAI-compatible providers; exact provider configuration is center-specific.
- MCP server commands and permissions should be documented in each center's `README.md`.
- Operational runbooks, support flows, and escalation contacts belong in each center folder.

## NCSA Deployment

For the current NCSA prototype details, use `NCSA/README.md`.

## License

MIT - see `LICENSE`.
