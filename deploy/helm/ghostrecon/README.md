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
  --set image.tag=0.1.0
```

Run `make helm-check` to lint and render both bundled and external datastore
configurations without accessing real secrets.

After installation, run the datastore smoke test:

```bash
helm test ghostrecon --namespace ghostrecon --logs
```

The test verifies PostgreSQL access with a non-superuser role and Redis authentication.

## Google Calendar Meeting Handoff

Sprint 11 meeting handoff uses Google Calendar service-account credentials.
Set non-secret defaults in `values.yaml`:

```yaml
env:
  GHOSTRECON_GOOGLE_CALENDAR_ID: primary
  GHOSTRECON_GOOGLE_CALENDAR_SEND_UPDATES: "true"
```

Put the service-account email, escaped private key, and optional delegated
Workspace subject in the encrypted values file under `secretEnv`. Production
deployments should grant the service account direct calendar access or Workspace
domain-wide delegation for the delegated subject.

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
