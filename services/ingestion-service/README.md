# ingestion-service

## Purpose

`ingestion-service` receives Attio webhooks, imports, and future inbound events. It validates authenticity, stores raw payloads, applies idempotency, and hands work to queues quickly so webhook providers receive timely acknowledgements.

## Runtime

- Entrypoint: `uvicorn ghostrecon.service_apps.runtime:app --host 0.0.0.0 --port 8080`
- Required env: `GHOSTRECON_SERVICE_NAME=ingestion-service`
- Required production secret: `GHOSTRECON_ATTIO_WEBHOOK_SECRET`

## Dependencies

- PostgreSQL for raw event and idempotency storage.
- Redis/Celery for async processing.
- Attio webhook delivery.

## Operations

- ACK valid webhooks quickly.
- Reject invalid signatures.
- Monitor duplicate rate, signature failures, queue depth, and webhook processing lag.

## Local Run

```bash
GHOSTRECON_SERVICE_NAME=ingestion-service uvicorn ghostrecon.service_apps.runtime:app --reload
```
