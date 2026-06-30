#!/usr/bin/env bash
# Bootstrap + start the full local stack.
# Usage: ./infra/scripts/start.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f .env ]; then
  echo "→ No .env found, creating one from .env.example"
  cp .env.example .env
fi

echo "→ Building and starting containers..."
docker compose up --build -d

echo "→ Waiting for backend health endpoint..."
for i in $(seq 1 30); do
  if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    echo "✓ Backend healthy at http://localhost:8000"
    echo "✓ API docs at        http://localhost:8000/docs"
    exit 0
  fi
  sleep 2
done

echo "✗ Backend did not become healthy in time. Check: docker compose logs backend"
exit 1
