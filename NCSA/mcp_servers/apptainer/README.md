# Apptainer deployment for NCSA MCP servers

These scripts pull GHCR images to SIF files and run them as Apptainer instances
on ports **8001–8004** (same as Delta OpenCode remotes).

## Prerequisites

- Apptainer / Singularity
- Network access to `ghcr.io` (or pre-copied SIFs)
- For Slurm MCP: host Slurm client binaries + munge socket (see binds below)
- For Illinois Chat / Report: real `config.json` with secrets (or env overrides)

## Quick start

```bash
cd NCSA/mcp_servers
cp .env.example .env   # edit IMAGE_OWNER / IMAGE_TAG / config paths
./apptainer/pull.sh
./apptainer/start-all.sh
./apptainer/stop-all.sh
```

SIF files land in `apptainer/sifs/` (gitignored).

## Slurm binds

`start-all.sh` bind-mounts (overridable via `.env`):

| Host path | Container path |
|-----------|----------------|
| `/usr/bin/sinfo` | `/usr/bin/sinfo` |
| `/usr/bin/squeue` | `/usr/bin/squeue` |
| `/usr/bin/scontrol` | `/usr/bin/scontrol` |
| `/sw/user/scripts/accounts` | `/usr/bin/accounts` |
| `/etc/slurm` | `/etc/slurm` |
| `/var/run/munge` | `/var/run/munge` |
| `/usr/lib64/slurm` | `/usr/lib64/slurm` |
| `/usr/lib64/libslurm.so.44` | `/usr/lib64/libslurm.so.44` |

If Slurm lives under a different prefix on your site, set the corresponding
`SINFO_PATH` / `SLURM_LIB_DIR` / etc. variables in `.env`.

## Instances

| Instance name | Port | SIF |
|---------------|------|-----|
| `ncsa-slurm` | 8001 | `ncsa_slurm_mcp.sif` |
| `ncsa-illinois-chat` | 8002 | `ncsa_illinois_chat_mcp.sif` |
| `ncsa-report` | 8003 | `ncsa_report_mcp.sif` |
| `ncsa-ticket` | 8004 | `ncsa_ticket_mcp.sif` |
