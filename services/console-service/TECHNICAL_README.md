
# console-service Technical README

## Architecture

Console Service is implemented by `src/ghostrecon/console/app.py`, `src/ghostrecon/console/api.py`, `src/ghostrecon/console/components.py`, `src/ghostrecon/console/layouts/`, `src/ghostrecon/console/callbacks/`. It is exposed through `console_router` and, where handlers also have `gateway_router` decorators, through `gateway-service` as the same handler function.

Related/shared modules referenced by this service: `src/ghostrecon/service_apps/factory.py`.

## Route Surface

| Exposure | Method | Path | Handler |
| --- | --- | --- | --- |
| service | `GET` | `/v1/review/candidates` | `review_candidates` |
| service | `POST` | `/v1/review/candidates/{candidate_id}/approve` | `review_candidate_approve` |
| service | `POST` | `/v1/review/candidates/{candidate_id}/reject` | `review_candidate_reject` |
| service | `POST` | `/v1/review/candidates/bulk-decision` | `review_candidates_bulk_decision` |
| service | `GET` | `/v1/review/crm-targets` | `review_crm_targets` |
| gateway | `GET` | `/v1/review/candidates` | `review_candidates` |
| gateway | `POST` | `/v1/review/candidates/{candidate_id}/approve` | `review_candidate_approve` |
| gateway | `POST` | `/v1/review/candidates/{candidate_id}/reject` | `review_candidate_reject` |
| gateway | `POST` | `/v1/review/candidates/bulk-decision` | `review_candidates_bulk_decision` |
| gateway | `GET` | `/v1/review/crm-targets` | `review_crm_targets` |

## Data Flow And Contracts

- Inputs enter through the route handlers, workers, or helper functions documented below and are validated by Pydantic request models or explicit helper checks.
- Persistence uses the shared database/session utilities in the implementation modules; serializers convert ORM rows into API models or JSON-safe dictionaries.
- Idempotent operations look up existing records by `Idempotency-Key` or derived stable hashes before creating new rows.
- Cross-service events are written through `OutboxEvent`/`new_event` helpers where the implementation emits asynchronous workflow signals.
- Policy checks are implemented inside the service layer and should not be bypassed by routes, workers, or console actions.
- The Dash console uses gateway/reporting clients for event create/edit, participant enrichment queueing, incident corroborate/reject/revert, and company watch promotion.
- Event and incident metadata/watermarks are visible only to `governance_reviewer`; incident rows locally dismiss rejected/promoted records while backend state remains authoritative.

## Function Reference

### `src/ghostrecon/console/app.py`

#### Module Functions

##### `create_console_dash_app(settings: Settings) -> Dash`

- Inputs: `settings` (Settings)
- Output: Returns `Dash`.
- Why: `create_console_dash_app` creates and persists a new domain object while enforcing idempotency and policy.
- How: It calls `Dash`, `register_callbacks`, `build_shell`, `Path`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: catches provider or validation errors and maps them to the module contract.

### `src/ghostrecon/console/api.py`

#### Classes

##### `ConsoleRequestContext`

`ConsoleRequestContext` is a data container or runtime class decorated with `dataclass(frozen=True)` based on `object`. Fields: `actor` (str), `role` (str).

##### `ConsoleApiError`

`ConsoleApiError` is a data container or runtime class based on `RuntimeError`. Fields: none declared at class level.

- `__init__(message: str, *, status_code: int | None = None, payload: dict[str, Any] | None = None, path: str | None = None) -> None`
  - Inputs: `message` (str), `status_code` (int | None), `payload` (dict[str, Any] | None), `path` (str | None)
  - Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
  - Why: Initializes ConsoleApiError with the provider, settings, or client state needed by later calls.
  - How: It calls `__init__`, `super`.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: may return `None` for not-found or unavailable data.
- `to_dict() -> dict[str, Any]`
  - Inputs: No external inputs.
  - Output: Returns `dict[str, Any]`.
  - Why: `ConsoleApiError.to_dict` provides the src/ghostrecon/console/api.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It performs direct field checks, simple transformations, or object construction in-process.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `ConsoleApiClient`

`ConsoleApiClient` is a data container or runtime class based on `object`. Fields: none declared at class level.

