# Secret Handling

GhostRecon uses SOPS with Age for Helm values containing credentials.

## Age Key Location

- Recipient configuration: `deploy/helm/ghostrecon/.sops.yaml`
- Default private-key file: `~/.config/sops/age/keys.txt`
- Alternative key path: `SOPS_AGE_KEY_FILE=/path/to/keys.txt`

Never commit an Age private key or a decrypted values file.

## Bundled Datastores

The default chart provisions PostgreSQL and Redis. Put only their credentials in
`secrets.sops.yaml`:

```yaml
postgresql:
  auth:
    postgresPassword: REPLACE_WITH_URL_SAFE_POSTGRES_ADMIN_PASSWORD
    password: REPLACE_WITH_URL_SAFE_GHOSTRECON_DATABASE_PASSWORD

redis:
  auth:
    password: REPLACE_WITH_URL_SAFE_REDIS_PASSWORD
```

Passwords used in generated URLs must contain only letters, numbers, `.`, `_`,
`~`, or `-`. Generate independent, high-entropy values for all three fields.

For a release named `ghostrecon`, Helm generates URLs with these shapes:

```text
postgresql+asyncpg://ghostrecon:DATABASE_PASSWORD@ghostrecon-postgresql:5432/ghostrecon
redis://:REDIS_PASSWORD@ghostrecon-redis:6379/0
```

The PostgreSQL administrator password is mounted only into PostgreSQL. Application
pods receive the non-superuser database URL.

## External Datastores

Disable either bundled datastore when using an existing managed service and supply
its complete URL through the encrypted values file:

```yaml
postgresql:
  enabled: false

redis:
  enabled: false

secretEnv:
  GHOSTRECON_DATABASE_URL: postgresql+asyncpg://ghostrecon:URL_SAFE_PASSWORD@postgresql.example.internal:5432/ghostrecon
  GHOSTRECON_REDIS_URL: rediss://:URL_SAFE_PASSWORD@redis.example.internal:6380/0?ssl_cert_reqs=required
```

External PostgreSQL and Redis instances must already exist. Helm does not create,
discover, or adopt infrastructure addressed by an external URL.

## Google Calendar

Meeting handoff uses Google Calendar service-account credentials. Keep the
private key encrypted in `secretEnv`:

```yaml
secretEnv:
  GHOSTRECON_GOOGLE_CLIENT_EMAIL: calendar-bot@example.iam.gserviceaccount.com
  GHOSTRECON_GOOGLE_PRIVATE_KEY: "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
  GHOSTRECON_GOOGLE_DELEGATED_SUBJECT: calendar-owner@example.com
```

`GHOSTRECON_GOOGLE_DELEGATED_SUBJECT` is optional when the service account has
direct calendar access. For Workspace domain-wide delegation, set it to the user
whose calendar should own the events.

## Encrypt And Deploy

1. Edit the encrypted file safely:

   ```bash
   sops deploy/helm/ghostrecon/secrets.sops.yaml
   ```

   For the initial plaintext placeholder, populate it and encrypt in place:

   ```bash
   sops -e -i deploy/helm/ghostrecon/secrets.sops.yaml
   ```

2. Validate the chart using committed non-secret fixtures:

   ```bash
   make helm-check
   ```

3. Render with decryption:

   ```bash
   helm secrets template ghostrecon deploy/helm/ghostrecon \
     -f deploy/helm/ghostrecon/secrets.sops.yaml
   ```

4. Install or upgrade:

   ```bash
   helm secrets upgrade --install ghostrecon deploy/helm/ghostrecon \
     --namespace ghostrecon \
     --create-namespace \
     --wait \
     --timeout 15m \
     -f deploy/helm/ghostrecon/secrets.sops.yaml
   ```

Do not redirect decrypted Helm output to a tracked file. Helm stores rendered
Kubernetes Secrets in release metadata, so cluster access to Helm release Secrets
must be restricted with RBAC.
