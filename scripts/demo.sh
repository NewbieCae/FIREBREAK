#!/usr/bin/env bash
# One-command Firebreak demo: installs the dependencies, starts the
# server in demo mode (fixed scenario, mock AI, no network) and opens
# the final interface in the browser.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "→ uv sync"
uv sync

URL="http://localhost:8000"
if curl -sf --max-time 2 "$URL/api/state" >/dev/null 2>&1; then
  echo "→ server already running on $URL"
else
  echo "→ starting FIREBREAK_DEMO=1 on $URL"
  uv run env FIREBREAK_DEMO=1 uvicorn firebreak.api:app --port 8000 &
  SRV=$!
  trap 'kill $SRV 2>/dev/null || true' EXIT
  for _ in $(seq 1 40); do
    curl -sf --max-time 1 "$URL/api/state" >/dev/null 2>&1 && break
    sleep 0.25
  done
fi

echo "→ interface: $URL/app/   ·   debug: $URL/   ·   API: $URL/docs"
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL/app/" >/dev/null 2>&1 || true
fi

# If we started the server, wait on it; otherwise exit.
if [ -n "${SRV:-}" ]; then
  echo "→ Ctrl+C to stop"
  wait "$SRV"
fi