- `__init__(*, base_url: str, timeout_seconds: int, actor: str = DEFAULT_ACTOR, role: str = DashboardRole.VIEWER.value, auth_token: str | None = None, client_factory: type[httpx.Client] = httpx.Client) -> None`
  - Inputs: `base_url` (str), `timeout_seconds` (int), `actor` (str), `role` (str), `auth_token` (str | None), `client_factory` (type[httpx.Client])
  - Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
  - Why: Initializes ConsoleApiClient with the provider, settings, or client state needed by later calls.
  - How: It calls `base_url.rstrip`; uses HTTP/provider IO.
  - Side effects: calls external HTTP, SMTP, IMAP, DNS, or provider APIs.
  - Failures: may return `None` for not-found or unavailable data.
- `from_settings(cls, settings: Settings, *, actor: str = DEFAULT_ACTOR, role: str = DashboardRole.VIEWER.value, client_factory: type[httpx.Client] = httpx.Client) -> ConsoleApiClient`
  - Inputs: `cls` (untyped value), `settings` (Settings), `actor` (str), `role` (str), `client_factory` (type[httpx.Client])
  - Output: Returns `ConsoleApiClient`.
  - Why: `ConsoleApiClient.from_settings` provides the src/ghostrecon/console/api.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `cls`; uses HTTP/provider IO.
  - Side effects: calls external HTTP, SMTP, IMAP, DNS, or provider APIs.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `url_for(path: str) -> str`
  - Inputs: `path` (str)
  - Output: Returns `str`.
  - Why: `ConsoleApiClient.url_for` provides the src/ghostrecon/console/api.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `path.startswith`; uses parsing/normalization.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `headers(*, idempotency_key: str | None = None) -> dict[str, str]`
  - Inputs: `idempotency_key` (str | None)
  - Output: Returns `dict[str, str]`.
  - Why: `ConsoleApiClient.headers` provides the src/ghostrecon/console/api.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It uses idempotency lookup.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `get(path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]`
  - Inputs: `path` (str), `params` (dict[str, Any] | None)
  - Output: Returns `dict[str, Any]`.
  - Why: `ConsoleApiClient.get` provides the src/ghostrecon/console/api.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `self.request`.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `post(path: str, *, payload: dict[str, Any] | None = None, idempotency_key: str | None = None) -> dict[str, Any]`
  - Inputs: `path` (str), `payload` (dict[str, Any] | None), `idempotency_key` (str | None)
  - Output: Returns `dict[str, Any]`.
  - Why: `ConsoleApiClient.post` provides the src/ghostrecon/console/api.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `self.request`; uses idempotency lookup.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `patch(path: str, *, payload: dict[str, Any] | None = None, idempotency_key: str | None = None) -> dict[str, Any]`
  - Inputs: `path` (str), `payload` (dict[str, Any] | None), `idempotency_key` (str | None)
  - Output: Returns `dict[str, Any]`.
  - Why: `ConsoleApiClient.patch` provides the src/ghostrecon/console/api.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `self.request`; uses idempotency lookup.
  - Side effects: No durable side effects; work is limited to computation, validation, or projection.
  - Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.
- `request(method: str, path: str, *, params: dict[str, Any] | None = None, payload: dict[str, Any] | None = None, idempotency_key: str | None = None) -> dict[str, Any]`
  - Inputs: `method` (str), `path` (str), `params` (dict[str, Any] | None), `payload` (dict[str, Any] | None), `idempotency_key` (str | None)
  - Output: Returns `dict[str, Any]`.
  - Why: `ConsoleApiClient.request` provides the src/ghostrecon/console/api.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
  - How: It calls `self.client_factory`, `_response_payload`, `client.request`, `getattr`, `ConsoleApiError`, `self.url_for`, `close`, `_error_message`; uses HTTP/provider IO, idempotency lookup.
  - Side effects: calls external HTTP, SMTP, IMAP, DNS, or provider APIs.
  - Failures: raises `ConsoleApiError`; catches provider or validation errors and maps them to the module contract.

#### Module Functions

##### `clean_params(params: dict[str, Any] | None) -> dict[str, Any]`

- Inputs: `params` (dict[str, Any] | None)
- Output: Returns `dict[str, Any]`.
- Why: `clean_params` provides the src/ghostrecon/console/api.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `items`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `dashboard_context_from_headers() -> ConsoleRequestContext`

- Inputs: No external inputs.
- Output: Returns `ConsoleRequestContext`.
- Why: `dashboard_context_from_headers` provides the src/ghostrecon/console/api.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `ConsoleRequestContext`, `get`, `normalize_role`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: catches provider or validation errors and maps them to the module contract.

