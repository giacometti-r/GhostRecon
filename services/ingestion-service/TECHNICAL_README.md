# ingestion-service Technical README

## Responsibilities

- Verify Attio HMAC signatures.
- Capture idempotency keys.
- Store raw payloads and processing status.
- Publish normalized events such as `account.ingested`, `contact.discovered`, and `crm.synced`.

## Interfaces

- `POST /webhooks/attio`

## Reliability

- Attio delivers at least once, so duplicate delivery is expected.
- The API path must return within provider timeout budgets.
- Processing happens in workers so external delivery is decoupled from internal workload.

## Failure Modes

- Invalid signature: return `401` and do not store as trusted input.
- Duplicate event: return success after recognizing the idempotency key.
- Worker failure: retain raw event and mark for replay.

## Testing

- Valid and invalid HMAC tests.
- Duplicate webhook tests.
- Timeout and retry behavior tests.
