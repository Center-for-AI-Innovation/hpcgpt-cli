#!/bin/bash
set -euo pipefail

ARGS=(-c "${CONFIG_FILE:-config.json}" --host "${HOST_IP:-0.0.0.0}" --port "${PORT:-8003}")

if [[ -n "${LOG_FILE:-}" ]]; then
  ARGS+=(--log-file "${LOG_FILE}")
fi
if [[ "${VERBOSE:-0}" == "1" ]]; then
  ARGS+=(-v)
fi

exec python server.py "${ARGS[@]}"
