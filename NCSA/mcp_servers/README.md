# NCSA MCP Servers

Standalone MCP services used by Delta OpenCode (`delta-opencode.jsonc`):

| Service | Directory | Port | Endpoint |
|---------|-----------|------|----------|
| Slurm | `slurm_server/` | 8001 | `http://<host>:8001/mcp` |
| Illinois Chat | `illinois_chat_server/` | 8002 | `http://<host>:8002/mcp` |
| Report | `report_server/` | 8003 | `http://<host>:8003/mcp` |
| Ticket / knowledge-base | `ticket_server/` | 8004 | `http://<host>:8004/mcp` |

Each server can run from a local venv (`python server.py -c config.json`) or as a
container (Docker / Apptainer).

## Container images

Images are built and pushed to GHCR on every `main` change under `NCSA/mcp_servers/`:

- `ghcr.io/<owner>/ncsa_slurm_mcp`
- `ghcr.io/<owner>/ncsa_illinois_chat_mcp`
- `ghcr.io/<owner>/ncsa_report_mcp`
- `ghcr.io/<owner>/ncsa_ticket_mcp`

Tags: `sha-<shortsha>` on every build, plus `VERSION.txt` (e.g. `v0.1.0`) when that
version tag does not already exist. Bump each server’s `VERSION.txt` to publish a
new named release.

Workflow: [`.github/workflows/ncsa-mcp-docker.yaml`](../../.github/workflows/ncsa-mcp-docker.yaml)
(build → smoke test → push).

## Docker Compose

```bash
cd NCSA/mcp_servers
cp .env.example .env
# Point ILLINOIS_CHAT_CONFIG / REPORT_CONFIG at real configs with secrets.
# Ensure those configs use host 0.0.0.0 and the ports above.
docker compose up -d --build
docker compose ps
docker compose down
```

Defaults bind `config.docker.json` for slurm/report/ticket so the stack can start
without secrets. Illinois Chat and production Report need real credentials.

### Slurm bind mounts

The Slurm image does **not** ship Slurm. Compose bind-mounts host tools (Delta defaults):

- Binaries: `sinfo`, `squeue`, `scontrol`, `accounts`
- Config / auth: `/etc/slurm`, `/var/run/munge`
- Libraries: `/usr/lib64/slurm`, `libslurm.so.44`

Override paths via `.env` (`SINFO_PATH`, `ACCOUNTS_PATH`, `SLURM_LIB_DIR`, …).

### Ticket data

Mount a host directory containing `clustered.json` (or set `TICKET_DATA_DIR`).
The image includes a tiny fixture under `ticket_server/fixtures/` for smoke tests.

## Apptainer

See [apptainer/README.md](apptainer/README.md):

```bash
./apptainer/pull.sh
./apptainer/start-all.sh
./apptainer/stop-all.sh
```

## Per-server layout

Each server directory contains:

- `Dockerfile`, `entrypoint.sh`, `VERSION.txt`
- `config.docker.json` — non-secret defaults for containers (`host: 0.0.0.0`)
- `example.config.json` — template for local/production `config.json` (gitignored)

## Local (non-container) run

```bash
cd slurm_server   # or illinois_chat_server / report_server / ticket_server
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp example.config.json config.json   # edit as needed
python server.py -c config.json
```
