#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

echo "Resetting local Compose volumes..."
docker compose down -v

echo "Starting local PostgreSQL and Redis..."
docker compose up --build -d postgres redis

echo "Applying database migrations..."
docker compose build migrate
docker compose run --rm migrate

echo "Seeding deterministic local demo data..."
docker compose run --rm migrate python -m ghostrecon.demo_seed

cat <<EOF

Local demo reset complete.

Start the local demo stack with:
  make dev

Or validate the full local demo workflow with:
  make demo-check

Gateway:
  http://localhost:${GHOSTRECON_HTTP_PORT:-8080}

Console:
  http://localhost:${GHOSTRECON_CONSOLE_HTTP_PORT:-8082}
EOF
