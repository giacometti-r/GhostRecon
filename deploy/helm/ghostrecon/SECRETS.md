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

Meeting handoff uses Google Calendar service-account credentials. Put the
non-secret service-account identity under `env`:

```yaml
env:
  GHOSTRECON_GOOGLE_CLIENT_EMAIL: calendar-bot@example.iam.gserviceaccount.com
  # Optional for Workspace domain-wide delegation:
  GHOSTRECON_GOOGLE_DELEGATED_SUBJECT: calendar-owner@example.com
```

Keep only the private key encrypted in `secretEnv`:

```yaml
secretEnv:
  GHOSTRECON_GOOGLE_PRIVATE_KEY: "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
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

## Provider Credential Ownership

Store provider tokens, passwords, private keys, and credential-bearing database/Redis URLs only in
secretEnv or generated datastore secrets. Strict profiles require Attio and SerpAPI tokens, Google
RSA private key, SMTP password, and IMAP password. Non-secret provider endpoints, service-account
email, calendar ID, protocol hosts/usernames, sender address, and identifying user agents belong in
env.

The chart projects secret keys per workload rather than using a global Secret envFrom. Update
secretProjection and the Python service dependency registry together whenever a process begins to
own a provider. Values beginning REPLACE_ or REPLACE- are rejected in strict profiles. Preflight
output never includes secret values.
