from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any
from urllib.parse import quote, urljoin, urlparse

from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for

from .auth import (
    build_dev_identity,
    build_identity_from_claims,
    decode_jwt_payload,
    identity_has_any_tag,
    merge_claim_sets,
    normalize_session_identity,
    safe_next_path,
)
from .catalog import SECTION_DEFS, build_cards, get_section
from .config import Settings, get_settings
from .oidc import OIDCError, build_authorization_url, build_logout_url, exchange_authorization_code, fetch_userinfo


DEV_PROFILES: dict[str, dict[str, Any]] = {
    "operator": {
        "username": "operator",
        "display_name": "Operator Demo",
        "email": "operator@cascadya.internal",
        "roles": ("portal-access", "control-panel-user", "monitoring-user", "grafana-user"),
        "label": "Operator",
        "description": "Portal access with operations and monitoring cards.",
    },
    "admin": {
        "username": "admin",
        "display_name": "Portal Admin Demo",
        "email": "admin@cascadya.internal",
        "roles": (
            "portal-access",
            "portal-admin",
            "control-panel-user",
            "monitoring-user",
            "grafana-user",
            "wazuh-user",
        ),
        "label": "Portal Admin",
        "description": "Full portal visibility, including security and identity administration.",
    },
}


def create_app(settings: Settings | None = None) -> Flask:
    active_settings = settings or get_settings()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.update(
        SECRET_KEY=active_settings.session_secret,
        SESSION_COOKIE_NAME=active_settings.session_cookie_name,
        SESSION_COOKIE_SECURE=active_settings.secure_cookies,
        SESSION_COOKIE_SAMESITE=active_settings.same_site,
        PERMANENT_SESSION_LIFETIME=timedelta(seconds=active_settings.session_ttl_seconds),
        PORTAL_SETTINGS=active_settings,
    )

    @app.before_request
    def _mark_session_permanent() -> None:
        session.permanent = True

    @app.get("/api/healthz")
    def api_healthz() -> Any:
        return jsonify({"status": "ok"})

    @app.get("/api/status")
    def api_status() -> Any:
        current_user = _current_user()
        return jsonify(
            {
                "status": "ok",
                "app_name": _settings().app_name,
                "environment": _settings().environment_label,
                "oidc_enabled": _settings().oidc_enabled,
                "oidc_ready": _settings().oidc_ready,
                "authenticated": current_user is not None,
                "user": _public_user_payload(current_user),
            }
        )

    @app.get("/api/me")
    def api_me() -> Any:
        current_user, response = _require_user()
        if response is not None:
            return response
        return jsonify(_public_user_payload(current_user))

    @app.get("/auth/login", endpoint="login_page")
    def login_page() -> Any:
        next_path = safe_next_path(request.args.get("next"), _settings().default_next_path)
        current_user = _current_user()
        if current_user is not None:
            return redirect(next_path)
        if _settings().oidc_ready:
            return redirect(url_for("oidc_start", next=next_path))
        return render_template(
            "login.html",
            title=f"{_settings().app_name} | Login",
            page_name="login",
            next_path=next_path,
            oidc_enabled=_settings().oidc_enabled,
            oidc_ready=_settings().oidc_ready,
            oidc_issuer_url=_settings().oidc_issuer_url,
            required_tags=_settings().required_tags,
            dev_profiles=_dev_profiles_for_template(),
            settings=_settings(),
        )

    @app.post("/auth/dev-login/<profile_key>", endpoint="dev_login")
    def dev_login(profile_key: str) -> Any:
        if not _settings().enable_dev_login:
            abort(404)
        profile = DEV_PROFILES.get(profile_key)
        if profile is None:
            abort(404)

        next_path = safe_next_path(request.form.get("next"), _settings().default_next_path)
        session.clear()
        session["user"] = build_dev_identity(
            username=profile["username"],
            display_name=profile["display_name"],
            email=profile["email"],
            roles=profile["roles"],
        )
        return redirect(next_path)

    @app.get("/auth/oidc/start", endpoint="oidc_start")
    def oidc_start() -> Any:
        next_path = safe_next_path(request.args.get("next"), _settings().default_next_path)
        if not _settings().oidc_ready:
            return _render_login(next_path, "OIDC is not fully configured for this portal instance."), 503

        state = secrets.token_urlsafe(32)
        redirect_uri = _public_url("auth_callback")
        session["oidc_auth"] = {
            "state": state,
            "next_path": next_path,
            "redirect_uri": redirect_uri,
        }

        try:
            authorize_url = build_authorization_url(
                _settings(),
                redirect_uri=redirect_uri,
                state=state,
            )
        except OIDCError as exc:
            session.pop("oidc_auth", None)
            return _render_login(next_path, str(exc)), 503
        return redirect(authorize_url, code=303)

    @app.get("/auth/callback", endpoint="auth_callback")
    def auth_callback() -> Any:
        oidc_auth = session.pop("oidc_auth", None)
        next_path = safe_next_path((oidc_auth or {}).get("next_path"), _settings().default_next_path)
        if request.args.get("error"):
            message = request.args.get("error_description") or request.args["error"]
            return _render_login(next_path, f"Keycloak rejected the login flow: {message}"), 401

        state = request.args.get("state")
        code = request.args.get("code")
        if not isinstance(oidc_auth, dict) or oidc_auth.get("state") != state or not code:
            return _render_login(next_path, "The OIDC callback is invalid or expired. Start the login flow again."), 400

        redirect_uri = oidc_auth.get("redirect_uri")
        if not isinstance(redirect_uri, str) or not redirect_uri:
            redirect_uri = _public_url("auth_callback")

        try:
            tokens = exchange_authorization_code(_settings(), code=code, redirect_uri=redirect_uri)
            access_token = tokens.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise OIDCError("OIDC token response does not contain an access_token.")

            id_token = tokens.get("id_token")
            if id_token is not None and not isinstance(id_token, str):
                id_token = None

            userinfo_claims = fetch_userinfo(_settings(), access_token=access_token)
            merged_claims = merge_claim_sets(
                decode_jwt_payload(access_token),
                decode_jwt_payload(id_token),
                userinfo_claims,
            )
            identity = build_identity_from_claims(
                merged_claims,
                client_id=_settings().oidc_client_id,
                auth_source="oidc",
                id_token=id_token,
            )
        except OIDCError as exc:
            return _render_login(next_path, str(exc)), 401

        session.clear()
        session["user"] = identity
        if _settings().required_tags and not identity_has_any_tag(identity, _settings().required_tags):
            return _render_forbidden(
                identity,
                message=(
                    "Your Keycloak session is valid, but this portal expects one of the access tags "
                    f"{', '.join(_settings().required_tags)} before showing cards."
                ),
            )
        return redirect(next_path, code=303)

    @app.route("/auth/logout", methods=["GET", "POST"], endpoint="logout")
    def logout() -> Any:
        current_user = _current_user()
        id_token = current_user.get("id_token") if current_user else None
        session.clear()
        try:
            logout_url = build_logout_url(
                _settings(),
                post_logout_redirect_uri=_public_url("login_page"),
                id_token_hint=id_token if isinstance(id_token, str) else None,
            )
        except OIDCError:
            logout_url = None
        return redirect(logout_url or url_for("login_page"), code=303)

    @app.get("/", endpoint="home")
    def home() -> Any:
        current_user, response = _require_user()
        if response is not None:
            return response
        sections = [section for section in _build_section_payloads(current_user) if section["card_count"]]
        return render_template(
            "hub.html",
            title=f"{_settings().app_name} | Home",
            page_name="home",
            hero_title="One login. Native tools. Clear routes.",
            hero_copy=(
                "The portal stays a hub, not a mega reverse proxy. Each card opens the existing "
                "service on its own DNS and reuses the Keycloak session when available."
            ),
            page_intro="A central hub for Cascadya services after Keycloak authentication.",
            sections=sections,
            active_nav="home",
            nav_items=_nav_items(_section_counts(current_user), active_key="home"),
            user=current_user,
            settings=_settings(),
        )

    @app.get("/operations", endpoint="operations")
    def operations() -> Any:
        return _render_section_page("operations")

    @app.get("/monitoring", endpoint="monitoring")
    def monitoring() -> Any:
        return _render_section_page("monitoring")

    @app.get("/security", endpoint="security")
    def security() -> Any:
        return _render_section_page("security")

    @app.get("/platform", endpoint="platform")
    def platform() -> Any:
        return _render_section_page("platform")

    def _render_section_page(section_key: str) -> Any:
        section = get_section(section_key)
        if section is None:
            abort(404)

        current_user, response = _require_user()
        if response is not None:
            return response
        payloads = _build_section_payloads(current_user)
        current_section = next(item for item in payloads if item["key"] == section_key)
        return render_template(
            "hub.html",
            title=f"{_settings().app_name} | {section.title}",
            page_name=section.key,
            hero_title=section.title,
            hero_copy=section.description,
            page_intro=section.strapline,
            sections=[current_section],
            active_nav=section.key,
            nav_items=_nav_items(_section_counts(current_user), active_key=section.key),
            user=current_user,
            settings=_settings(),
        )

    def _settings() -> Settings:
        return app.config["PORTAL_SETTINGS"]

    def _current_user() -> dict[str, Any] | None:
        return normalize_session_identity(session.get("user"))

    def _require_user() -> tuple[dict[str, Any] | None, Any | None]:
        current_user = _current_user()
        if current_user is None:
            return None, _redirect_to_login()
        if _settings().required_tags and not identity_has_any_tag(current_user, _settings().required_tags):
            return current_user, _render_forbidden(
                current_user,
                message=(
                    "This portal is restricted to users carrying one of the access tags "
                    f"{', '.join(_settings().required_tags)}."
                ),
            )
        return current_user, None

    def _render_login(next_path: str, login_error: str | None = None) -> str:
        return render_template(
            "login.html",
            title=f"{_settings().app_name} | Login",
            page_name="login",
            next_path=next_path,
            oidc_enabled=_settings().oidc_enabled,
            oidc_ready=_settings().oidc_ready,
            oidc_issuer_url=_settings().oidc_issuer_url,
            required_tags=_settings().required_tags,
            dev_profiles=_dev_profiles_for_template(),
            login_error=login_error,
            settings=_settings(),
        )

    def _build_section_payloads(current_user: dict[str, Any]) -> list[dict[str, Any]]:
        section_payloads: list[dict[str, Any]] = []
        cards = build_cards(_settings())
        for section in SECTION_DEFS:
            card_views: list[dict[str, Any]] = []
            accessible_count = 0
            locked_count = 0
            for card in cards:
                if card.section != section.key:
                    continue
                is_accessible = identity_has_any_tag(current_user, card.required_tags)
                if not is_accessible and not card.preview_when_locked:
                    continue
                if is_accessible:
                    accessible_count += 1
                else:
                    locked_count += 1
                card_views.append(
                    {
                        "key": card.key,
                        "title": card.title,
                        "href": card.href,
                        "host": _host_label(card.href),
                        "badge": card.badge,
                        "accent": card.accent,
                        "description": card.description,
                        "audience": card.audience,
                        "required_tags": card.required_tags,
                        "is_accessible": is_accessible,
                    }
                )

            section_payloads.append(
                {
                    "key": section.key,
                    "title": section.title,
                    "strapline": section.strapline,
                    "description": section.description,
                    "href": url_for(section.key),
                    "cards": card_views,
                    "card_count": len(card_views),
                    "accessible_count": accessible_count,
                    "locked_count": locked_count,
                }
            )
        return section_payloads

    def _section_counts(current_user: dict[str, Any]) -> dict[str, int]:
        return {
            section["key"]: section["accessible_count"]
            for section in _build_section_payloads(current_user)
        }

    def _nav_items(section_counts: dict[str, int], *, active_key: str | None) -> list[dict[str, Any]]:
        items = [
            {
                "key": "home",
                "label": "Home",
                "href": url_for("home"),
                "count": sum(section_counts.values()),
                "is_active": active_key == "home",
            }
        ]
        for section in SECTION_DEFS:
            items.append(
                {
                    "key": section.key,
                    "label": section.title,
                    "href": url_for(section.key),
                    "count": section_counts.get(section.key, 0),
                    "is_active": active_key == section.key,
                }
            )
        return items

    def _redirect_to_login() -> Any:
        next_path = quote(_request_path_with_query(), safe="")
        return redirect(f"{url_for('login_page')}?next={next_path}", code=303)

    def _render_forbidden(current_user: dict[str, Any], *, message: str) -> Any:
        return (
            render_template(
                "forbidden.html",
                title=f"{_settings().app_name} | Access denied",
                page_name="forbidden",
                message=message,
                user=current_user,
                nav_items=_nav_items(_section_counts(current_user), active_key=None),
                settings=_settings(),
            ),
            403,
        )

    def _public_url(endpoint: str) -> str:
        route_path = url_for(endpoint)
        if _settings().public_base_url:
            return urljoin(f"{_settings().public_base_url.rstrip('/')}/", route_path.lstrip("/"))
        return request.url_root.rstrip("/") + route_path

    def _request_path_with_query() -> str:
        query = request.query_string.decode("utf-8")
        if query:
            return f"{request.path}?{query}"
        return request.path

    def _public_user_payload(current_user: dict[str, Any] | None) -> dict[str, Any] | None:
        if current_user is None:
            return None
        return {
            "username": current_user["username"],
            "display_name": current_user["display_name"],
            "email": current_user["email"],
            "roles": current_user["roles"],
            "groups": current_user["groups"],
            "tags": current_user["tags"],
            "auth_source": current_user["auth_source"],
        }

    def _dev_profiles_for_template() -> list[dict[str, Any]]:
        if not _settings().enable_dev_login:
            return []
        profiles: list[dict[str, Any]] = []
        for profile_key, profile in DEV_PROFILES.items():
            profiles.append(
                {
                    "key": profile_key,
                    "label": profile["label"],
                    "description": profile["description"],
                    "roles": profile["roles"],
                }
            )
        return profiles

    def _host_label(url: str) -> str:
        parsed = urlparse(url)
        return parsed.netloc or url

    return app


app = create_app()


def launch_server(flask_app: Flask) -> None:
    from waitress import serve

    settings = flask_app.config["PORTAL_SETTINGS"]
    serve(flask_app, host=settings.app_host, port=settings.app_port)