##### `normalize_role(role: str | None) -> str`

- Inputs: `role` (str | None)
- Output: Returns `str`.
- Why: `normalize_role` canonicalizes caller or provider input before comparison/persistence.
- How: It calls `DashboardRole`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: catches provider or validation errors and maps them to the module contract.

##### `idempotency_key(action: str, target_id: str | None = None) -> str`

- Inputs: `action` (str), `target_id` (str | None)
- Output: Returns `str`.
- Why: `idempotency_key` provides the src/ghostrecon/console/api.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `uuid4`; uses idempotency lookup.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `metadata_from(payload: dict[str, Any] | None) -> dict[str, Any]`

- Inputs: `payload` (dict[str, Any] | None)
- Output: Returns `dict[str, Any]`.
- Why: `metadata_from` provides the src/ghostrecon/console/api.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `payload.get`, `isinstance`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `degraded_dependencies(payloads: list[dict[str, Any] | None]) -> list[str]`

- Inputs: `payloads` (list[dict[str, Any] | None])
- Output: Returns `list[str]`.
- Why: `degraded_dependencies` provides the src/ghostrecon/console/api.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `metadata_from`, `metadata.get`, `names.add`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `any_stale(payloads: list[dict[str, Any] | None]) -> bool`

- Inputs: `payloads` (list[dict[str, Any] | None])
- Output: Returns `bool`.
- Why: `any_stale` provides the src/ghostrecon/console/api.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `any`, `bool`, `get`, `metadata_from`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_error_message(response: httpx.Response) -> str`

- Inputs: `response` (httpx.Response)
- Output: Returns `str`.
- Why: `_error_message` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_response_payload`, `payload.get`, `isinstance`; uses HTTP/provider IO.
- Side effects: calls external HTTP, SMTP, IMAP, DNS, or provider APIs.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_response_payload(response: httpx.Response) -> dict[str, Any]`

- Inputs: `response` (httpx.Response)
- Output: Returns `dict[str, Any]`.
- Why: `_response_payload` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `response.json`, `isinstance`; uses HTTP/provider IO.
- Side effects: calls external HTTP, SMTP, IMAP, DNS, or provider APIs.
- Failures: catches provider or validation errors and maps them to the module contract.

### `src/ghostrecon/console/components.py`

#### Module Functions

##### `icon(name: str, *, size: int = 18) -> DashIconify`

- Inputs: `name` (str), `size` (int)
- Output: Returns `DashIconify`.
- Why: `icon` provides the src/ghostrecon/console/components.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `DashIconify`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `nav_link(label: str, href: str, icon_name: str) -> dcc.Link`

- Inputs: `label` (str), `href` (str), `icon_name` (str)
- Output: Returns `dcc.Link`.
- Why: `nav_link` provides the src/ghostrecon/console/components.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `dcc.Link`, `icon`, `html.Span`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `page_header(title: str, subtitle: str | None = None, actions: list[Any] | None = None) -> html.Div`

- Inputs: `title` (str), `subtitle` (str | None), `actions` (list[Any] | None)
- Output: Returns `html.Div`.
- Why: `page_header` provides the src/ghostrecon/console/components.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `html.Div`, `html.H1`, `html.P`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `metadata_banner(payloads: list[dict[str, Any] | None]) -> html.Div`

- Inputs: `payloads` (list[dict[str, Any] | None])
- Output: Returns `html.Div`.
- Why: `metadata_banner` provides the src/ghostrecon/console/components.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `degraded_dependencies`, `any_stale`, `html.Div`, `join`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `metadata_details(payload: dict[str, Any] | None) -> html.Div`

- Inputs: `payload` (dict[str, Any] | None)
- Output: Returns `html.Div`.
- Why: `metadata_details` provides the src/ghostrecon/console/components.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `metadata_from`, `html.Dl`, `html.Div`, `metadata.get`, `html.Dt`, `html.Dd`, `format_value`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `summary_tile(label: str, value: int | str, detail: str | None = None) -> html.Div`

- Inputs: `label` (str), `value` (int | str), `detail` (str | None)
- Output: Returns `html.Div`.
- Why: `summary_tile` provides the src/ghostrecon/console/components.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `html.Div`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `status_badge(value: Any) -> html.Span`

- Inputs: `value` (Any)
- Output: Returns `html.Span`.
- Why: `status_badge` provides the src/ghostrecon/console/components.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `replace`, `html.Span`, `css_token`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `action_button(label: str, action_id: dict[str, Any] | str, icon_name: str, *, disabled: bool = False, danger: bool = False) -> html.Button`

- Inputs: `label` (str), `action_id` (dict[str, Any] | str), `icon_name` (str), `disabled` (bool), `danger` (bool)
- Output: Returns `html.Button`.
- Why: `action_button` provides the src/ghostrecon/console/components.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `html.Button`, `icon`, `html.Span`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `records_table(records: list[dict[str, Any]], columns: list[ColumnSpec], *, actions: ActionFactory | None = None, empty_message: str = 'No records match the current view.') -> html.Div`

- Inputs: `records` (list[dict[str, Any]]), `columns` (list[ColumnSpec]), `actions` (ActionFactory | None), `empty_message` (str)
- Output: Returns `html.Div`.
- Why: `records_table` provides the src/ghostrecon/console/components.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `html.Div`, `empty_state`, `html.Th`, `header_cells.append`, `rows.append`, `html.Table`, `html.Td`, `cells.append`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `empty_state(message: str) -> html.Div`

- Inputs: `message` (str)
- Output: Returns `html.Div`.
- Why: `empty_state` provides the src/ghostrecon/console/components.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `html.Div`, `icon`, `html.Span`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `error_notice(message: str, detail: str | None = None) -> html.Div`

- Inputs: `message` (str), `detail` (str | None)
- Output: Returns `html.Div`.
- Why: `error_notice` provides the src/ghostrecon/console/components.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `html.Div`, `html.Strong`, `html.P`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `query_badges(params: dict[str, Any]) -> html.Div`

- Inputs: `params` (dict[str, Any])
- Output: Returns `html.Div`.
- Why: `query_badges` provides the src/ghostrecon/console/components.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `html.Div`, `html.Span`, `params.items`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `detail_panel(title: str, rows: list[tuple[str, Any]]) -> html.Section`

- Inputs: `title` (str), `rows` (list[tuple[str, Any]])
- Output: Returns `html.Section`.
- Why: `detail_panel` provides the src/ghostrecon/console/components.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `html.Section`, `html.H2`, `html.Dl`, `html.Div`, `html.Dt`, `html.Dd`, `format_value`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `json_block(value: Any) -> html.Pre`

- Inputs: `value` (Any)
- Output: Returns `html.Pre`.
- Why: `json_block` provides the src/ghostrecon/console/components.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `html.Pre`, `format_json`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `format_value(value: Any) -> str`

- Inputs: `value` (Any)
- Output: Returns `str`.
- Why: `format_value` provides the src/ghostrecon/console/components.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `isinstance`, `format_json`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `format_json(value: Any) -> str`

- Inputs: `value` (Any)
- Output: Returns `str`.
- Why: `format_json` provides the src/ghostrecon/console/components.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `json.dumps`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: catches provider or validation errors and maps them to the module contract.

##### `css_token(value: Any) -> str`

- Inputs: `value` (Any)
- Output: Returns `str`.
- Why: `css_token` provides the src/ghostrecon/console/components.py behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `lower`, `join`, `char.isalnum`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

### `src/ghostrecon/console/layouts/`

#### Module Functions

##### `build_shell(settings: Settings) -> html.Div`

- Inputs: `settings` (Settings)
- Output: Returns `html.Div`.
- Why: `build_shell` derives a stable request, key, or projection object from richer inputs.
- How: It calls `dashboard_context_from_headers`, `html.Div`, `replace`, `dcc.Location`, `dcc.Store`, `html.Header`, `html.Footer`, `html.Nav`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `render_page(pathname: str | None, search: str | None, actor: str | None, role: str | None, settings: Settings, *, client: ConsoleApiClient | None = None) -> html.Div`

- Inputs: `pathname` (str | None), `search` (str | None), `actor` (str | None), `role` (str | None), `settings` (Settings), `client` (ConsoleApiClient | None)
- Output: Returns `html.Div`.
- Why: `render_page` constructs Dash UI for a page or widget.
- How: It calls `_normalize_role`, `_params`, `_page`, `ConsoleApiClient.from_settings`, `rstrip`, `path.startswith`, `overview_page`, `events_page`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: catches provider or validation errors and maps them to the module contract.

##### `overview_page(client: ConsoleApiClient, params: dict[str, Any]) -> html.Div`

- Inputs: `client` (ConsoleApiClient), `params` (dict[str, Any])
- Output: Returns `html.Div`.
- Why: `overview_page` provides the src/ghostrecon/console/layouts/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `_errors`, `_page`, `_safe_get`, `summary_tile`, `isinstance`, `get`, `html.Div`, `detail_panel`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `events_page(client: ConsoleApiClient, params: dict[str, Any], *, role: str) -> html.Div`

- Inputs: `client` (ConsoleApiClient), `params` (dict[str, Any]), `role` (str)
- Output: Returns `html.Div`.
- Why: `events_page` provides the src/ghostrecon/console/layouts/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `_safe_get`, `payload.get`, `_page`, `_filtered`, `query_badges`, `_event_calendar`, `_event_map`, `records_table`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `event_detail_page(client: ConsoleApiClient, event_id: str, *, role: str) -> html.Div`

- Inputs: `client` (ConsoleApiClient), `event_id` (str), `role` (str)
- Output: Returns `html.Div`.
- Why: `event_detail_page` provides the src/ghostrecon/console/layouts/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `_safe_get`, `payload.get`, `_page`, `detail_panel`, `records_table`, `metadata_details`, `participants.get`, `event.get`; uses policy validation.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `incidents_page(client: ConsoleApiClient, params: dict[str, Any], *, role: str) -> html.Div`

- Inputs: `client` (ConsoleApiClient), `params` (dict[str, Any]), `role` (str)
- Output: Returns `html.Div`.
- Why: `incidents_page` provides the src/ghostrecon/console/layouts/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `_safe_get`, `payload.get`, `_page`, `_filtered`, `query_badges`, `_incident_chart`, `records_table`, `_pagination`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `incident_detail_page(client: ConsoleApiClient, incident_id: str, *, role: str) -> html.Div`

- Inputs: `client` (ConsoleApiClient), `incident_id` (str), `role` (str)
- Output: Returns `html.Div`.
- Why: `incident_detail_page` provides the src/ghostrecon/console/layouts/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `_safe_get`, `payload.get`, `_page`, `detail_panel`, `html.Div`, `metadata_details`, `_incident_actions`, `incident.get`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `watchlists_page(client: ConsoleApiClient, params: dict[str, Any], *, role: str) -> html.Div`

- Inputs: `client` (ConsoleApiClient), `params` (dict[str, Any]), `role` (str)
- Output: Returns `html.Div`.
- Why: `watchlists_page` provides the src/ghostrecon/console/layouts/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `_safe_get`, `_page`, `_filtered`, `query_badges`, `records_table`, `_pagination`, `payload.get`, `_watch_actions`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `review_page(client: ConsoleApiClient, params: dict[str, Any], *, role: str) -> html.Div`

- Inputs: `client` (ConsoleApiClient), `params` (dict[str, Any]), `role` (str)
- Output: Returns `html.Div`.
- Why: `review_page` provides the src/ghostrecon/console/layouts/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `_safe_get`, `_page`, `_filtered`, `query_badges`, `dcc.Link`, `html.Div`, `records_table`, `_pagination`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `enrichment_review_page(client: ConsoleApiClient, params: dict[str, Any]) -> html.Div`

- Inputs: `client` (ConsoleApiClient), `params` (dict[str, Any])
- Output: Returns `html.Div`.
- Why: `enrichment_review_page` provides the src/ghostrecon/console/layouts/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `_safe_get`, `_page`, `_filtered`, `records_table`, `contacts.get`, `cases.get`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `crm_exports_page(client: ConsoleApiClient, params: dict[str, Any], *, role: str) -> html.Div`

- Inputs: `client` (ConsoleApiClient), `params` (dict[str, Any]), `role` (str)
- Output: Returns `html.Div`.
- Why: `crm_exports_page` provides the src/ghostrecon/console/layouts/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `_safe_get`, `_page`, `_filtered`, `query_badges`, `records_table`, `_pagination`, `payload.get`, `_crm_target_actions`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `crm_export_detail_page(client: ConsoleApiClient, batch_id: str, *, role: str) -> html.Div`

- Inputs: `client` (ConsoleApiClient), `batch_id` (str), `role` (str)
- Output: Returns `html.Div`.
- Why: `crm_export_detail_page` provides the src/ghostrecon/console/layouts/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `_safe_get`, `_page`, `detail_panel`, `html.Div`, `records_table`, `_crm_batch_actions`, `batch.get`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `sequences_page(client: ConsoleApiClient, params: dict[str, Any], *, role: str) -> html.Div`

- Inputs: `client` (ConsoleApiClient), `params` (dict[str, Any]), `role` (str)
- Output: Returns `html.Div`.
- Why: `sequences_page` provides the src/ghostrecon/console/layouts/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `_safe_get`, `_page`, `_filtered`, `query_badges`, `records_table`, `html.Div`, `payload.get`, `_sequence_actions`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `meetings_page(client: ConsoleApiClient, params: dict[str, Any], *, role: str) -> html.Div`

- Inputs: `client` (ConsoleApiClient), `params` (dict[str, Any]), `role` (str)
- Output: Returns `html.Div`.
- Why: `meetings_page` provides the src/ghostrecon/console/layouts/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `_safe_get`, `_page`, `_filtered`, `query_badges`, `records_table`, `_pagination`, `payload.get`, `dcc.Link`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `meeting_detail_page(client: ConsoleApiClient, meeting_id: str, *, role: str) -> html.Div`

- Inputs: `client` (ConsoleApiClient), `meeting_id` (str), `role` (str)
- Output: Returns `html.Div`.
- Why: `meeting_detail_page` provides the src/ghostrecon/console/layouts/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `_safe_get`, `payload.get`, `_page`, `detail_panel`, `html.Div`, `records_table`, `_meeting_actions`, `meeting.get`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `source_health_page(client: ConsoleApiClient, params: dict[str, Any]) -> html.Div`

- Inputs: `client` (ConsoleApiClient), `params` (dict[str, Any])
- Output: Returns `html.Div`.
- Why: `source_health_page` provides the src/ghostrecon/console/layouts/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `_safe_get`, `_page`, `_filtered`, `query_badges`, `records_table`, `html.Div`, `_pagination`, `payload.get`; uses policy validation.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_page(title: str, payloads: list[dict[str, Any] | None], children: list[Any], *, query_params: dict[str, Any] | None = None) -> html.Div`

