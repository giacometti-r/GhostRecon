#!/bin/sh
set -eu

chart="deploy/helm/ghostrecon"
internal_values="$chart/tests/values-internal.yaml"
external_values="$chart/tests/values-external.yaml"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

helm lint "$chart" -f "$internal_values"
helm lint "$chart" -f "$external_values"
helm template ghostrecon "$chart" -f "$internal_values" >"$tmp_dir/internal.yaml"
helm template ghostrecon "$chart" -f "$external_values" >"$tmp_dir/external.yaml"

grep -q "name: ghostrecon-postgresql" "$tmp_dir/internal.yaml"
grep -q "name: ghostrecon-redis" "$tmp_dir/internal.yaml"
grep -q "volumeClaimTemplates:" "$tmp_dir/internal.yaml"
grep -q "kind: Job" "$tmp_dir/internal.yaml"
grep -q "helm.sh/hook: test" "$tmp_dir/internal.yaml"
grep -q "sleep 5" "$tmp_dir/internal.yaml"
grep -q "postgresql+asyncpg://ghostrecon:template-app-password@ghostrecon-postgresql:5432/ghostrecon" "$tmp_dir/internal.yaml"
grep -q "redis://:template-redis-password@ghostrecon-redis:6379/0" "$tmp_dir/internal.yaml"

if grep -q "# Source: ghostrecon/charts/postgresql/" "$tmp_dir/external.yaml"; then
  echo "external mode unexpectedly rendered PostgreSQL resources" >&2
  exit 1
fi

if grep -q "# Source: ghostrecon/charts/redis/" "$tmp_dir/external.yaml"; then
  echo "external mode unexpectedly rendered Redis resources" >&2
  exit 1
fi

expect_failure() {
  name="$1"
  shift
  if "$@" >"$tmp_dir/$name.stdout" 2>"$tmp_dir/$name.stderr"; then
    echo "expected Helm render to fail: $name" >&2
    exit 1
  fi
}

expect_failure missing-credentials helm template ghostrecon "$chart"
expect_failure conflicting-database-url helm template ghostrecon "$chart" \
  -f "$internal_values" \
  --set-string secretEnv.GHOSTRECON_DATABASE_URL=conflict
expect_failure invalid-database-password helm template ghostrecon "$chart" \
  -f "$internal_values" \
  --set-string postgresql.auth.password=invalid/password
