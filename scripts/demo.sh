#!/usr/bin/env bash
# Démo Firebreak en une commande : installe les dépendances, lance le
# serveur en mode démo (scénario figé, IA mock, zéro réseau) et ouvre
# le dashboard dans le navigateur.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "→ uv sync"
uv sync

URL="http://localhost:8000"
if curl -sf --max-time 2 "$URL/api/state" >/dev/null 2>&1; then
  echo "→ serveur déjà en ligne sur $URL"
else
  echo "→ démarrage FIREBREAK_DEMO=1 sur $URL"
  uv run env FIREBREAK_DEMO=1 uvicorn firebreak.api:app --port 8000 &
  SRV=$!
  trap 'kill $SRV 2>/dev/null || true' EXIT
  for _ in $(seq 1 40); do
    curl -sf --max-time 1 "$URL/api/state" >/dev/null 2>&1 && break
    sleep 0.25
  done
fi

echo "→ dashboard : $URL/   ·   API : $URL/docs"
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL/" >/dev/null 2>&1 || true
fi

# Si on a lancé le serveur, attendre dessus ; sinon sortir.
if [ -n "${SRV:-}" ]; then
  echo "→ Ctrl+C pour arrêter"
  wait "$SRV"
fi
