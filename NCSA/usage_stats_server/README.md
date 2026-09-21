# Usage Stats Server

Ingests session launch and duration reports from the `hpc-gpt` wrapper and stores them in SQLite.

On Delta this service runs on `dt-hpcgpt` port **8005**. Other sites can bind wherever they prefer; clients discover it via the `HPCGPT_USAGE_URL` module environment variable.

## Setup

```bash
cd NCSA/usage_stats_server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp example.config.json config.json
# edit config.json as needed
python server.py
```

Or override listen settings on the command line:

```bash
python server.py --host 0.0.0.0 --port 8005 --db-path /path/to/usage.db
```

## Configuration

| Field | Description | Default |
|-------|-------------|---------|
| `host` | Listen address | `0.0.0.0` |
| `port` | Listen port | `8005` |
| `db_path` | SQLite file for session records | `data/usage.db` |
| `log_level` | Logging level | `INFO` |

Trusted campus network is assumed (no auth), matching the MCP servers on ports 8001–8004.

## API

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness check |
| `POST` | `/v1/sessions` | Ingest one session record |
| `GET` | `/v1/sessions` | List recent sessions (`username`, `limit` query params) |
| `GET` | `/v1/stats` | Summary: total sessions, unique users, total/avg duration |

### Ingest payload (`POST /v1/sessions`)

```json
{
  "session_id": "uuid",
  "username": "user",
  "hostname": "dt-login01",
  "started_at": "2026-09-21T15:00:00Z",
  "ended_at": "2026-09-21T15:05:00Z",
  "duration_sec": 300,
  "exit_code": 0
}
```

## Client wiring

The site Lmod module sets:

```bash
export HPCGPT_USAGE_URL=http://dt-hpcgpt:8005
```

The `hpc-gpt` wrapper POSTs to `${HPCGPT_USAGE_URL}/v1/sessions` after each session. Telemetry is best-effort and does not affect the user session if the server is unreachable.

## Plotting usage

`plot_usage_stats.py` reads the SQLite database and writes the same style of pie charts as the cron CSV analyzer (`unique_opens.png`, `time_used.png`):

```bash
# from NCSA/usage_stats_server with deps installed
python plot_usage_stats.py
python plot_usage_stats.py --db-path data/usage.db -s 2026-09-01 -e 2026-09-30 -n 10
python plot_usage_stats.py -o unique_opens.png --time-output time_used.png
```

| Flag | Purpose | Default |
|------|---------|---------|
| `--db-path` | SQLite path (else taken from `config.json`) | `data/usage.db` |
| `-o` / `--output` | Unique-opens pie chart path | `unique_opens.png` |
| `--time-output` | Time-used pie chart path | `time_used.png` |
| `-s` / `--starttime` | Include sessions starting on/after | 1 month ago |
| `-e` / `--endtime` | Include sessions starting on/before | now |
| `-n` / `--top-n` | Top users shown individually; rest → `other` | `10` |

Unique opens count one launch per stored session. Time used sums `duration_sec` per user and plots whole minutes.