- Inputs: `title` (str), `payloads` (list[dict[str, Any] | None]), `children` (list[Any]), `query_params` (dict[str, Any] | None)
- Output: Returns `html.Div`.
- Why: `_page` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `html.Div`, `page_header`, `metadata_banner`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_safe_get(client: ConsoleApiClient, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]`

- Inputs: `client` (ConsoleApiClient), `path` (str), `params` (dict[str, Any] | None)
- Output: Returns `dict[str, Any]`.
- Why: `_safe_get` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `client.get`, `exc.to_dict`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: catches provider or validation errors and maps them to the module contract.

##### `_errors(payloads: dict[str, dict[str, Any]]) -> list[html.Div]`

- Inputs: `payloads` (dict[str, dict[str, Any]])
- Output: Returns `list[html.Div]`.
- Why: `_errors` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `payloads.items`, `errors.append`, `error_notice`, `get`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_count(payload: dict[str, Any], key: str) -> int`

- Inputs: `payload` (dict[str, Any]), `key` (str)
- Output: Returns `int`.
- Why: `_count` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `payload.get`, `isinstance`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_params(search: str | None) -> dict[str, Any]`

- Inputs: `search` (str | None)
- Output: Returns `dict[str, Any]`.
- Why: `_params` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `parse_qs`, `lstrip`, `parsed.items`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_filtered(params: dict[str, Any], *allowed: str) -> dict[str, Any]`

