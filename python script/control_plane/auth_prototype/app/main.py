from __future__ import annotations

import asyncio
import secrets
import statistics
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urljoin

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import get_settings
from .database import database_is_healthy, get_db_session
from .fleet import (
    DEFAULT_PROVISIONING_WORKFLOW_KEY,
    FleetNotFoundError,
    FleetValidationError,
    build_edge_agent_e2e_probe_context,
    build_ems_light_e2e_probe_context,
    build_orders_probe_context,
    cancel_provisioning_job,
    create_site,
    delete_provisioning_job,
    delete_inventory_asset,
    get_inventory_asset,
    get_inventory_scan,
    get_provisioning_job,
    get_site,
    list_provisioning_workflows,
    list_inventory_assets,
    list_inventory_scans,
    list_provisioning_jobs,
    list_sites,
    prepare_provisioning_job,
    register_inventory_asset,
    request_inventory_scan,
    run_provisioning_job,
    serialize_inventory_asset,
    serialize_inventory_scan,
    serialize_provisioning_job,
    serialize_site,
    set_site_active,
    update_site,
)
from .nats_e2e import (
    NatsE2EProbeError,
    run_monitoring_connection_probe_via_broker_async,
    run_nats_command_request_via_broker_async,
    run_nats_request_reply_probe_async,
    run_orders_probe_via_broker_async,
    run_nats_request_reply_probe_via_broker_async,
)
from .keycloak_admin import (
    KeycloakAdminError,
    delete_keycloak_user,
    provision_keycloak_user,
    update_keycloak_user,
)
from .oidc import OIDCError, build_authorization_url, build_logout_url, exchange_authorization_code, fetch_userinfo
from .rbac import fetch_rbac_catalog
from .security import (
    DEFAULT_DEMO_USERS,
    ManagedRoleError,
    ManagedUserNotFoundError,
    ManagedUserProvisionError,
    SessionUser,
    authenticate_bearer_user,
    authenticate_legacy,
    build_session_payload,
    delete_managed_user,
    extract_id_token,
    get_managed_user,
    list_managed_users,
    load_session_user,
    provision_managed_user,
    replace_user_roles,
    serialize_user,
    set_user_active,
    sync_user_from_oidc_claims,
    update_managed_user_profile,
)
from .wazuh_alerts import build_live_alerts_snapshot

settings = get_settings()
templates = Jinja2Templates(directory=str(Path(__file__).with_name("templates")))
frontend_dist_dir = Path(__file__).resolve().parent.parent / "frontend" / "dist"
frontend_index_file = frontend_dist_dir / "index.html"
frontend_assets_dir = frontend_dist_dir / "assets"
frontend_favicon_file = frontend_dist_dir / "favicon.png"

app = FastAPI(title=settings.app_name)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie=settings.session_cookie_name,
    same_site=settings.same_site,
    https_only=settings.secure_cookies,
    max_age=settings.session_ttl_seconds,
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=list(settings.trusted_hosts),
)

app.mount(
    "/ui/assets",
    StaticFiles(directory=str(frontend_assets_dir), check_dir=False),
    name="ui-assets",
)


