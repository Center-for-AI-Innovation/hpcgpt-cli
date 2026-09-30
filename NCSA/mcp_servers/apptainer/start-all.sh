#!/usr/bin/env bash
# Start all NCSA MCP servers as Apptainer instances on ports 8001–8004.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "${SCRIPT_DIR}/env.sh"

require_sif() {
  local sif="$1"
  if [[ ! -f "${sif}" ]]; then
    echo "Missing ${sif}. Run ${SCRIPT_DIR}/pull.sh first." >&2
    exit 1
  fi
}

start_instance() {
  local name="$1"
  shift
  local instance="${INSTANCE_PREFIX}-${name}"

  if apptainer instance list 2>/dev/null | grep -qE "\\b${instance}\\b"; then
    echo "Instance ${instance} already running; skipping."
    return 0
  fi

  echo "Starting ${instance}..."
  apptainer instance start "$@" "${instance}"
}

SLURM_SIF="${SIF_DIR}/ncsa_slurm_mcp.sif"
CHAT_SIF="${SIF_DIR}/ncsa_illinois_chat_mcp.sif"
REPORT_SIF="${SIF_DIR}/ncsa_report_mcp.sif"
TICKET_SIF="${SIF_DIR}/ncsa_ticket_mcp.sif"

require_sif "${SLURM_SIF}"
require_sif "${CHAT_SIF}"
require_sif "${REPORT_SIF}"
require_sif "${TICKET_SIF}"

# shellcheck disable=SC2086
start_instance slurm \
  --env "HOST_IP=0.0.0.0" --env "PORT=8001" --env "CONFIG_FILE=/app/config.json" \
  --env "LD_LIBRARY_PATH=/usr/lib64/slurm:/usr/lib64" \
  -B "${SLURM_CONFIG}:/app/config.json:ro" \
  -B "${SINFO_PATH}:/usr/bin/sinfo:ro" \
  -B "${SQUEUE_PATH}:/usr/bin/squeue:ro" \
  -B "${SCONTROL_PATH}:/usr/bin/scontrol:ro" \
  -B "${ACCOUNTS_PATH}:/usr/bin/accounts:ro" \
  -B "${SLURM_CONF_DIR}:/etc/slurm:ro" \
  -B "${MUNGE_RUN_DIR}:/var/run/munge:ro" \
  -B "${SLURM_LIB_DIR}:/usr/lib64/slurm:ro" \
  -B "${LIBSLURM_SO}:/usr/lib64/libslurm.so.44:ro" \
  --network-args "portmap=8001:8001/tcp" \
  "${SLURM_SIF}"

CHAT_ENV=(--env "HOST_IP=0.0.0.0" --env "PORT=8002" --env "CONFIG_FILE=/app/config.json")
if [[ -n "${ILLINOIS_CHAT_URL:-}" ]]; then
  CHAT_ENV+=(--env "ILLINOIS_CHAT_URL=${ILLINOIS_CHAT_URL}")
fi
if [[ -n "${ILLINOIS_CHAT_API_KEY:-}" ]]; then
  CHAT_ENV+=(--env "ILLINOIS_CHAT_API_KEY=${ILLINOIS_CHAT_API_KEY}")
fi
if [[ -n "${ILLINOIS_CHAT_MODEL:-}" ]]; then
  CHAT_ENV+=(--env "ILLINOIS_CHAT_MODEL=${ILLINOIS_CHAT_MODEL}")
fi

# shellcheck disable=SC2086
start_instance illinois-chat \
  "${CHAT_ENV[@]}" \
  -B "${ILLINOIS_CHAT_CONFIG}:/app/config.json:ro" \
  --network-args "portmap=8002:8002/tcp" \
  "${CHAT_SIF}"

# shellcheck disable=SC2086
start_instance report \
  --env "HOST_IP=0.0.0.0" --env "PORT=8003" --env "CONFIG_FILE=/app/config.json" \
  -B "${REPORT_CONFIG}:/app/config.json:ro" \
  --network-args "portmap=8003:8003/tcp" \
  "${REPORT_SIF}"

# shellcheck disable=SC2086
start_instance ticket \
  --env "HOST_IP=0.0.0.0" --env "PORT=8004" --env "CONFIG_FILE=/app/config.json" \
  --env "DATA_FILE=/data/clustered.json" \
  -B "${TICKET_CONFIG}:/app/config.json:ro" \
  -B "${TICKET_DATA_DIR}:/data:ro" \
  --network-args "portmap=8004:8004/tcp" \
  "${TICKET_SIF}"

echo "All NCSA MCP instances requested."
apptainer instance list
echo "Endpoints:"
echo "  slurm:         http://127.0.0.1:8001/mcp"
echo "  illinois-chat: http://127.0.0.1:8002/mcp"
echo "  report:        http://127.0.0.1:8003/mcp"
echo "  ticket:        http://127.0.0.1:8004/mcp"