- Inputs: `params` (dict[str, Any]), `*allowed`
- Output: Returns `dict[str, Any]`.
- Why: `_filtered` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `params.get`; uses policy validation.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_pagination(payload: dict[str, Any], base_path: str, params: dict[str, Any]) -> html.Div`

- Inputs: `payload` (dict[str, Any]), `base_path` (str), `params` (dict[str, Any])
- Output: Returns `html.Div`.
- Why: `_pagination` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `payload.get`, `join`, `html.Div`, `dcc.Link`, `next_params.items`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_event_calendar(events: list[dict[str, Any]]) -> html.Div`

- Inputs: `events` (list[dict[str, Any]])
- Output: Returns `html.Div`.
- Why: `_event_calendar` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `Counter`, `go.Figure`, `figure.update_layout`, `html.Section`, `empty_state`, `html.H2`, `dcc.Graph`, `go.Bar`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_event_map(events: list[dict[str, Any]]) -> html.Div`

- Inputs: `events` (list[dict[str, Any]])
- Output: Returns `html.Div`.
- Why: `_event_map` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `go.Figure`, `figure.update_layout`, `html.Section`, `empty_state`, `html.H2`, `dcc.Graph`, `go.Scattergeo`, `event.get`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_incident_chart(incidents: list[dict[str, Any]]) -> html.Div`

