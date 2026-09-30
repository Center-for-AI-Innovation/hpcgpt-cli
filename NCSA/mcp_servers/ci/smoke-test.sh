#!/usr/bin/env bash
# Container smoke test for NCSA MCP images.
# Expects: IMAGE, SMOKE_ID, SMOKE_PORT
set -euo pipefail

IMAGE="${IMAGE:?IMAGE is required}"
SMOKE_ID="${SMOKE_ID:?SMOKE_ID is required}"
SMOKE_PORT="${SMOKE_PORT:?SMOKE_PORT is required}"
NAME="ncsa-smoke-${SMOKE_ID}-$$"
MOCK_PID=""

cleanup() {
  docker rm -f "${NAME}" >/dev/null 2>&1 || true
  if [[ -n "${MOCK_PID}" ]]; then
    kill "${MOCK_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

wait_for_port() {
  local port="$1"
  local tries=45
  for ((i = 1; i <= tries; i++)); do
    # Any HTTP response (including 4xx/405) means the MCP HTTP server is up.
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "http://127.0.0.1:${port}/mcp" || true)"
    if [[ -n "${code}" && "${code}" != "000" ]]; then
      echo "Port ${port} responded with HTTP ${code}."
      return 0
    fi
    if ! docker ps --format '{{.Names}}' | grep -qx "${NAME}"; then
      echo "Container exited early:" >&2
      docker logs "${NAME}" >&2 || true
      return 1
    fi
    sleep 1
  done
  echo "Timed out waiting for port ${port}" >&2
  docker logs "${NAME}" >&2 || true
  return 1
}

start_illinois_mock() {
  # Minimal JSON HTTP server that satisfies ChatMCP._verify_course
  python3 - <<'PY' &
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        _ = self.rfile.read(length)
        body = json.dumps({"message": "ok", "contexts": ["smoke"]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass

HTTPServer(("0.0.0.0", 18080), H).serve_forever()
PY
  MOCK_PID=$!
  sleep 1
}

case "${SMOKE_ID}" in
  slurm)
    docker run -d --name "${NAME}" -p "${SMOKE_PORT}:8001" \
      -e HOST_IP=0.0.0.0 -e PORT=8001 \
      "${IMAGE}"
    ;;
  illinois_chat)
    start_illinois_mock
    docker run -d --name "${NAME}" -p "${SMOKE_PORT}:8002" \
      --add-host=host.docker.internal:host-gateway \
      -e HOST_IP=0.0.0.0 -e PORT=8002 \
      -e ILLINOIS_CHAT_URL=http://host.docker.internal:18080/ \
      -e ILLINOIS_CHAT_API_KEY=smoke-key \
      -e ILLINOIS_CHAT_MODEL=smoke-model \
      "${IMAGE}"
    ;;
  report)
    docker run -d --name "${NAME}" -p "${SMOKE_PORT}:8003" \
      -e HOST_IP=0.0.0.0 -e PORT=8003 \
      "${IMAGE}"
    ;;
  ticket)
    docker run -d --name "${NAME}" -p "${SMOKE_PORT}:8004" \
      -e HOST_IP=0.0.0.0 -e PORT=8004 \
      -e DATA_FILE=/data/clustered.json \
      "${IMAGE}"
    ;;
  *)
    echo "Unknown SMOKE_ID=${SMOKE_ID}" >&2
    exit 1
    ;;
esac

wait_for_port "${SMOKE_PORT}"
echo "Smoke test passed for ${SMOKE_ID}"
