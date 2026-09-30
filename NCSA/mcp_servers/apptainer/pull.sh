#!/usr/bin/env bash
# Pull NCSA MCP Docker images from GHCR into local Apptainer SIF files.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "${SCRIPT_DIR}/env.sh"

mkdir -p "${SIF_DIR}"

pull_one() {
  local name="$1"
  local image="$2"
  local sif="${SIF_DIR}/${name}.sif"
  echo "Pulling ${image} -> ${sif}"
  apptainer pull --force "${sif}" "docker://${image}"
}

pull_one "ncsa_slurm_mcp"          "${IMAGE_REGISTRY}/${IMAGE_OWNER}/ncsa_slurm_mcp:${IMAGE_TAG}"
pull_one "ncsa_illinois_chat_mcp"  "${IMAGE_REGISTRY}/${IMAGE_OWNER}/ncsa_illinois_chat_mcp:${IMAGE_TAG}"
pull_one "ncsa_report_mcp"         "${IMAGE_REGISTRY}/${IMAGE_OWNER}/ncsa_report_mcp:${IMAGE_TAG}"
pull_one "ncsa_ticket_mcp"         "${IMAGE_REGISTRY}/${IMAGE_OWNER}/ncsa_ticket_mcp:${IMAGE_TAG}"

echo "Done. SIFs in ${SIF_DIR}"