- Inputs: `incidents` (list[dict[str, Any]])
- Output: Returns `html.Div`.
- Why: `_incident_chart` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `Counter`, `go.Figure`, `figure.update_layout`, `html.Section`, `empty_state`, `html.H2`, `dcc.Graph`, `go.Bar`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_review_actions(record: dict[str, Any], role: str) -> list[Any]`

- Inputs: `record` (dict[str, Any]), `role` (str)
- Output: Returns `list[Any]`.
- Why: `_review_actions` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_can_mutate`, `action_button`, `_action_id`, `record.get`; uses policy validation.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_bulk_review_actions(records: list[dict[str, Any]], role: str) -> list[Any]`

- Inputs: `records` (list[dict[str, Any]]), `role` (str)
- Output: Returns `list[Any]`.
- Why: `_bulk_review_actions` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `join`, `record.get`, `versions.keys`, `_can_mutate`, `action_button`, `_action_id`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_crm_target_actions(record: dict[str, Any], role: str) -> list[Any]`

- Inputs: `record` (dict[str, Any]), `role` (str)
- Output: Returns `list[Any]`.
- Why: `_crm_target_actions` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `action_button`, `_action_id`, `record.get`, `_can_mutate`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_crm_batch_actions(batch: dict[str, Any], role: str) -> list[Any]`

- Inputs: `batch` (dict[str, Any]), `role` (str)
- Output: Returns `list[Any]`.
- Why: `_crm_batch_actions` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `action_button`, `_action_id`, `batch.get`, `_can_mutate`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_incident_actions(record: dict[str, Any], role: str) -> list[Any]`

