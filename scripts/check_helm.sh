#!/bin/sh
set -eu

chart="deploy/helm/ghostrecon"
internal_values="$chart/tests/values-internal.yaml"
external_values="$chart/tests/values-external.yaml"
production_values="$chart/tests/values-production.yaml"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

helm lint "$chart" -f "$internal_values"
helm lint "$chart" -f "$external_values"
helm lint "$chart" -f "$production_values"
helm template ghostrecon "$chart" -f "$internal_values" >"$tmp_dir/internal.yaml"
helm template ghostrecon "$chart" -f "$external_values" >"$tmp_dir/external.yaml"
helm template ghostrecon "$chart" -f "$production_values" >"$tmp_dir/production.yaml"

grep -q "name: ghostrecon-postgresql" "$tmp_dir/internal.yaml"
grep -q "name: ghostrecon-redis" "$tmp_dir/internal.yaml"
grep -q "volumeClaimTemplates:" "$tmp_dir/internal.yaml"
grep -q "kind: Job" "$tmp_dir/internal.yaml"
grep -q "helm.sh/hook: test" "$tmp_dir/internal.yaml"
grep -q "sleep 5" "$tmp_dir/internal.yaml"
grep -q "postgresql+asyncpg://ghostrecon:template-app-password@ghostrecon-postgresql:5432/ghostrecon" "$tmp_dir/internal.yaml"
grep -q "redis://:template-redis-password@ghostrecon-redis:6379/0" "$tmp_dir/internal.yaml"


grep -q 'GHOSTRECON_PROFILE: "production"' "$tmp_dir/production.yaml"
grep -q 'name: ghostrecon-preflight' "$tmp_dir/production.yaml"
grep -q 'helm.sh/hook: pre-install,pre-upgrade' "$tmp_dir/production.yaml"
grep -q 'ghostrecon@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' "$tmp_dir/production.yaml"
grep -q 'postgres@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb' "$tmp_dir/production.yaml"
grep -q 'redis@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc' "$tmp_dir/production.yaml"
grep -q 'emailvalidator@sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd' "$tmp_dir/production.yaml"
if grep -q 'secretRef:' "$tmp_dir/production.yaml"; then
  echo "production workloads unexpectedly expose the complete secret" >&2
  exit 1
fi

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
expect_failure invalid-profile helm template ghostrecon "$chart"   -f "$internal_values" --set-string profile=prod
expect_failure mutable-app-image helm template ghostrecon "$chart"   -f "$production_values" --set-string image.digest=
expect_failure mutable-postgres-image helm template ghostrecon "$chart"   -f "$production_values" --set-string postgresql.image.digest=
expect_failure mutable-redis-image helm template ghostrecon "$chart"   -f "$production_values" --set-string redis.image.digest=
expect_failure mutable-verifier-image helm template ghostrecon "$chart"   -f "$production_values" --set-string emailVerifier.image.digest=
expect_failure latest-app-tag helm template ghostrecon "$chart"   -f "$production_values" --set-string image.tag=latest
expect_failure latest-postgres-tag helm template ghostrecon "$chart" -f "$production_values" --set-string postgresql.image.tag=latest
expect_failure latest-redis-tag helm template ghostrecon "$chart" -f "$production_values" --set-string redis.image.tag=latest
expect_failure latest-verifier-tag helm template ghostrecon "$chart" -f "$production_values" --set-string emailVerifier.image.tag=latest
expect_failure fake-geocoder helm template ghostrecon "$chart"   -f "$production_values" --set-string env.GHOSTRECON_GEOCODER_PROVIDER=local_demo
expect_failure fake-news helm template ghostrecon "$chart" -f "$production_values" --set-string env.GHOSTRECON_NEWS_PROVIDER=local_demo
expect_failure fake-crm helm template ghostrecon "$chart" -f "$production_values" --set-string env.GHOSTRECON_CRM_PROVIDER=local_demo
expect_failure disabled-verifier helm template ghostrecon "$chart" -f "$production_values" --set-string env.GHOSTRECON_EMAIL_VERIFIER_PROVIDER=disabled
expect_failure disabled-smtp helm template ghostrecon "$chart" -f "$production_values" --set-string env.GHOSTRECON_SMTP_PROVIDER=disabled
expect_failure disabled-imap helm template ghostrecon "$chart" -f "$production_values" --set-string env.GHOSTRECON_IMAP_PROVIDER=disabled
expect_failure disabled-search helm template ghostrecon "$chart"   -f "$production_values" --set-string env.GHOSTRECON_SEARCH_PROVIDER=disabled
expect_failure fake-calendar helm template ghostrecon "$chart"   -f "$production_values" --set-string env.GHOSTRECON_CALENDAR_PROVIDER=fake
expect_failure placeholder-setting helm template ghostrecon "$chart" -f "$production_values" --set-string env.GHOSTRECON_SMTP_HOST=REPLACE_SMTP_HOST
expect_failure placeholder-secret helm template ghostrecon "$chart"   -f "$production_values" --set-string secretEnv.GHOSTRECON_ATTIO_ACCESS_TOKEN=REPLACE_ME
