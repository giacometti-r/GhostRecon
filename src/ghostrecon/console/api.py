from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx

from ghostrecon.common.config import Settings
from ghostrecon.models.api import DashboardRole

DEFAULT_ACTOR = "dashboard"


@dataclass(frozen=True)
class ConsoleRequestContext:
    actor: str = DEFAULT_ACTOR
    role: str = DashboardRole.VIEWER.value


class ConsoleApiError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        payload: dict[str, Any] | None = None,
        path: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}
        self.path = path

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": str(self),
            "status_code": self.status_code,
            "payload": self.payload,
            "path": self.path,
        }


class ConsoleApiClient:
    """Synchronous gateway client used by Dash callbacks."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: int,
        actor: str = DEFAULT_ACTOR,
        role: str = DashboardRole.VIEWER.value,
        auth_token: str | None = None,
        client_factory: type[httpx.Client] = httpx.Client,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.actor = actor or DEFAULT_ACTOR
        self.role = role or DashboardRole.VIEWER.value
        self.auth_token = auth_token
        self.client_factory = client_factory

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        actor: str = DEFAULT_ACTOR,
        role: str = DashboardRole.VIEWER.value,
        client_factory: type[httpx.Client] = httpx.Client,
    ) -> ConsoleApiClient:
        return cls(
            base_url=str(settings.gateway_base_url),
            timeout_seconds=settings.console_request_timeout_seconds,
            actor=actor,
            role=role,
            auth_token=settings.api_auth_token,
            client_factory=client_factory,
        )

    def url_for(self, path: str) -> str:
        normalized = path if path.startswith("/") else f"/{path}"
        return f"{self.base_url}{normalized}"

    def headers(self, *, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "X-Actor": self.actor,
            "X-Operator-Role": self.role,
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.request("GET", path, params=params)

    def post(
        self,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self.request("POST", path, payload=payload, idempotency_key=idempotency_key)

    def patch(
        self,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self.request("PATCH", path, payload=payload, idempotency_key=idempotency_key)

    def delete(
        self,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self.request("DELETE", path, payload=payload, idempotency_key=idempotency_key)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        client = self.client_factory(timeout=self.timeout_seconds)
        try:
            response = client.request(
                method,
                self.url_for(path),
                params=clean_params(params),
                json=payload,
                headers=self.headers(idempotency_key=idempotency_key),
            )
        except httpx.TimeoutException as exc:
            raise ConsoleApiError("gateway request timed out", path=path) from exc
        except httpx.HTTPError as exc:
            raise ConsoleApiError(f"gateway request failed: {exc}", path=path) from exc
        finally:
            close = getattr(client, "close", None)
            if close is not None:
                close()

        if response.status_code >= 400:
            raise ConsoleApiError(
                _error_message(response),
                status_code=response.status_code,
                payload=_response_payload(response),
                path=path,
            )
        return _response_payload(response)


def clean_params(params: dict[str, Any] | None) -> dict[str, Any]:
    return {key: value for key, value in (params or {}).items() if value not in (None, "")}


def dashboard_context_from_headers() -> ConsoleRequestContext:
    try:
        from flask import request

        actor = request.headers.get("X-Actor") or DEFAULT_ACTOR
        role = request.headers.get("X-Operator-Role") or DashboardRole.VIEWER.value
    except RuntimeError:
        return ConsoleRequestContext()
    return ConsoleRequestContext(actor=actor, role=normalize_role(role))


def normalize_role(role: str | None) -> str:
    try:
        return DashboardRole(role or DashboardRole.VIEWER.value).value
    except ValueError:
        return DashboardRole.VIEWER.value


def idempotency_key(action: str, *target_parts: object | None) -> str:
    stable_parts = [str(part) for part in target_parts if part not in (None, "")]
    suffix = f":{':'.join(stable_parts)}" if stable_parts else ""
    return f"dashboard:{action}{suffix}:{uuid4()}"


def metadata_from(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    metadata = payload.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def degraded_dependencies(payloads: list[dict[str, Any] | None]) -> list[str]:
    names: set[str] = set()
    for payload in payloads:
        metadata = metadata_from(payload)
        for dependency in metadata.get("degraded_dependencies") or []:
            names.add(str(dependency))
    return sorted(names)


def any_stale(payloads: list[dict[str, Any] | None]) -> bool:
    return any(bool(metadata_from(payload).get("stale")) for payload in payloads)


def _error_message(response: httpx.Response) -> str:
    payload = _response_payload(response)
    detail = payload.get("detail")
    if isinstance(detail, str):
        return detail
    return f"gateway returned HTTP {response.status_code}"


def _response_payload(response: httpx.Response) -> dict[str, Any]:
    if not response.content:
        return {}
    try:
        payload = response.json()
    except ValueError:
        return {"raw": response.text}
    return payload if isinstance(payload, dict) else {"data": payload}