- Inputs: `record` (dict[str, Any]), `role` (str)
- Output: Returns `list[Any]`.
- Why: `_incident_actions` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_can_mutate`, `record.get`, `dcc.Link`, `action_button`, `_action_id`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_watch_actions(record: dict[str, Any], role: str) -> list[Any]`

- Inputs: `record` (dict[str, Any]), `role` (str)
- Output: Returns `list[Any]`.
- Why: `_watch_actions` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `bool`, `action_button`, `record.get`, `_action_id`, `_can_mutate`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_sequence_actions(record: dict[str, Any], role: str) -> list[Any]`

- Inputs: `record` (dict[str, Any]), `role` (str)
- Output: Returns `list[Any]`.
- Why: `_sequence_actions` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_can_mutate`, `action_button`, `record.get`, `_action_id`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_meeting_actions(record: dict[str, Any], role: str) -> list[Any]`

- Inputs: `record` (dict[str, Any]), `role` (str)
- Output: Returns `list[Any]`.
- Why: `_meeting_actions` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `_can_mutate`, `action_button`, `_action_id`, `record.get`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_action_id(kind: str, action: str, target_id: Any, version: Any = None, policy_hash: Any = None, enabled: Any = None) -> dict[str, Any]`

- Inputs: `kind` (str), `action` (str), `target_id` (Any), `version` (Any), `policy_hash` (Any), `enabled` (Any)
- Output: Returns `dict[str, Any]`.
- Why: `_action_id` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It uses policy validation.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_can_mutate(role: str) -> bool`

- Inputs: `role` (str)
- Output: Returns `bool`.
- Why: `_can_mutate` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It performs direct field checks, simple transformations, or object construction in-process.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_normalize_role(role: str | None) -> str`

- Inputs: `role` (str | None)
- Output: Returns `str`.
- Why: `_normalize_role` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `DashboardRole`; uses parsing/normalization.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: catches provider or validation errors and maps them to the module contract.

##### `_location(event: dict[str, Any]) -> str`

- Inputs: `event` (dict[str, Any])
- Output: Returns `str`.
- Why: `_location` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `join`, `event.get`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

### `src/ghostrecon/console/callbacks/`

#### Module Functions

##### `register_callbacks(dash_app: Any, settings: Settings) -> None`

- Inputs: `dash_app` (Any), `settings` (Settings)
- Output: Returns `None`; all useful effects occur through persistence, provider calls, mutation, or raised errors.
- Why: `register_callbacks` provides the src/ghostrecon/console/callbacks/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `dash_app.callback`, `render_page`, `Output`, `Input`, `State`, `isinstance`, `perform_dashboard_action`, `_success_notice`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: may return `None` for not-found or unavailable data; catches provider or validation errors and maps them to the module contract.