@app.get("/favicon.png", include_in_schema=False)
async def favicon() -> Response:
    if not frontend_favicon_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Frontend favicon build is not available. Run npm run build in auth_prototype/frontend.",
        )
    return FileResponse(frontend_favicon_file, media_type="image/png")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon_ico() -> Response:
    return RedirectResponse(url="/favicon.png?v=2", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


class UserRoleUpdatePayload(BaseModel):
    role_names: list[str] = Field(default_factory=list)


class UserActiveUpdatePayload(BaseModel):
    is_active: bool


class UserInvitePayload(BaseModel):
    email: str
    first_name: str | None = None
    last_name: str | None = None
    role_names: list[str] = Field(default_factory=list)


class UserProfileUpdatePayload(BaseModel):
    email: str
    first_name: str | None = None
    last_name: str | None = None


class SiteUpsertPayload(BaseModel):
    code: str
    name: str
    customer_name: str | None = None
    country: str | None = None
    city: str | None = None
    timezone: str | None = None
    address_line1: str | None = None
    notes: str | None = None
    is_active: bool = True


class SiteStatusUpdatePayload(BaseModel):
    is_active: bool


class InventoryScanRequestPayload(BaseModel):
    site_id: int | None = None
    target_ip: str
    teltonika_router_ip: str | None = None
    target_label: str | None = None
    ssh_username: str | None = None
    ssh_port: int | None = None
    downstream_probe_ip: str | None = None
    asset_type: str = "industrial_pc"


class AssetRegistrationPayload(BaseModel):
    site_id: int | None = None
    site_code: str | None = None
    site_name: str | None = None
    customer_name: str | None = None
    country: str | None = None
    city: str | None = None
    timezone: str | None = None
    address_line1: str | None = None
    site_notes: str | None = None
    hostname: str
    inventory_hostname: str
    naming_slug: str | None = None
    management_ip: str | None = None
    teltonika_router_ip: str | None = None
    management_interface: str | None = None
    uplink_interface: str | None = None
    gateway_ip: str | None = None
    wireguard_address: str | None = None
    notes: str | None = None
    provisioning_vars: dict[str, str] = Field(default_factory=dict)


class ProvisioningJobCreatePayload(BaseModel):
    asset_id: int
    workflow_key: str | None = None
    playbook_name: str | None = None
    dispatch_mode: str = "auto"
    inventory_group: str = "cascadya_ipc"
    remote_unlock_vault_secret_value: str | None = None
    remote_unlock_vault_secret_confirm_overwrite: bool = False


class ProvisioningJobRunPayload(BaseModel):
    step_key: str | None = None


class E2ETestRequestPayload(BaseModel):
    asset_id: int | None = None
    site_id: int | None = None
    flow_key: str = "ems_site"
    sample_count: int = Field(default=5, ge=1, le=100)
    sample_interval_seconds: float = Field(default=0.0, ge=0.0, le=60.0)


class OrdersDispatchPayload(BaseModel):
    subject: str = "cascadya.routing.command"
    timeout_seconds: float = 10.0
    command_payload: dict[str, Any] = Field(default_factory=dict)


def _float_or_none(value: Any) -> float | None:
    return round(float(value), 3) if isinstance(value, (int, float)) else None


def _e2e_percentile(values: list[float], ratio: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return round(values[0], 3)
    ordered = sorted(values)
    position = max(0.0, min(float(ratio), 1.0)) * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    interpolated = ordered[lower] * (1.0 - weight) + ordered[upper] * weight
    return round(interpolated, 3)


def _extract_measurement_values(probe_result: dict[str, Any]) -> dict[str, float | None]:
    summary = probe_result.get("summary")
    if not isinstance(summary, dict):
        return {}

    flow_key = str(probe_result.get("flow_key") or "ems_site").strip().lower()
    if flow_key == "ems_light":
        active_total_with_proxy_ms = _float_or_none(
            summary.get("reconstructed_active_total_ms")
            if summary.get("reconstructed_active_total_ms") is not None
            else summary.get("control_plane_total_ms")
        )
        active_total_without_proxy_ms = _float_or_none(
            (
                float(summary.get("transport_overhead_ms"))
                + float(summary.get("ems_light_connection_rtt_ms"))
            )
            if isinstance(summary.get("transport_overhead_ms"), (int, float))
            and isinstance(summary.get("ems_light_connection_rtt_ms"), (int, float))
            else None
        )
        return {
            "active_total_ms": active_total_with_proxy_ms,
            "active_total_without_proxy_ms": active_total_without_proxy_ms,
            "control_panel_to_broker_ms": _float_or_none(
                summary.get("control_panel_to_broker_active_ms")
                if summary.get("control_panel_to_broker_active_ms") is not None
                else summary.get("transport_overhead_ms")
            ),
            "broker_proxy_internal_ms": _float_or_none(
                summary.get("broker_proxy_internal_ms")
                if summary.get("broker_proxy_internal_ms") is not None
                else summary.get("broker_proxy_handler_ms")
            ),
            "broker_to_target_ms": _float_or_none(summary.get("ems_light_connection_rtt_ms")),
            "observed_total_ms": _float_or_none(summary.get("control_plane_total_ms")),
        }

    active_total_with_proxy_ms = _float_or_none(
        summary.get("reconstructed_active_total_ms")
        if summary.get("reconstructed_active_total_ms") is not None
        else summary.get("control_plane_total_ms")
    )
    active_total_without_proxy_ms = _float_or_none(
        (
            float(summary.get("control_panel_to_broker_active_ms"))
            + float(summary.get("broker_to_ipc_active_ms"))
            + float(summary.get("modbus_simulator_round_trip_ms"))
        )
        if isinstance(summary.get("control_panel_to_broker_active_ms"), (int, float))
        and isinstance(summary.get("broker_to_ipc_active_ms"), (int, float))
        and isinstance(summary.get("modbus_simulator_round_trip_ms"), (int, float))
        else None
    )

    return {
        "active_total_ms": active_total_with_proxy_ms,
        "active_total_without_proxy_ms": active_total_without_proxy_ms,
        "control_panel_to_broker_ms": _float_or_none(
            summary.get("control_panel_to_broker_active_ms")
            if summary.get("control_panel_to_broker_active_ms") is not None
            else summary.get("probe_connection_rtt_ms")
        ),
        "broker_proxy_internal_ms": _float_or_none(summary.get("broker_proxy_internal_ms")),
        "broker_to_ipc_ms": _float_or_none(
            summary.get("broker_to_ipc_active_ms")
            if summary.get("broker_to_ipc_active_ms") is not None
            else summary.get("gateway_connection_rtt_ms")
        ),
        "ipc_to_modbus_ms": _float_or_none(summary.get("modbus_simulator_round_trip_ms")),
        "broker_local_probe_rtt_ms": _float_or_none(summary.get("probe_connection_rtt_ms")),
        "observed_total_ms": _float_or_none(summary.get("control_plane_total_ms")),
    }


def _build_measurement_stats(
    measurement_samples: list[dict[str, Any]],
    *,
    flow_key: str,
) -> list[dict[str, Any]]:
    metric_catalog = (
        [
            ("active_total_ms", "RTT actif reconstruit (avec traitement broker)"),
            ("active_total_without_proxy_ms", "RTT actif reconstruit (sans traitement broker)"),
            ("control_panel_to_broker_ms", "Control Panel <-> Broker VM"),
            ("broker_proxy_internal_ms", "Traitement broker"),
            ("broker_to_target_ms", "Broker VM <-> ems-light"),
            ("observed_total_ms", "Total HTTP observe control panel -> broker"),
        ]
        if flow_key == "ems_light"
        else [
            ("active_total_ms", "RTT actif reconstruit (avec traitement broker)"),
            ("active_total_without_proxy_ms", "RTT actif reconstruit (sans traitement broker)"),
            ("control_panel_to_broker_ms", "Control Panel <-> Broker VM"),
            ("broker_proxy_internal_ms", "Traitement broker"),
            ("broker_to_ipc_ms", "Broker VM <-> Industrial PC"),
            ("ipc_to_modbus_ms", "Industrial PC <-> Modbus Simulator"),
            ("broker_local_probe_rtt_ms", "Broker-local NATS client RTT (/connz)"),
            ("observed_total_ms", "Total HTTP observe control panel -> broker"),
        ]
    )

    stats_rows: list[dict[str, Any]] = []
    for metric_key, metric_label in metric_catalog:
        values = [
            float(sample["values"][metric_key])
            for sample in measurement_samples
            if isinstance(sample.get("values"), dict) and isinstance(sample["values"].get(metric_key), (int, float))
        ]
        if not values:
            stats_rows.append(
                {
                    "key": metric_key,
                    "label": metric_label,
                    "count": 0,
                    "min_ms": None,
                    "avg_ms": None,
                    "median_ms": None,
                    "p95_ms": None,
                    "max_ms": None,
                    "stddev_ms": None,
                }
            )
            continue

        stats_rows.append(
            {
                "key": metric_key,
                "label": metric_label,
                "count": len(values),
                "min_ms": round(min(values), 3),
                "avg_ms": round(statistics.fmean(values), 3),
                "median_ms": _e2e_percentile(values, 0.5),
                "p95_ms": _e2e_percentile(values, 0.95),
                "max_ms": round(max(values), 3),
                "stddev_ms": round(statistics.pstdev(values), 3) if len(values) > 1 else 0.0,
            }
        )
    return stats_rows


def _choose_representative_probe_index(measurement_samples: list[dict[str, Any]]) -> int:
    indexed_values: list[tuple[int, float]] = []
    for index, sample in enumerate(measurement_samples):
        values = sample.get("values")
        if not isinstance(values, dict):
            continue
        candidate = values.get("active_total_ms")
        if isinstance(candidate, (int, float)):
            indexed_values.append((index, float(candidate)))

    if not indexed_values:
        return max(len(measurement_samples) - 1, 0)

    ordered = sorted(indexed_values, key=lambda item: item[1])
    return ordered[len(ordered) // 2][0]


async def _run_single_e2e_probe(
    *,
    flow_key: str,
    probe_context: dict[str, Any],
) -> dict[str, Any]:
    if flow_key == "ems_light":
        return await run_monitoring_connection_probe_via_broker_async(
            broker_probe_url=str(probe_context["broker_probe_url"]),
            broker_probe_token=str(probe_context["broker_probe_token"]),
            broker_probe_ca_cert_path=str(probe_context["broker_probe_ca_cert_path"]),
            connection_name=str(probe_context["connection_name"]),
            flow_label=str(probe_context["flow_label"]),
        )

    if probe_context.get("probe_mode") == "broker_proxy":
        return await run_nats_request_reply_probe_via_broker_async(
            asset_name=str(probe_context["inventory_hostname"]),
            ping_subject=str(probe_context["ping_subject"]),
            broker_probe_url=str(probe_context["broker_probe_url"]),
            broker_probe_token=str(probe_context["broker_probe_token"]),
            broker_probe_ca_cert_path=str(probe_context["broker_probe_ca_cert_path"]),
        )

    return await run_nats_request_reply_probe_async(
        asset_name=str(probe_context["inventory_hostname"]),
        nats_url=str(probe_context["nats_url"]),
        ping_subject=str(probe_context["ping_subject"]),
        ca_cert_path=str(probe_context["ca_cert_path"]),
        client_cert_path=str(probe_context["client_cert_path"]),
        client_key_path=str(probe_context["client_key_path"]),
        monitoring_url=probe_context.get("monitoring_url"),
    )


def _safe_next_path(next_path: str | None) -> str:
    default_path = "/ui/app" if _frontend_build_ready() else "/app"
    if not next_path:
        return default_path
    if not next_path.startswith("/") or next_path.startswith("//"):
        return default_path
    return next_path


def _public_url(request: Request, route_name: str) -> str:
    route_path = str(app.url_path_for(route_name))
    if settings.public_base_url:
        return urljoin(f"{settings.public_base_url.rstrip('/')}/", route_path.lstrip("/"))
    return str(request.url_for(route_name))


def _redirect_to_login(next_path: str) -> RedirectResponse:
    return RedirectResponse(
        f"/auth/login?next={_safe_next_path(next_path)}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _render_login(
    request: Request,
    *,
    error: str | None,
    next_path: str,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    oidc_login_url = None
    if settings.oidc_enabled:
        oidc_login_url = f"/auth/oidc/start?next={_safe_next_path(next_path)}"

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "title": "Login",
            "error": error,
            "next_path": _safe_next_path(next_path),
            "demo_users": tuple(DEFAULT_DEMO_USERS.values()),
            "legacy_login_enabled": settings.enable_legacy_login,
            "oidc_enabled": settings.oidc_enabled,
            "oidc_ready": settings.oidc_ready,
            "oidc_login_url": oidc_login_url,
            "oidc_issuer_url": settings.oidc_issuer_url,
        },
        status_code=status_code,
    )


def _render_forbidden(
    request: Request,
    *,
    user: SessionUser | None,
    message: str,
    required_permission: str | None = None,
    status_code: int = status.HTTP_403_FORBIDDEN,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="unauthorized.html",
        context={
            "title": "Acces refuse",
            "user": user,
            "message": message,
            "required_permission": required_permission,
        },
        status_code=status_code,
    )


def _parse_role_names_csv(role_names: str) -> tuple[str, ...]:
    values = {item.strip() for item in role_names.split(",") if item.strip()}
    return tuple(sorted(values))


def _normalize_email_input(email: str) -> str:
    normalized = email.strip().lower()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise ValueError("L'email fourni n'est pas valide.")
    local_part, _, domain_part = normalized.partition("@")
    if "." not in domain_part or not local_part:
        raise ValueError("L'email fourni n'est pas valide.")
    return normalized


def _frontend_build_ready() -> bool:
    return frontend_index_file.exists()


def _request_path_with_query(request: Request) -> str:
    path = request.url.path
    if request.url.query:
        return f"{path}?{request.url.query}"
    return path


def _extract_bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization")
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _resolve_request_user(request: Request, session: Session) -> SessionUser | None:
    bearer_token = _extract_bearer_token(request)
    if bearer_token:
        return authenticate_bearer_user(
            session,
            bearer_token,
            default_role_names=settings.jit_default_roles,
            bootstrap_admin_emails=settings.bootstrap_admin_emails,
        )

    user = load_session_user(session, request.session.get("user"))
    if user is None and request.session.get("user") is not None:
        request.session.clear()
    return user


def require_api_user(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> SessionUser:
    try:
        user = _resolve_request_user(request, session)
    except OIDCError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from None

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )
    return user


def require_permission(permission_name: str):
    def dependency(user: Annotated[SessionUser, Depends(require_api_user)]) -> SessionUser:
        if not user.has_permission(permission_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission_name}' required",
            )
        return user

    return dependency


def require_admin_user(user: Annotated[SessionUser, Depends(require_api_user)]) -> SessionUser:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user


def _get_html_user_or_response(
    request: Request,
    session: Session,
    *,
    next_path: str,
    required_permission: str,
) -> tuple[SessionUser | None, Response | None]:
    try:
        user = _resolve_request_user(request, session)
    except OIDCError as exc:
        return None, _render_login(
            request,
            error=str(exc),
            next_path=next_path,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    if user is None:
        return None, _redirect_to_login(next_path)
    if not user.is_active:
        request.session.clear()
        return None, _render_forbidden(
            request,
            user=user,
            message="Ton compte existe bien dans le control panel, mais il est desactive.",
        )
    if not user.has_permission(required_permission):
        return None, _render_forbidden(
            request,
            user=user,
            message="Ton identite OIDC est valide, mais tes permissions metier ne permettent pas cette action.",
            required_permission=required_permission,
        )
    return user, None


@app.get("/healthz")
async def healthz() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/healthz/db")
async def healthz_db(
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    if not database_is_healthy(session):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    return JSONResponse({"status": "ok", "database": "ok"})


@app.get("/", response_class=HTMLResponse, response_model=None)
async def index(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> Response:
    try:
        current_user = _resolve_request_user(request, session)
    except OIDCError:
        current_user = None
    destination = "/ui/app" if current_user and _frontend_build_ready() else "/app" if current_user else "/auth/login"
    return RedirectResponse(destination, status_code=status.HTTP_303_SEE_OTHER)


@app.get("/auth/login", response_class=HTMLResponse, response_model=None)
async def login_page(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
    next: str | None = None,
) -> Response:
    try:
        current_user = _resolve_request_user(request, session)
    except OIDCError as exc:
        return _render_login(
            request,
            error=str(exc),
            next_path=_safe_next_path(next),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    if current_user is not None:
        return RedirectResponse(_safe_next_path(next), status_code=status.HTTP_303_SEE_OTHER)

    return _render_login(
        request,
        error=None,
        next_path=_safe_next_path(next),
    )


@app.post("/auth/login", response_class=HTMLResponse, response_model=None)
async def login_submit(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next_path: Annotated[str, Form(alias="next_path")] = "/app",
) -> Response:
    if not settings.enable_legacy_login:
        return _render_login(
            request,
            error="Le login local est desactive. Utilise Keycloak OIDC.",
            next_path=_safe_next_path(next_path),
            status_code=status.HTTP_403_FORBIDDEN,
        )

    user = authenticate_legacy(username=username, password=password)
    if user is None:
        return _render_login(
            request,
            error="Identifiants invalides.",
            next_path=_safe_next_path(next_path),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    request.session.clear()
    request.session["user"] = build_session_payload(user)
    return RedirectResponse(
        _safe_next_path(next_path),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.get("/auth/oidc/start", response_model=None)
async def oidc_start(request: Request, next: str | None = None) -> Response:
    if not settings.oidc_ready:
        return _render_login(
            request,
            error="OIDC n'est pas encore configure. Renseigne les variables Keycloak avant de l'activer.",
            next_path=_safe_next_path(next),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    state = secrets.token_urlsafe(32)
    redirect_uri = _public_url(request, "auth_callback")
    request.session["oidc_auth"] = {
        "state": state,
        "next_path": _safe_next_path(next),
        "redirect_uri": redirect_uri,
    }

    try:
        authorize_url = build_authorization_url(redirect_uri=redirect_uri, state=state)
    except OIDCError as exc:
        request.session.pop("oidc_auth", None)
        return _render_login(
            request,
            error=str(exc),
            next_path=_safe_next_path(next),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return RedirectResponse(authorize_url, status_code=status.HTTP_303_SEE_OTHER)


@app.get("/auth/callback", name="auth_callback", response_model=None)
async def auth_callback(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> Response:
    oidc_auth = request.session.pop("oidc_auth", None)
    next_path = _safe_next_path((oidc_auth or {}).get("next_path"))

    if error:
        message = error_description or error
        return _render_login(
            request,
            error=f"Keycloak a refuse la connexion: {message}",
            next_path=next_path,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if not isinstance(oidc_auth, dict) or oidc_auth.get("state") != state or not code:
        return _render_login(
            request,
            error="Le callback OIDC est invalide ou a expire. Relance la connexion.",
            next_path=next_path,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    redirect_uri = oidc_auth.get("redirect_uri")
    if not isinstance(redirect_uri, str) or not redirect_uri:
        redirect_uri = _public_url(request, "auth_callback")

    try:
        tokens = exchange_authorization_code(code=code, redirect_uri=redirect_uri)
        access_token = tokens.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise OIDCError("OIDC token response does not contain an access_token.")
        claims = fetch_userinfo(access_token=access_token)
        user = sync_user_from_oidc_claims(
            session,
            claims,
            default_role_names=settings.jit_default_roles,
            bootstrap_admin_emails=settings.bootstrap_admin_emails,
        )
    except OIDCError as exc:
        return _render_login(
            request,
            error=str(exc),
            next_path=next_path,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        request.session.clear()
        return _render_forbidden(
            request,
            user=user,
            message="Le compte miroir a bien ete cree, mais il est desactive dans le RBAC du control panel.",
        )

    request.session.clear()
    request.session["user"] = build_session_payload(
        user,
        id_token=tokens.get("id_token") if isinstance(tokens.get("id_token"), str) else None,
    )
    return RedirectResponse(next_path, status_code=status.HTTP_303_SEE_OTHER)


@app.post("/auth/logout", response_model=None)
async def logout(request: Request) -> Response:
    id_token = extract_id_token(request.session.get("user"))
    request.session.clear()

    try:
        logout_url = build_logout_url(
            post_logout_redirect_uri=_public_url(request, "login_page"),
            id_token_hint=id_token,
        )
    except OIDCError:
        logout_url = None
    if logout_url:
        return RedirectResponse(logout_url, status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse("/auth/login", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/ui", include_in_schema=False)
@app.get("/ui/", include_in_schema=False)
async def frontend_entry(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> Response:
    if not _frontend_build_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Frontend build is not available. Run npm run build in auth_prototype/frontend.",
        )

    user, response = _get_html_user_or_response(
        request,
        session,
        next_path=_request_path_with_query(request),
        required_permission="dashboard:read",
    )
    if response is not None:
        return response
    assert user is not None
    return FileResponse(frontend_index_file)


@app.get("/ui/{full_path:path}", include_in_schema=False)
async def frontend_routes(
    full_path: str,
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> Response:
    del full_path
    if not _frontend_build_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Frontend build is not available. Run npm run build in auth_prototype/frontend.",
        )

    user, response = _get_html_user_or_response(
        request,
        session,
        next_path=_request_path_with_query(request),
        required_permission="dashboard:read",
    )
    if response is not None:
        return response
    assert user is not None
    return FileResponse(frontend_index_file)


@app.get("/app", response_class=HTMLResponse, response_model=None)
async def app_home(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> Response:
    user, response = _get_html_user_or_response(
        request,
        session,
        next_path="/app",
        required_permission="dashboard:read",
    )
    if response is not None:
        return response
    assert user is not None
    if _frontend_build_ready():
        return RedirectResponse("/ui/app", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "title": "Dashboard",
            "user": user,
            "secure_cookies": settings.secure_cookies,
            "oidc_enabled": settings.oidc_enabled,
        },
    )


@app.get("/admin", response_class=HTMLResponse, response_model=None)
async def admin_page(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> Response:
    user, response = _get_html_user_or_response(
        request,
        session,
        next_path="/admin",
        required_permission="user:read",
    )
    if response is not None:
        return response
    assert user is not None

    if not _frontend_build_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Frontend build is not available. Run npm run build in auth_prototype/frontend.",
        )

    return RedirectResponse("/ui/admin", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/api/me")
async def api_me(user: Annotated[SessionUser, Depends(require_api_user)]) -> JSONResponse:
    return JSONResponse(serialize_user(user))


@app.get("/api/ui/config")
async def api_ui_config(user: Annotated[SessionUser, Depends(require_api_user)]) -> JSONResponse:
    del user
    return JSONResponse(
        {
            "dashboards": {
                "wazuh": {
                    "url": settings.wazuh_dashboard_url,
                }
            }
        }
    )


@app.get("/api/alerts/live")
async def api_live_alerts(
    user: Annotated[SessionUser, Depends(require_permission("dashboard:read"))],
) -> JSONResponse:
    del user
    return JSONResponse(await build_live_alerts_snapshot(settings))


@app.get("/api/admin/audit")
async def api_admin_audit(
    user: Annotated[SessionUser, Depends(require_permission("audit:read"))],
) -> JSONResponse:
    return JSONResponse(
        {
            "viewer": user.username,
            "entries": [
                {
                    "at": "2026-03-26T10:00:00Z",
                    "action": "site.provision.requested",
                    "actor": "operator.luc",
                },
                {
                    "at": "2026-03-26T10:02:00Z",
                    "action": "central.config.publish",
                    "actor": "control-plane",
                },
            ],
        }
    )


@app.get("/api/admin/rbac/catalog")
async def api_admin_rbac_catalog(
    user: Annotated[SessionUser, Depends(require_permission("user:read"))],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    del user
    try:
        catalog = fetch_rbac_catalog(session)
    except (OperationalError, ProgrammingError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RBAC schema is not initialized",
        ) from None
    return JSONResponse(catalog)


@app.get("/api/admin/users")
async def api_admin_users(
    user: Annotated[SessionUser, Depends(require_permission("user:read"))],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    del user
    return JSONResponse({"users": [serialize_user(item) for item in list_managed_users(session)]})


@app.post("/api/admin/users/invite")
async def api_admin_invite_user(
    payload: UserInvitePayload,
    session: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[SessionUser, Depends(require_permission("user:write"))],
) -> JSONResponse:
    normalized_role_names = tuple(sorted({name.strip() for name in payload.role_names if name.strip()}))
    if normalized_role_names and not current_user.has_permission("role:assign"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'role:assign' required to assign roles during invitation.",
        )

    try:
        normalized_email = _normalize_email_input(payload.email)
        keycloak_user = provision_keycloak_user(
            email=normalized_email,
            first_name=payload.first_name,
            last_name=payload.last_name,
        )
        managed_user = provision_managed_user(
            session,
            keycloak_uuid=keycloak_user.keycloak_uuid,
            email=keycloak_user.email,
            preferred_username=keycloak_user.username,
            display_name=keycloak_user.display_name,
            role_names=normalized_role_names,
            is_active=True,
        )
    except (ValueError, KeycloakAdminError, ManagedRoleError, ManagedUserProvisionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None

    response_payload: dict[str, object] = {
        "user": serialize_user(managed_user),
    }
    return JSONResponse(response_payload)


@app.get("/api/admin/users/{user_id}")
async def api_admin_user_detail(
    user: Annotated[SessionUser, Depends(require_permission("user:read"))],
    session: Annotated[Session, Depends(get_db_session)],
    user_id: int = 0,
) -> JSONResponse:
    del user
    try:
        managed_user = next(item for item in list_managed_users(session) if item.id == user_id)
    except StopIteration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown user",
        ) from None
    return JSONResponse(serialize_user(managed_user))


@app.put("/api/admin/users/{user_id}")
async def api_admin_user_profile(
    payload: UserProfileUpdatePayload,
    user_id: int,
    session: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[SessionUser, Depends(require_admin_user)],
) -> JSONResponse:
    del current_user
    try:
        normalized_email = _normalize_email_input(payload.email)
        existing_user = get_managed_user(session, user_id)
        keycloak_user = update_keycloak_user(
            keycloak_uuid=existing_user.keycloak_uuid,
            email=normalized_email,
            first_name=payload.first_name,
            last_name=payload.last_name,
        )
        managed_user = update_managed_user_profile(
            session,
            user_id,
            keycloak_uuid=keycloak_user.keycloak_uuid,
            email=keycloak_user.email,
            preferred_username=keycloak_user.username,
            display_name=keycloak_user.display_name,
            is_active=existing_user.is_active,
        )
    except (ValueError, KeycloakAdminError, ManagedUserNotFoundError, ManagedUserProvisionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None
    return JSONResponse(serialize_user(managed_user))


@app.put("/api/admin/users/{user_id}/roles")
async def api_admin_user_roles(
    payload: UserRoleUpdatePayload,
    user_id: int,
    session: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[SessionUser, Depends(require_permission("role:assign"))],
) -> JSONResponse:
    del current_user
    normalized_role_names = tuple(sorted({name.strip() for name in payload.role_names if name.strip()}))
    try:
        managed_user = replace_user_roles(session, user_id, normalized_role_names)
    except (ManagedRoleError, ManagedUserNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None
    return JSONResponse(serialize_user(managed_user))


@app.put("/api/admin/users/{user_id}/status")
async def api_admin_user_status(
    payload: UserActiveUpdatePayload,
    user_id: int,
    session: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[SessionUser, Depends(require_permission("user:write"))],
) -> JSONResponse:
    del current_user
    try:
        managed_user = set_user_active(session, user_id, is_active=payload.is_active)
    except ManagedUserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None
    return JSONResponse(serialize_user(managed_user))


@app.delete("/api/admin/users/{user_id}")
async def api_admin_delete_user(
    user_id: int,
    session: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[SessionUser, Depends(require_admin_user)],
) -> JSONResponse:
    if current_user.user_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own admin account from this endpoint.",
        )

    try:
        managed_user = get_managed_user(session, user_id)
        deleted_email = managed_user.email
        keycloak_deleted = delete_keycloak_user(
            keycloak_uuid=managed_user.keycloak_uuid,
            ignore_missing=True,
        )
        delete_managed_user(session, user_id)
    except (KeycloakAdminError, ManagedUserNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None

    response_payload: dict[str, object] = {
        "status": "ok",
        "user_id": user_id,
        "email": deleted_email,
        "keycloak_user_deleted": keycloak_deleted,
    }
    if not keycloak_deleted:
        response_payload["warning"] = "The Keycloak account was already missing."
    return JSONResponse(response_payload)


@app.get("/api/sites")
async def api_sites(
    user: Annotated[SessionUser, Depends(require_permission("site:read"))],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    del user
    return JSONResponse({"sites": [serialize_site(site) for site in list_sites(session)]})


@app.post("/api/sites")
async def api_create_site(
    payload: SiteUpsertPayload,
    session: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[SessionUser, Depends(require_permission("site:write"))],
) -> JSONResponse:
    del current_user
    try:
        site = create_site(
            session,
            code=payload.code,
            name=payload.name,
            customer_name=payload.customer_name,
            country=payload.country,
            city=payload.city,
            timezone_name=payload.timezone,
            address_line1=payload.address_line1,
            notes=payload.notes,
            is_active=payload.is_active,
        )
    except FleetValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    return JSONResponse(serialize_site(site), status_code=status.HTTP_201_CREATED)


@app.get("/api/sites/{site_id}")
async def api_site_detail(
    site_id: int,
    user: Annotated[SessionUser, Depends(require_permission("site:read"))],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    del user
    try:
        site = get_site(session, site_id)
    except FleetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    return JSONResponse(serialize_site(site))


@app.put("/api/sites/{site_id}")
async def api_update_site(
    site_id: int,
    payload: SiteUpsertPayload,
    session: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[SessionUser, Depends(require_permission("site:write"))],
) -> JSONResponse:
    del current_user
    try:
        site = update_site(
            session,
            site_id,
            code=payload.code,
            name=payload.name,
            customer_name=payload.customer_name,
            country=payload.country,
            city=payload.city,
            timezone_name=payload.timezone,
            address_line1=payload.address_line1,
            notes=payload.notes,
            is_active=payload.is_active,
        )
    except FleetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    except FleetValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    return JSONResponse(serialize_site(site))


@app.put("/api/sites/{site_id}/status")
async def api_site_status(
    site_id: int,
    payload: SiteStatusUpdatePayload,
    session: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[SessionUser, Depends(require_permission("site:write"))],
) -> JSONResponse:
    del current_user
    try:
        site = set_site_active(session, site_id, is_active=payload.is_active)
    except FleetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    return JSONResponse(serialize_site(site))


@app.get("/api/inventory/assets")
async def api_inventory_assets(
    user: Annotated[SessionUser, Depends(require_permission("inventory:read"))],
    session: Annotated[Session, Depends(get_db_session)],
    site_id: int | None = None,
    registration_status: str | None = None,
) -> JSONResponse:
    del user
    assets = list_inventory_assets(session, site_id=site_id, registration_status=registration_status)
    return JSONResponse({"assets": [serialize_inventory_asset(asset) for asset in assets]})


@app.get("/api/inventory/assets/{asset_id}")
async def api_inventory_asset_detail(
    asset_id: int,
    user: Annotated[SessionUser, Depends(require_permission("inventory:read"))],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    del user
    try:
        asset = get_inventory_asset(session, asset_id)
    except FleetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    return JSONResponse(serialize_inventory_asset(asset))


@app.delete("/api/inventory/assets/{asset_id}")
async def api_delete_inventory_asset(
    asset_id: int,
    session: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[SessionUser, Depends(require_api_user)],
) -> JSONResponse:
    try:
        asset = get_inventory_asset(session, asset_id)
    except FleetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None

    if asset.registration_status == "discovered":
        if not current_user.has_permission("inventory:scan"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission 'inventory:scan' required to delete a discovered asset.",
            )
    elif not current_user.has_permission("provision:prepare"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'provision:prepare' required to delete a registered asset.",
        )

    try:
        result = delete_inventory_asset(session, asset_id)
    except FleetValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    return JSONResponse(result)


@app.get("/api/inventory/scans")
async def api_inventory_scans(
    user: Annotated[SessionUser, Depends(require_permission("inventory:read"))],
    session: Annotated[Session, Depends(get_db_session)],
    site_id: int | None = None,
) -> JSONResponse:
    del user
    scans = list_inventory_scans(session, site_id=site_id)
    return JSONResponse({"scans": [serialize_inventory_scan(scan) for scan in scans]})


@app.get("/api/inventory/scans/{scan_id}")
async def api_inventory_scan_detail(
    scan_id: int,
    user: Annotated[SessionUser, Depends(require_permission("inventory:read"))],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    del user
    try:
        scan = get_inventory_scan(session, scan_id)
    except FleetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    return JSONResponse(serialize_inventory_scan(scan))


@app.post("/api/inventory/scans")
async def api_request_inventory_scan(
    payload: InventoryScanRequestPayload,
    session: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[SessionUser, Depends(require_permission("inventory:scan"))],
) -> JSONResponse:
    try:
        scan, asset = request_inventory_scan(
            session,
            settings=settings,
            requested_by_user_id=current_user.user_id,
            site_id=payload.site_id,
            target_ip=payload.target_ip,
            teltonika_router_ip=payload.teltonika_router_ip,
            target_label=payload.target_label,
            ssh_username=payload.ssh_username,
            ssh_port=payload.ssh_port,
            downstream_probe_ip=payload.downstream_probe_ip,
            asset_type=payload.asset_type,
        )
    except FleetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    except FleetValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    return JSONResponse(
        {
            "scan": serialize_inventory_scan(scan),
            "asset": serialize_inventory_asset(asset),
        },
        status_code=status.HTTP_201_CREATED,
    )


@app.post("/api/inventory/assets/{asset_id}/register")
async def api_register_inventory_asset(
    asset_id: int,
    payload: AssetRegistrationPayload,
    session: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[SessionUser, Depends(require_permission("provision:prepare"))],
) -> JSONResponse:
    if payload.site_id is None and not current_user.has_permission("site:write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'site:write' required to create a new site during onboarding.",
        )

    try:
        asset = register_inventory_asset(
            session,
            settings=settings,
            asset_id=asset_id,
            site_id=payload.site_id,
            site_code=payload.site_code,
            site_name=payload.site_name,
            customer_name=payload.customer_name,
            country=payload.country,
            city=payload.city,
            timezone_name=payload.timezone,
            address_line1=payload.address_line1,
            site_notes=payload.site_notes,
            hostname=payload.hostname,
            inventory_hostname=payload.inventory_hostname,
            naming_slug=payload.naming_slug,
            management_ip=payload.management_ip,
            teltonika_router_ip=payload.teltonika_router_ip,
            management_interface=payload.management_interface,
            uplink_interface=payload.uplink_interface,
            gateway_ip=payload.gateway_ip,
            wireguard_address=payload.wireguard_address,
            notes=payload.notes,
            provisioning_vars=payload.provisioning_vars,
        )
    except FleetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    except FleetValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    return JSONResponse(serialize_inventory_asset(asset))


@app.post("/api/e2e/tests")
async def api_run_e2e_test(
    payload: E2ETestRequestPayload,
    session: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[SessionUser, Depends(require_permission("inventory:scan"))],
) -> JSONResponse:
    del current_user
    try:
        flow_key = (payload.flow_key or "ems_site").strip().lower()

        if flow_key == "ems_light":
            probe_context = build_ems_light_e2e_probe_context(settings=settings)
        else:
            if payload.asset_id is None:
                raise FleetValidationError("Selectionne d'abord un industrial PC pour le flux ems-site.")

            asset = get_inventory_asset(session, payload.asset_id)
            probe_context = build_edge_agent_e2e_probe_context(
                asset,
                settings=settings,
                site_id=payload.site_id,
            )

        requested_sample_count = int(payload.sample_count or 1)
        requested_sample_interval_seconds = float(payload.sample_interval_seconds or 0.0)
        measurement_samples: list[dict[str, Any]] = []
        raw_probe_results: list[dict[str, Any]] = []

        for sample_index in range(requested_sample_count):
            probe_result = await _run_single_e2e_probe(flow_key=flow_key, probe_context=probe_context)
            raw_probe_results.append(probe_result)
            measurement_samples.append(
                {
                    "index": sample_index + 1,
                    "tested_at": probe_result.get("tested_at"),
                    "request_id": probe_result.get("request_id"),
                    "values": _extract_measurement_values(probe_result),
                }
            )
            if sample_index + 1 < requested_sample_count and requested_sample_interval_seconds > 0:
                await asyncio.sleep(requested_sample_interval_seconds)
    except FleetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    except FleetValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    except NatsE2EProbeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from None

    representative_index = _choose_representative_probe_index(measurement_samples)
    representative_probe = raw_probe_results[representative_index]
    measurement_batch = {
        "requested_count": requested_sample_count,
        "completed_count": len(measurement_samples),
        "representative_index": representative_index + 1,
        "flow_key": flow_key,
        "sample_interval_seconds": round(requested_sample_interval_seconds, 3),
        "samples": measurement_samples,
        "stats": _build_measurement_stats(measurement_samples, flow_key=flow_key),
    }

    return JSONResponse(
        {
            "site": probe_context["site"],
            "asset": probe_context["asset"],
            "probe": representative_probe,
            "measurement_batch": measurement_batch,
        }
    )


@app.get("/api/orders/live")
async def api_orders_live(
    current_user: Annotated[SessionUser, Depends(require_permission("inventory:read"))],
    limit: int = 50,
) -> JSONResponse:
    del current_user
    try:
        probe_context = build_orders_probe_context(settings=settings)
        orders_result = await run_orders_probe_via_broker_async(
            broker_probe_url=str(probe_context["broker_probe_url"]),
            broker_probe_token=str(probe_context["broker_probe_token"]),
            broker_probe_ca_cert_path=str(probe_context["broker_probe_ca_cert_path"]),
            limit=max(1, min(limit, 500)),
        )
    except FleetValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    except NatsE2EProbeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from None

    return JSONResponse(orders_result)


@app.post("/api/orders/dispatch")
async def api_orders_dispatch(
    payload: OrdersDispatchPayload,
    current_user: Annotated[SessionUser, Depends(require_permission("inventory:scan"))],
) -> JSONResponse:
    del current_user
    try:
        probe_context = build_orders_probe_context(settings=settings)
        dispatch_result = await run_nats_command_request_via_broker_async(
            broker_probe_url=str(probe_context["broker_probe_url"]),
            broker_probe_token=str(probe_context["broker_probe_token"]),
            broker_probe_ca_cert_path=str(probe_context["broker_probe_ca_cert_path"]),
            command_subject=payload.subject,
            command_payload=payload.command_payload,
            timeout_seconds=payload.timeout_seconds,
        )
    except FleetValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    except NatsE2EProbeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from None

    return JSONResponse(dispatch_result)


@app.get("/api/provisioning/jobs")
async def api_provisioning_jobs(
    user: Annotated[SessionUser, Depends(require_permission("provision:prepare"))],
    session: Annotated[Session, Depends(get_db_session)],
    site_id: int | None = None,
) -> JSONResponse:
    del user
    jobs = list_provisioning_jobs(session, site_id=site_id)
    return JSONResponse(
        {
            "execution_mode": settings.provisioning_execution_mode,
            "playbook_root": settings.provisioning_playbook_root,
            "default_workflow_key": DEFAULT_PROVISIONING_WORKFLOW_KEY,
            "workflow_catalog": list_provisioning_workflows(),
            "jobs": [serialize_provisioning_job(job) for job in jobs],
        }
    )


@app.get("/api/provisioning/jobs/{job_id}")
async def api_provisioning_job_detail(
    job_id: int,
    user: Annotated[SessionUser, Depends(require_permission("provision:prepare"))],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    del user
    try:
        job = get_provisioning_job(session, job_id)
    except FleetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    return JSONResponse(serialize_provisioning_job(job))


@app.post("/api/provisioning/jobs")
async def api_prepare_provisioning_job(
    payload: ProvisioningJobCreatePayload,
    session: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[SessionUser, Depends(require_permission("provision:prepare"))],
) -> JSONResponse:
    try:
        job = prepare_provisioning_job(
            session,
            settings=settings,
            requested_by_user_id=current_user.user_id,
            asset_id=payload.asset_id,
            playbook_name=payload.playbook_name or settings.provisioning_default_playbook,
            inventory_group=payload.inventory_group,
            workflow_key=payload.workflow_key,
            dispatch_mode=payload.dispatch_mode,
            remote_unlock_vault_secret_value=payload.remote_unlock_vault_secret_value,
            remote_unlock_vault_secret_confirm_overwrite=payload.remote_unlock_vault_secret_confirm_overwrite,
        )
    except FleetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    except FleetValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    return JSONResponse(serialize_provisioning_job(job), status_code=status.HTTP_201_CREATED)


@app.post("/api/provisioning/jobs/{job_id}/run")
def api_run_provisioning_job(
    job_id: int,
    session: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[SessionUser, Depends(require_permission("provision:run"))],
    payload: ProvisioningJobRunPayload | None = None,
) -> JSONResponse:
    del current_user
    try:
        job = run_provisioning_job(
            session,
            job_id=job_id,
            settings=settings,
            requested_step_key=payload.step_key if payload else None,
        )
    except FleetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    except FleetValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur interne pendant l'execution du provisioning: {exc.__class__.__name__}: {exc}",
        ) from exc
    return JSONResponse(serialize_provisioning_job(job))


@app.post("/api/provisioning/jobs/{job_id}/cancel")
async def api_cancel_provisioning_job(
    job_id: int,
    session: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[SessionUser, Depends(require_permission("provision:cancel"))],
) -> JSONResponse:
    del current_user
    try:
        job = cancel_provisioning_job(session, job_id)
    except FleetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    except FleetValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    return JSONResponse(serialize_provisioning_job(job))


@app.delete("/api/provisioning/jobs/{job_id}")
async def api_delete_provisioning_job(
    job_id: int,
    session: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[SessionUser, Depends(require_permission("provision:cancel"))],
) -> JSONResponse:
    del current_user
    try:
        result = delete_provisioning_job(session, job_id)
    except FleetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    except FleetValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    return JSONResponse(result)
