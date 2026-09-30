#!/usr/bin/env bash
# Stop all NCSA MCP Apptainer instances started by start-all.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "${SCRIPT_DIR}/env.sh"

for name in slurm illinois-chat report ticket; do
  instance="${INSTANCE_PREFIX}-${name}"
  if apptainer instance list 2>/dev/null | grep -qE "\\b${instance}\\b"; then
    echo "Stopping ${instance}..."
    apptainer instance stop "${instance}"
  else
    echo "Instance ${instance} not running."
  fi
done

echo "Done."