##### `perform_dashboard_action(action_id: dict[str, Any], *, actor: str, role: str | None, settings: Settings, client: ConsoleApiClient | None = None, client_factory: type[httpx.Client] = httpx.Client) -> str`

- Inputs: `action_id` (dict[str, Any]), `actor` (str), `role` (str | None), `settings` (Settings), `client` (ConsoleApiClient | None), `client_factory` (type[httpx.Client])
- Output: Returns `str`.
- Why: `perform_dashboard_action` provides the src/ghostrecon/console/callbacks/ behavior named by the function and is called by routes, workers, repositories, or adjacent helpers.
- How: It calls `normalize_role`, `ConsoleApiError`, `ConsoleApiClient.from_settings`, `api.post`, `_perform_incident_action`, `api.patch`, `_perform_meeting_action`, `action_id.get`; uses HTTP/provider IO, idempotency lookup, parsing/normalization, policy validation.
- Side effects: calls external HTTP, SMTP, IMAP, DNS, or provider APIs.
- Failures: raises `ConsoleApiError`.

##### `_perform_incident_action(api: ConsoleApiClient, action: str, target_id: str, action_id: dict[str, Any]) -> str`

- Inputs: `api` (ConsoleApiClient), `action` (str), `target_id` (str), `action_id` (dict[str, Any])
- Output: Returns `str`.
- Why: `_perform_incident_action` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `ConsoleApiError`, `api.post`, `action_id.get`, `_int`, `idempotency_key`; uses idempotency lookup, policy validation.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: raises `ConsoleApiError`.

##### `_perform_meeting_action(api: ConsoleApiClient, action: str, target_id: str) -> str`

- Inputs: `api` (ConsoleApiClient), `action` (str), `target_id` (str)
- Output: Returns `str`.
- Why: `_perform_meeting_action` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `ConsoleApiError`, `api.post`, `idempotency_key`; uses idempotency lookup.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: raises `ConsoleApiError`.

##### `_success_notice(message: str) -> html.Div`

- Inputs: `message` (str)
- Output: Returns `html.Div`.
- Why: `_success_notice` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It calls `html.Div`, `icon`, `html.Span`.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: No explicit raises in the implementation; upstream callers still need to handle dependency errors from invoked helpers.

##### `_int(value: Any) -> int`

- Inputs: `value` (Any)
- Output: Returns `int`.
- Why: `_int` is a private helper that keeps the module-level workflow readable and isolates repeated implementation detail.
- How: It performs direct field checks, simple transformations, or object construction in-process.
- Side effects: No durable side effects; work is limited to computation, validation, or projection.
- Failures: catches provider or validation errors and maps them to the module contract.

## Shared Module Notes

- `src/ghostrecon/service_apps/factory.py` is shared or mounted behavior used by this service; its exhaustive function reference lives in the service that owns that module in the mapping, or in `gateway-service` for route/factory code.

## Failure Handling

- Validation helpers raise `ValueError` or provider-specific runtime errors before database changes where possible.
- Route handlers translate expected service exceptions to HTTP status codes such as `400`, `401`, `404`, `409`, `502`, or `503`.
- Provider adapters keep provider-specific payload parsing isolated from workflow state changes.
- Retry-oriented functions preserve existing records and append status/failure metadata instead of deleting historical evidence.

## Tests

- `tests/unit/test_console_dashboard.py`

## Sprint 25a Security Boundary

The console still sends legacy demo actor/role state. Strict profiles reject those headers, while
OIDC sessions, console workload identity, represented-user propagation, CSRF, and security-state UX
are not implemented. The current console is local/test-only from an identity perspective. See the
[security foundation reference](../../docs/security-foundation.md).

## Startup and dependency contract

Set GHOSTRECON_PROFILE explicitly. In staging and production this process owns gateway URL only; it does not own or probe the database. Startup exits non-zero with redacted setting/error/remediation records when an owned dependency is missing, fake, disabled, unsafe, or placeholder.

Readiness returns status, service, profile, and named checks. Console reports gateway configuration and never opens a direct database readiness connection.

Synthetic/demo adapters and deterministic inferred domains are local-only. Tests may inject fakes under the test profile; staging and production reject fake injection and exact synthetic lineage markers before persistence.

Run python -m ghostrecon.common.preflight --format json with GHOSTRECON_SERVICE_NAME set to this process before launch.
