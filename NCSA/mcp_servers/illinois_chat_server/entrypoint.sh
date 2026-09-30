#!/bin/bash
set -euo pipefail

ARGS=(-c "${CONFIG_FILE:-config.json}" --host "${HOST_IP:-0.0.0.0}" --port "${PORT:-8002}")

if [[ -n "${ILLINOIS_CHAT_URL:-}" ]]; then
  ARGS+=(--illinois-chat-url "${ILLINOIS_CHAT_URL}")
fi
if [[ -n "${ILLINOIS_CHAT_API_KEY:-}" ]]; then
  ARGS+=(--illinois-chat-api-key "${ILLINOIS_CHAT_API_KEY}")
fi
if [[ -n "${ILLINOIS_CHAT_MODEL:-}" ]]; then
  ARGS+=(--illinois-chat-model "${ILLINOIS_CHAT_MODEL}")
fi
if [[ -n "${LOG_FILE:-}" ]]; then
  ARGS+=(--log-file "${LOG_FILE}")
fi
if [[ "${VERBOSE:-0}" == "1" ]]; then
  ARGS+=(-v)
fi

exec python server.py "${ARGS[@]}"
