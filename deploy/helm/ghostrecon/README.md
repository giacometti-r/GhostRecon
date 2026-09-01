# GhostRecon Helm Chart

This chart deploys the GhostRecon microservices and can provision persistent,
single-node PostgreSQL and Redis instances for a self-contained installation.

## Initialization Flow

On the first `helm secrets upgrade --install`:

1. Helm creates the PostgreSQL and Redis StatefulSets, Services, Secrets, and PVC
   templates.
2. The PostgreSQL entrypoint initializes an empty data volume, creates the
   `ghostrecon` database, and creates a non-superuser application role.
3. Redis starts with password authentication and append-only persistence.
4. The post-install migration hook retries until PostgreSQL is reachable and runs
   `alembic upgrade head`.
5. Application workloads receive generated database and Redis URLs from
   `ghostrecon-secrets`.
6. Dedicated Celery worker and scheduler Deployments run background jobs,
   including hourly company watchlist monitoring.

Subsequent upgrades reconcile the same release-owned resources and reuse their
PVCs. Helm will not adopt unrelated objects that happen to use the same names.

## Install

Prepare and encrypt `secrets.sops.yaml` as described in
`SECRETS.md`, then run:

```bash
helm secrets upgrade --install ghostrecon deploy/helm/ghostrecon \
  --namespace ghostrecon \
  --create-namespace \
  --wait \
  --timeout 15m \
  -f deploy/helm/ghostrecon/secrets.sops.yaml \
  --set image.repository=registry.example.com/ghostrecon \
  --set profile=production \
  --set image.digest=sha256:REPLACE_WITH_IMAGE_DIGEST \
  --set postgresql.image.digest=sha256:REPLACE_WITH_POSTGRES_DIGEST \
  --set redis.image.digest=sha256:REPLACE_WITH_REDIS_DIGEST \
  --set emailVerifier.image.digest=sha256:REPLACE_WITH_VERIFIER_DIGEST
```

Run `make helm-check` to lint and render both bundled and external datastore
configurations without accessing real secrets.

After installation, run the datastore smoke test:

```bash
helm test ghostrecon --namespace ghostrecon --logs
```

The test verifies PostgreSQL access with a non-superuser role and Redis authentication.

## Dash Console

Sprint 12 deploys the Python Dash dashboard as `console-service` in the normal
`services` list. It uses the same application image and receives the internal
gateway URL from chart values:

```yaml
env:
  GHOSTRECON_GATEWAY_BASE_URL: http://gateway-service:8080
  GHOSTRECON_CONSOLE_REQUEST_TIMEOUT_SECONDS: "10"
```

Expose `console-service` only through authenticated internal ingress or
port-forwarding. The service keeps `/healthz`, `/readyz`, `/metrics`, `/docs`,
and `/v1/*` routes ahead of the Dash catch-all route.

## Sprint 25b Security Deployment Boundary

The chart renders gateway-only TLS ingress, internal owner/console services, default-deny network policies, distinct service accounts with token automount disabled, and separate read-only key/trust secret mounts for every service, worker queue, and scheduler. Production validation rejects local OIDC, mutable images, public docs, missing TLS, or a non-OIDC authentication backend.

Provision each referenced `ghostrecon-<workload>-identity` Secret before deployment. Private keys must be unique and trust bundles may retain old public keys only during a bounded rotation overlap. Provider credentials are projected only into listed consumers through `secretProjection`.

## Google Calendar Meeting Handoff

Sprint 11 meeting handoff uses Google Calendar service-account credentials.
Set non-secret defaults in `values.yaml`:

```yaml
env:
  GHOSTRECON_GOOGLE_CALENDAR_ID: primary
  GHOSTRECON_GOOGLE_CLIENT_EMAIL: calendar-bot@company.ch
  GHOSTRECON_GOOGLE_CALENDAR_SEND_UPDATES: "true"
  # Optional for Workspace domain-wide delegation:
  GHOSTRECON_GOOGLE_DELEGATED_SUBJECT: calendar-owner@company.ch
```

Put only the escaped private key in the encrypted values file under `secretEnv`.
The service-account email and optional delegated Workspace subject are non-secret
runtime identity values and belong under `env`. Production deployments should grant
the service account direct calendar access or Workspace domain-wide delegation for
the delegated subject.

## Datastore Modes

Bundled mode is enabled by default:

```yaml
postgresql:
  enabled: true
  persistence:
    size: 20Gi
    storageClass: ""

redis:
  enabled: true
  persistence:
    size: 5Gi
    storageClass: ""
```

An empty `storageClass` uses the cluster default StorageClass. Set explicit
classes where production storage policy requires them.

For external services, set `postgresql.enabled=false` or
`redis.enabled=false` and provide the corresponding URL under `secretEnv` in
the encrypted values file.

## Connection URL Examples

Bundled release named `ghostrecon`:

```text
postgresql+asyncpg://ghostrecon:change-this-password@ghostrecon-postgresql:5432/ghostrecon
redis://:change-this-password@ghostrecon-redis:6379/0
```

External services:

```text
postgresql+asyncpg://ghostrecon:change-this-password@postgresql.example.internal:5432/ghostrecon
redis://:change-this-password@redis.example.internal:6379/0
rediss://:change-this-password@redis.example.internal:6380/0?ssl_cert_reqs=required
```

Use `postgresql+asyncpg` for GhostRecon. Use `rediss` and the TLS parameters
required by the Redis provider when connecting over TLS.

## Operational Constraints

- Bundled PostgreSQL and Redis are persistent but single-node. Use managed or
  operator-controlled external services when high availability is required.
- PostgreSQL initialization scripts run only when the PVC is empty. Changing
  credentials in SOPS does not alter passwords inside an existing database.
  Rotate database credentials deliberately with SQL before updating the values.
- Redis password changes are applied when its StatefulSet rolls.
- Review PVC retention and backup policy before uninstalling a production release.
- The migration hook depends on Helm hook execution. GitOps controllers that skip
  hooks need a separate migration job in their deployment workflow.
- NetworkPolicies require a cluster network plugin that enforces the Kubernetes
  NetworkPolicy API.

## Profiles, Preflight, and Immutable Images

Set top-level profile to local, test, staging, or production. Strict profiles require live provider
values, complete owned credentials, identifying user agents, a SHA-256 application digest, and
SHA-256 digests for each enabled bundled PostgreSQL, Redis, and email-verifier image. Image
references render as repository@sha256:digest; latest and tag-only strict releases fail rendering.

The pre-install/pre-upgrade preflight Job runs one redacted configuration container per service and
process before migrations. Workloads consume the shared non-secret ConfigMap but receive only
secret keys listed in secretProjection for their dependency ownership. Run make helm-check for
local, external, immutable-production, and negative renders.
