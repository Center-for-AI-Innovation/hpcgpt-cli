# Client deployment instructions (site install)

These are the instructions for deploying the hpcGPT OpenCode CLI on an HPC cluster so users load it via Environment Modules. The files in this directory are from Delta's deployment and will need tweaks for other systems.

## Directory contents

```text
client-deployment/
  installer.sh       # Site OpenCode installer
  module.lua         # Lmod/Environment Modules template
  opencode.jsonc     # Site config template (providers, MCP, prompts)
  tui.jsonc          # TUI config that loads site interface plugins
  plugins/
    slurm-sidebar/   # Opt-in, no-LLM Slurm status display
    feedback/        # Direct conversation feedback dialog
  prompts/
    support.txt      # Support agent system prompt
    debug.txt        # Debug mode system prompt
    learning.txt     # Learning mode system prompt
    report.txt       # `/report` command template
```

| File | Purpose |
|------|---------|
| `installer.sh` | Fork of the [official OpenCode installer](https://opencode.ai/install) with `--install-dir` and `--no-modify-path` |
| `module.lua` | Lmod template that sets `PATH`, `OPENCODE_CONFIG`, and `NCSA_LLM_URL` |
| `opencode.jsonc` | Site config: provider, models, MCP server URLs, permissions, and prompt references |
| `tui.jsonc` | Site TUI config loaded through `OPENCODE_TUI_CONFIG` |
| `plugins/slurm-sidebar/` | Read-only sidebar that runs local Slurm commands only on user-requested refresh |
| `plugins/feedback/` | No-LLM feedback dialog with an explicitly confirmed conversation attachment |
| `prompts/` | Prompt files referenced by `opencode.jsonc` via `{file:./prompts/...}` |

## Target site layout

Delta uses `/sw/external/` for system software. After deployment, the install root should look like:

```text
/sw/external/opencode/
  bin/opencode
  opencode.json
  tui.jsonc
  plugins/
    slurm-sidebar/
    feedback/
  prompts/
    support.txt
    debug.txt
    learning.txt
    report.txt

/sw/external/modulefiles/hpc-gpt/
  1.15.13.lua
```

The module name (`hpc-gpt`) comes from the modulefile directory name. Adjust paths if your site uses a different convention.

## Site admin setup

### 1. Install the OpenCode binary

Run the installer as a user with permission to write the target directory. Use `--no-modify-path` so shell configs on the admin account are not modified.

```bash
cd client-deployment

bash installer.sh \
  --install-dir /sw/external/opencode/bin \
  --no-modify-path
```

Verify:

```bash
/sw/external/opencode/bin/opencode --version
```

### 2. Deploy site configuration and prompts

Copy the config and prompt files into the install root. Prompt paths in the config are relative to the config file, so keep `prompts/` alongside it.

```bash
mkdir -p /sw/external/opencode/prompts
mkdir -p /sw/external/opencode/plugins

cp opencode.jsonc /sw/external/opencode/opencode.json
cp tui.jsonc /sw/external/opencode/tui.jsonc
cp -R plugins/slurm-sidebar /sw/external/opencode/plugins/
cp -R plugins/feedback /sw/external/opencode/plugins/
cp prompts/support.txt prompts/debug.txt prompts/learning.txt prompts/report.txt /sw/external/opencode/prompts/
```

Edit `/sw/external/opencode/opencode.json` for your site:

- **Provider / models** — model IDs and display names under `provider`
- **`NCSA_LLM_URL`** — set in the modulefile (see below); referenced in config as `{env:NCSA_LLM_URL}`
- **MCP servers** — Enable/Disable the MCP servers that you have deployed. Slurm, Illinois Chat, report, and/or knowledge-base endpoints
- **Modes** — `support` provides Delta guidance and information lookup; `debug` performs hands-on troubleshooting with Delta-safe guardrails; `learning` acts as a TA without implementing the core assignment algorithm

### 3. Install the modulefile

Copy `module.lua` into your modules tree. The filename should match the OpenCode version you installed.

```bash
mkdir -p /sw/external/modulefiles/hpc-gpt
cp module.lua /sw/external/modulefiles/hpc-gpt/1.15.13.lua
```

Update the template for your site:

| Variable | Description |
|----------|-------------|
| `root` | Software root (e.g. `/sw/external/opencode`) |
| `version` | Module version string; should match the installed OpenCode release |
| `OPENCODE_CONFIG` | Path to your site config (e.g. `/sw/external/opencode/delta-opencode.json`) |
| `OPENCODE_TUI_CONFIG` | Path to the site TUI config (e.g. `/sw/external/opencode/tui.jsonc`) |
| `NCSA_LLM_URL` | Base URL for your hosted OpenAI-compatible model endpoint |
| `HPCGPT_FEEDBACK_EMAIL` | Site feedback recipient used by the TUI plugin |
| `HPCGPT_FEEDBACK_FROM` | Authorized sender used by the TUI plugin |

The feedback plugin requires a working system `mail` command on the login nodes.

## End user usage

After the site admin completes the steps above:

```bash
module load hpc-gpt/1.15.13
opencode
```

Loading the module sets `OPENCODE_CONFIG`, `OPENCODE_TUI_CONFIG`, `NCSA_LLM_URL`, `HPCGPT_FEEDBACK_EMAIL`, and `HPCGPT_FEEDBACK_FROM` automatically. Users do not need a personal install or config export.

Run `/jobs` to enable the Slurm sidebar and load status once. Click `[Refresh]` or run `/jobs-refresh` for another update. The sidebar performs no background polling.

Run `/feedback` to select a category, enter a short comment, and explicitly confirm attachment of the full OpenCode session. The importable session export is limited to 5 MiB and may contain reasoning, tool output, and file content. No email is sent until the user confirms. The plugin uses the local `mail` command and the recipient configured by `HPCGPT_FEEDBACK_EMAIL`; it does not invoke the LLM or ticket-reporting MCP server.

Use learning mode when a student wants TA-style explanation, focused questions, mechanical bug diagnosis, or a non-solution source skeleton while retaining ownership of the core algorithm.

Use support mode for questions such as partition choice, job submission guidance, or documentation lookup. Use debug mode when the assistant should inspect files, edit project code or scripts, and run lightweight validation commands.

Debug mode is designed for shared-cluster etiquette: login nodes are for inspection and small checks; GPU tests, benchmarks, training, and long-running work should go through Slurm.

## Upgrading

1. Run `installer.sh` with the new `--version` (or latest if omitted).
2. Update the modulefile version string and filename if you version modules per release.
3. Re-test `opencode` and your site config against the new CLI.
4. Review the [OpenCode release notes](https://github.com/anomalyco/opencode/releases) for breaking config changes.

## Per-user install (development)

> **Warning**
> A locally installed OpenCode version in your home directory can conflict with the site-wide installation and produce errors like this when you try to use `opencode`:
>
> ```
> Error: 4 of 5 requests failed: Unexpected server error. Check server logs for details.
> Affected startup requests: config.providers, provider.list, app.agents, config.get
>     at r0 (/$bunfs/root/chunk-a3x1tf54.js:468:117)
>     at <anonymous> (/$bunfs/root/chunk-a3x1tf54.js:468:5550)
>     at processTicksAndRejections (native:7:39)
> ```
>
> To use the site-wide install, delete any existing OpenCode files in your home directory, specifically at `~/.config/opencode` and `~/.opencode`.

For development, users can install the OpenCode client in their home directory by following the standard [OpenCode install instructions](https://opencode.ai) and pointing to their own config:

```bash
export OPENCODE_CONFIG=/path/to/opencode.jsonc
export OPENCODE_TUI_CONFIG=/path/to/tui.jsonc
export NCSA_LLM_URL=https://your-endpoint/v1
opencode
```

When using a repo checkout, set `OPENCODE_CONFIG` to the absolute path of this directory's `opencode.jsonc`.
