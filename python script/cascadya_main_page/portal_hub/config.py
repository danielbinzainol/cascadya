from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional during bootstrap
    load_dotenv = None


if load_dotenv is not None:
    load_dotenv()


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw.strip())


def _env_str(name: str) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    value = raw.strip()
    return value or None


def _env_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name)
    if raw is None:
        return default
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    return values or default


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment_label: str
    app_host: str
    app_port: int
    public_base_url: str | None
    session_secret: str
    session_cookie_name: str
    secure_cookies: bool
    same_site: str
    session_ttl_seconds: int
    oidc_enabled: bool
    oidc_issuer_url: str | None
    oidc_discovery_url: str | None
    oidc_client_id: str | None
    oidc_client_secret: str | None
    oidc_internal_base_url: str | None
    oidc_verify_tls: bool
    oidc_ca_cert_path: str | None
    oidc_scopes: tuple[str, ...]
    required_tags: tuple[str, ...]
    enable_dev_login: bool
    default_next_path: str
    control_panel_url: str
    features_url: str
    grafana_url: str
    wazuh_url: str
    mimir_url: str
    keycloak_admin_url: str
    docs_url: str | None

    @property
    def oidc_ready(self) -> bool:
        return (
            self.oidc_enabled
            and self.oidc_issuer_url is not None
            and self.oidc_client_id is not None
            and self.oidc_client_secret is not None
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("PORTAL_APP_NAME", "Cascadya Portal"),
        environment_label=os.getenv("PORTAL_ENV_LABEL", "DEV1"),
        app_host=os.getenv("APP_HOST", "127.0.0.1"),
        app_port=_env_int("APP_PORT", 8788),
        public_base_url=_env_str("PORTAL_PUBLIC_BASE_URL"),
        session_secret=os.getenv(
            "PORTAL_SESSION_SECRET",
            "replace-me-before-exposing-the-portal",
        ),
        session_cookie_name=os.getenv("PORTAL_SESSION_COOKIE", "cascadya_portal_session"),
        secure_cookies=_env_flag("PORTAL_SECURE_COOKIES", False),
        same_site=os.getenv("PORTAL_SAMESITE", "Lax"),
        session_ttl_seconds=_env_int("PORTAL_SESSION_TTL_SECONDS", 28800),
        oidc_enabled=_env_flag("PORTAL_OIDC_ENABLED", False),
        oidc_issuer_url=_env_str("PORTAL_OIDC_ISSUER_URL"),
        oidc_discovery_url=_env_str("PORTAL_OIDC_DISCOVERY_URL"),
        oidc_client_id=_env_str("PORTAL_OIDC_CLIENT_ID"),
        oidc_client_secret=_env_str("PORTAL_OIDC_CLIENT_SECRET"),
        oidc_internal_base_url=_env_str("PORTAL_OIDC_INTERNAL_BASE_URL"),
        oidc_verify_tls=_env_flag("PORTAL_OIDC_VERIFY_TLS", True),
        oidc_ca_cert_path=_env_str("PORTAL_OIDC_CA_CERT_PATH"),
        oidc_scopes=_env_csv("PORTAL_OIDC_SCOPES", ("openid", "profile", "email")),
        required_tags=_env_csv("PORTAL_REQUIRED_TAGS", ()),
        enable_dev_login=_env_flag("PORTAL_ENABLE_DEV_LOGIN", True),
        default_next_path=os.getenv("PORTAL_DEFAULT_NEXT_PATH", "/"),
        control_panel_url=os.getenv(
            "PORTAL_URL_CONTROL_PANEL",
            "https://control-panel.cascadya.internal",
        ),
        features_url=os.getenv(
            "PORTAL_URL_FEATURES",
            "https://features.cascadya.internal",
        ),
        grafana_url=os.getenv(
            "PORTAL_URL_GRAFANA",
            "https://grafana.cascadya.internal",
        ),
        wazuh_url=os.getenv(
            "PORTAL_URL_WAZUH",
            "https://wazuh.cascadya.internal",
        ),
        mimir_url=os.getenv(
            "PORTAL_URL_MIMIR",
            "https://grafana.cascadya.internal",
        ),
        keycloak_admin_url=os.getenv(
            "PORTAL_URL_KEYCLOAK_ADMIN",
            "https://auth.cascadya.internal/admin/",
        ),
        docs_url=_env_str("PORTAL_URL_DOCS"),
    )
