from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from celery import Task
from redis import Redis

from ghostrecon.common.config import Settings

from .context import current_identity, current_operation
from .identity import AssuranceLevel, IdentityContext, IdentityType
from .jwt import TokenValidationError, sign_eddsa, verify_eddsa
from .workload import FileCredentialProvider

TASK_HEADER = "ghostrecon-task-authorization"
TASK_JWT_PURPOSE = "ghostrecon-task+jwt"

TASK_QUEUES = {
    "ghostrecon.fetch_source": "source-fetch",
    "ghostrecon.fetch_event_source": "source-fetch",
    "ghostrecon.fetch_incident_source": "source-fetch",
    "ghostrecon.parse_pending_event_items": "event-parser",
    "ghostrecon.parse_pending_incident_items": "incident-parser",
    "ghostrecon.monitor_watch_targets": "watch-monitor",
    "ghostrecon.crawl_company_domain": "enrichment",
    "ghostrecon.resolve_entity": "enrichment",
    "ghostrecon.enrich_contact_candidate": "enrichment",
    "ghostrecon.generate_email_candidates": "email-intelligence",
    "ghostrecon.persist_email_candidates": "email-intelligence",
    "ghostrecon.verify_email_candidates_batch": "email-intelligence",
    "ghostrecon.evaluate_suppression": "governance",
    "ghostrecon.process_crm_export_batch": "crm-export",
    "ghostrecon.process_due_sequence_steps": "sequencing",
    "ghostrecon.poll_sequence_inbound_email": "sequencing",
    "ghostrecon.process_due_sequence_email_alerts": "sequencing",
    "ghostrecon.retry_meeting_crm_sync": "meeting-sync",
}


def canonical_argument_digest(args: Any, kwargs: Any) -> str:
    encoded = json.dumps(
        {"args": args, "kwargs": kwargs},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def signed_task_headers(
    settings: Settings,
    *,
    task_name: str,
    args: Any,
    kwargs: Any,
    queue: str,
    correlation_id: str,
    causation_id: str,
) -> dict[str, str]:
    expected_queue = TASK_QUEUES.get(task_name)
    if expected_queue != queue:
        raise ValueError("task queue does not match the operation registry")
    if not settings.service_identity or not settings.service_private_key_id:
        raise RuntimeError("task publisher identity is not configured")
    now = datetime.now(UTC)
    issuer = f"urn:ghostrecon:{settings.profile.value}:workload:{settings.service_identity}"
    claims = {
        "iss": issuer,
        "sub": issuer,
        "aud": f"urn:ghostrecon:{settings.profile.value}:worker:{queue}",
        "task": task_name,
        "args_digest": canonical_argument_digest(args, kwargs),
        "queue": queue,
        "correlation_id": correlation_id,
        "causation_id": causation_id,
        "iat": int(now.timestamp()),
        "nbf": int((now - timedelta(seconds=1)).timestamp()),
        "exp": int((now + timedelta(seconds=45)).timestamp()),
        "jti": secrets.token_urlsafe(24),
    }
    token = sign_eddsa(
        claims,
        FileCredentialProvider(settings).private_key(),
        kid=settings.service_private_key_id,
        token_type=TASK_JWT_PURPOSE,
    )
    return {TASK_HEADER: token}


class SignedTask(Task):
    """Reject untrusted Celery delivery before task business code starts."""

    abstract = True
    security_settings: Settings | None = None

    def before_start(self, task_id: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        settings = self.security_settings
        if settings is None or not settings.strict_runtime:
            return
        headers = self.request.headers or {}
        token = headers.get(TASK_HEADER)
        if not isinstance(token, str):
            raise TokenValidationError("unsigned task")
        queue = TASK_QUEUES.get(self.name)
        if queue is None:
            raise TokenValidationError("unclassified task")
        bundle = FileCredentialProvider(settings).trust_bundle()
        verified = None
        for trusted in bundle.values():
            try:
                verified = verify_eddsa(
                    token,
                    trusted.public_keys,
                    expected_type=TASK_JWT_PURPOSE,
                    issuer=trusted.issuer,
                    audience=f"urn:ghostrecon:{settings.profile.value}:worker:{queue}",
                    maximum_lifetime_seconds=45,
                )
                break
            except TokenValidationError:
                continue
        if verified is None:
            raise TokenValidationError("untrusted task publisher")
        claims = verified.claims
        if (
            claims.get("task") != self.name
            or claims.get("queue") != queue
            or claims.get("args_digest") != canonical_argument_digest(args, kwargs)
        ):
            raise TokenValidationError("altered task delivery")
        replay = Redis.from_url(str(settings.redis_url), decode_responses=True)
        ttl = max(1, int(claims["exp"]) - int(datetime.now(UTC).timestamp()))
        if not replay.set(f"ghostrecon:task-replay:{claims['jti']}", "1", nx=True, ex=ttl):
            raise TokenValidationError("replayed task")
        now = datetime.now(UTC)
        identity = IdentityContext(
            identity_type=IdentityType.WORKER,
            subject=str(claims["sub"]),
            actor_label=queue,
            issuer=str(claims["iss"]),
            audience=(str(claims["aud"]),),
            roles=frozenset(),
            permissions=frozenset({"workload.execute"}),
            calling_service=settings.service_identity,
            on_behalf_of_subject=None,
            authentication_method="signed_celery_task",
            authenticated_at=now,
            assurance=AssuranceLevel.WORKLOAD,
            session_id=None,
            correlation_id=str(claims["correlation_id"]),
            request_id=task_id,
            claim_mapping_version="workload.v1",
            permission_policy_version="sprint25b.v1",
            environment=settings.profile.value,
        )
        self.request.ghostrecon_identity_token = current_identity.set(identity)
        self.request.ghostrecon_operation_token = current_operation.set(self.name)

    def after_return(
        self,
        status: str,
        retval: Any,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        identity_token = getattr(self.request, "ghostrecon_identity_token", None)
        operation_token = getattr(self.request, "ghostrecon_operation_token", None)
        if operation_token is not None:
            current_operation.reset(operation_token)
        if identity_token is not None:
            current_identity.reset(identity_token)
