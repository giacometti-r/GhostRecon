from __future__ import annotations

import httpx
from fastapi import Request
from fastapi.responses import Response

from .identity import IdentityContext
from .operations import OperationPolicy
from .perimeter import security_error
from .workload import OBO_HEADER, SERVICE_HEADER, WorkloadSigner

HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
        "host",
        "cookie",
        "authorization",
    }
)


async def forward_to_owner(
    request: Request,
    policy: OperationPolicy,
    identity: IdentityContext,
) -> Response:
    signer: WorkloadSigner = request.app.state.workload_signer
    headers = {
        name: value
        for name, value in request.headers.items()
        if name.lower() not in HOP_BY_HOP
        and not name.lower().startswith("x-ghostrecon-")
        and not name.lower().startswith("x-actor")
    }
    headers[SERVICE_HEADER] = signer.service_token(policy.owner)
    headers[OBO_HEADER] = signer.obo_token(identity, policy.owner, policy.operation_id)
    target = f"http://{policy.owner}:8080{request.url.path}"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            upstream = await client.request(
                request.method,
                target,
                params=request.query_params,
                content=await request.body(),
                headers=headers,
            )
    except httpx.HTTPError:
        return security_error(
            status_code=503,
            code="owner_unavailable",
            message="owning service is temporarily unavailable",
            correlation_id=request.state.correlation_id,
        )
    response_headers = {
        name: value
        for name, value in upstream.headers.items()
        if name.lower() not in HOP_BY_HOP and name.lower() != "content-length"
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=upstream.headers.get("content-type"),
    )


async def forward_to_console(request: Request, identity: IdentityContext) -> Response:
    signer: WorkloadSigner = request.app.state.workload_signer
    headers = {
        name: value
        for name, value in request.headers.items()
        if name.lower() not in HOP_BY_HOP
        and not name.lower().startswith("x-ghostrecon-")
        and name.lower() not in {"x-actor", "x-operator-role"}
    }
    # The host-only session remains authoritative at the gateway; forwarding it
    # lets same-origin Dash callbacks return through the gateway session path.
    cookie = request.headers.get("cookie")
    if cookie:
        headers["Cookie"] = cookie
    headers[SERVICE_HEADER] = signer.service_token("console-service")
    headers[OBO_HEADER] = signer.obo_token(identity, "console-service", "console.render")
    headers["X-GhostRecon-Verified-Actor"] = identity.actor_label
    headers["X-GhostRecon-Verified-Subject"] = identity.represented_subject
    headers["X-GhostRecon-Verified-Roles"] = ",".join(sorted(identity.roles))
    headers["X-GhostRecon-Verified-Permissions"] = ",".join(sorted(identity.permissions))
    headers["X-GhostRecon-Verified-Assurance"] = identity.assurance.value
    headers["X-GhostRecon-Verified-Authentication-Method"] = identity.authentication_method
    headers["X-GhostRecon-Verified-Authenticated-At"] = identity.authenticated_at.isoformat()
    headers["X-GhostRecon-Verified-Correlation-ID"] = identity.correlation_id
    headers["X-GhostRecon-Verified-Role"] = next(iter(sorted(identity.roles)), "viewer")
    path = request.url.path
    target = f"http://console-service:8080{path}"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            upstream = await client.request(
                request.method,
                target,
                params=request.query_params,
                content=await request.body(),
                headers=headers,
            )
    except httpx.HTTPError:
        return security_error(
            status_code=503,
            code="console_unavailable",
            message="console is temporarily unavailable",
            correlation_id=request.state.correlation_id,
        )
    response_headers = {
        name: value
        for name, value in upstream.headers.items()
        if name.lower() not in HOP_BY_HOP and name.lower() != "content-length"
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=upstream.headers.get("content-type"),
    )
