#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

GATEWAY_URL="http://localhost:${GHOSTRECON_HTTP_PORT:-8080}"
CONSOLE_URL="http://localhost:${GHOSTRECON_CONSOLE_HTTP_PORT:-8082}"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

pass() {
  echo "OK: $*"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"
}

container_id() {
  docker compose ps -q "$1" 2>/dev/null || true
}

require_running_container() {
  service="$1"
  id=$(container_id "$service")
  [ -n "$id" ] || fail "Compose service is not created: $service"
  running=$(docker inspect -f '{{.State.Running}}' "$id")
  [ "$running" = "true" ] || fail "Compose service is not running: $service"
  health=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$id")
  case "$health" in
    healthy|none) pass "container $service is running ($health)" ;;
    *) fail "Compose service is not healthy: $service ($health)" ;;
  esac
}

http_get() {
  label="$1"
  url="$2"
  tmp=$(mktemp)
  code=$(curl -fsS -o "$tmp" -w '%{http_code}' "$url" 2>/tmp/ghostrecon-demo-check-curl.err || true)
  if [ "$code" != "200" ]; then
    body=$(cat "$tmp" 2>/dev/null || true)
    err=$(cat /tmp/ghostrecon-demo-check-curl.err 2>/dev/null || true)
    rm -f "$tmp" /tmp/ghostrecon-demo-check-curl.err
    fail "$label returned HTTP ${code:-000}: ${body:-$err}"
  fi
  rm -f "$tmp" /tmp/ghostrecon-demo-check-curl.err
  pass "$label"
}

wait_for_http() {
  label="$1"
  url="$2"
  attempt=1
  while [ "$attempt" -le 30 ]; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      pass "$label"
      return 0
    fi
    attempt=$((attempt + 1))
    sleep 2
  done
  fail "$label did not become ready at $url"
}

require_command docker
require_command curl

for service in postgres redis gateway-service console-service worker email-verifier; do
  require_running_container "$service"
done

pass "required Compose containers are running"

postgres_id=$(container_id postgres)
redis_id=$(container_id redis)

docker exec "$postgres_id" psql -U ghostrecon -d ghostrecon -tAc \
  "select version_num from alembic_version limit 1" >/dev/null \
  || fail "PostgreSQL alembic_version check failed"
pass "PostgreSQL alembic_version exists"

expected_tables="source_definitions cyber_events security_incidents watch_targets review_candidates crm_targets"
for table_name in $expected_tables; do
  exists=$(docker exec "$postgres_id" psql -U ghostrecon -d ghostrecon -tAc \
    "select to_regclass('public.$table_name') is not null")
  [ "$exists" = "t" ] || fail "PostgreSQL missing table: $table_name"
done
pass "PostgreSQL representative schema tables exist"

for table_name in $expected_tables; do
  count=$(docker exec "$postgres_id" psql -U ghostrecon -d ghostrecon -tAc \
    "select count(*) from $table_name")
  [ "$count" -ge 1 ] || fail "PostgreSQL demo seed missing rows in $table_name"
done
pass "PostgreSQL deterministic demo seed rows exist"

redis_ping=$(docker exec "$redis_id" redis-cli ping)
[ "$redis_ping" = "PONG" ] || fail "Redis ping failed: $redis_ping"
pass "Redis ping"

wait_for_http "gateway health endpoint is reachable" "$GATEWAY_URL/healthz"
http_get "gateway readiness" "$GATEWAY_URL/readyz"
http_get "gateway KPI catalog" "$GATEWAY_URL/v1/reporting/kpis/catalog"
http_get "gateway reporting events" "$GATEWAY_URL/v1/reporting/events"
http_get "gateway reporting incidents" "$GATEWAY_URL/v1/reporting/incidents"
http_get "gateway reporting watch targets" "$GATEWAY_URL/v1/reporting/watch-targets"
http_get "gateway reporting review queue" "$GATEWAY_URL/v1/reporting/review-queue"
http_get "gateway reporting CRM targets" "$GATEWAY_URL/v1/reporting/crm-targets"
http_get "gateway reporting source health" "$GATEWAY_URL/v1/reporting/source-health"

wait_for_http "console health endpoint is reachable" "$CONSOLE_URL/healthz"
http_get "console readiness" "$CONSOLE_URL/readyz"
http_get "console root" "$CONSOLE_URL/"
http_get "Dash callback dependency metadata" "$CONSOLE_URL/_dash-dependencies"

cat <<EOF

Local demo check passed.

Gateway: $GATEWAY_URL
Console: $CONSOLE_URL
EOF
