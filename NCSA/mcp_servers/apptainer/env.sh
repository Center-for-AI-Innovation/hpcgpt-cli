#!/usr/bin/env bash
# Shared Apptainer environment for NCSA MCP servers.
# Override any variable by exporting it before calling scripts, or by
# placing a .env file next to docker-compose (sourced if present).

APPTAINER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_ROOT="$(cd "${APPTAINER_DIR}/.." && pwd)"

if [[ -f "${MCP_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${MCP_ROOT}/.env"
  set +a
fi

IMAGE_REGISTRY="${IMAGE_REGISTRY:-ghcr.io}"
IMAGE_OWNER="${IMAGE_OWNER:-ncsa}"
IMAGE_TAG="${IMAGE_TAG:-v0.1.0}"

SIF_DIR="${SIF_DIR:-${APPTAINER_DIR}/sifs}"
INSTANCE_PREFIX="${INSTANCE_PREFIX:-ncsa}"

SINFO_PATH="${SINFO_PATH:-/usr/bin/sinfo}"
SQUEUE_PATH="${SQUEUE_PATH:-/usr/bin/squeue}"
SCONTROL_PATH="${SCONTROL_PATH:-/usr/bin/scontrol}"
ACCOUNTS_PATH="${ACCOUNTS_PATH:-/sw/user/scripts/accounts}"
SLURM_CONF_DIR="${SLURM_CONF_DIR:-/etc/slurm}"
MUNGE_RUN_DIR="${MUNGE_RUN_DIR:-/var/run/munge}"
SLURM_LIB_DIR="${SLURM_LIB_DIR:-/usr/lib64/slurm}"
LIBSLURM_SO="${LIBSLURM_SO:-/usr/lib64/libslurm.so.44}"

SLURM_CONFIG="${SLURM_CONFIG:-${MCP_ROOT}/slurm_server/config.docker.json}"
ILLINOIS_CHAT_CONFIG="${ILLINOIS_CHAT_CONFIG:-${MCP_ROOT}/illinois_chat_server/config.docker.json}"
REPORT_CONFIG="${REPORT_CONFIG:-${MCP_ROOT}/report_server/config.docker.json}"
TICKET_CONFIG="${TICKET_CONFIG:-${MCP_ROOT}/ticket_server/config.docker.json}"
TICKET_DATA_DIR="${TICKET_DATA_DIR:-${MCP_ROOT}/ticket_server/fixtures}"

# Host network keeps OpenCode URLs (http://dt-hpcgpt:800N/mcp) working without port maps.
APPTAINER_NETWORK_ARGS="${APPTAINER_NETWORK_ARGS:---net --network-args portmap=8001:8001/tcp --network-args portmap=8002:8002/tcp --network-args portmap=8003:8003/tcp --network-args portmap=8004:8004/tcp}"
