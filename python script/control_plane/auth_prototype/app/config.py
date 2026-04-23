from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse


def _env_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name)
    if raw is None:
        return default
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    return values or default


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


def _default_database_url() -> str:
    db_path = Path(__file__).resolve().parents[1] / "control_panel_auth.db"
    return f"sqlite+pysqlite:///{db_path.as_posix()}"


def _default_provisioning_playbook_root() -> str | None:
    playbook_root = Path(__file__).resolve().parents[1] / "provisioning_ansible"
    if playbook_root.exists():
        return str(playbook_root)
    return None


def _env_str(name: str) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    value = raw.strip()
    return value or None


def _realm_from_issuer_url(issuer_url: str | None) -> str | None:
    if not issuer_url:
        return None
    parsed = urlparse(issuer_url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) >= 2 and segments[-2] == "realms":
        return segments[-1]
    return None


@dataclass(frozen=True)
class Settings:
    app_name: str
    session_secret: str
    session_cookie_name: str
    secure_cookies: bool
    same_site: str
    session_ttl_seconds: int
    trusted_hosts: tuple[str, ...]
    database_url: str
    database_echo: bool
    public_base_url: str | None
    wazuh_dashboard_url: str | None
    wazuh_alerts_indexer_url: str | None
    wazuh_alerts_indexer_username: str | None
    wazuh_alerts_indexer_password: str | None
    wazuh_alerts_index_pattern: str
    wazuh_alerts_verify_tls: bool
    wazuh_alerts_ca_cert_path: str | None
    wazuh_alerts_page_size: int
    wazuh_alerts_min_rule_level: int
    wazuh_alerts_timeout_seconds: int
    oidc_enabled: bool
    enable_legacy_login: bool
    oidc_issuer_url: str | None
    oidc_discovery_url: str | None
    oidc_client_id: str | None
    oidc_client_secret: str | None
    oidc_internal_base_url: str | None
    oidc_verify_tls: bool
    oidc_scopes: tuple[str, ...]
    bootstrap_admin_emails: tuple[str, ...]
    jit_default_roles: tuple[str, ...]
    keycloak_admin_base_url: str | None
    keycloak_admin_realm: str
    keycloak_admin_username: str | None
    keycloak_admin_password: str | None
    keycloak_managed_realm: str | None
    provisioning_playbook_root: str | None
    provisioning_default_playbook: str
    provisioning_execution_mode: str
    provisioning_ssh_key_path: str | None
    provisioning_ssh_key_passphrase: str | None
    provisioning_ssh_password: str | None
    provisioning_become_password: str | None
    provisioning_step_timeout_seconds: int
    provisioning_nats_server_ca_cert_path: str | None
    provisioning_wazuh_manager_address_default: str | None
    provisioning_wazuh_manager_port_default: int
    provisioning_wazuh_registration_server_default: str | None
    provisioning_wazuh_registration_port_default: int
    provisioning_wazuh_agent_group_default: str | None
    provisioning_wazuh_registration_password: str | None
    provisioning_wazuh_registration_ca_cert_path: str | None
    provisioning_ipc_alloy_mimir_remote_write_url_default: str | None
    provisioning_ipc_alloy_scrape_interval_default: str
    provisioning_ipc_alloy_scrape_timeout_default: str
    provisioning_ipc_alloy_tenant_default: str | None
    provisioning_ipc_alloy_retention_profile_default: str
    provisioning_ipc_alloy_mimir_username: str | None
    provisioning_ipc_alloy_mimir_password: str | None
    provisioning_ipc_alloy_mimir_verify_tls: bool
    provisioning_ipc_alloy_mimir_ca_cert_path: str | None
    provisioning_remote_unlock_broker_url_default: str | None
    provisioning_remote_unlock_broker_inventory_hostname: str | None
    provisioning_remote_unlock_broker_ansible_host: str | None
    provisioning_remote_unlock_broker_ansible_user: str | None
    provisioning_remote_unlock_broker_ansible_port: int
    provisioning_remote_unlock_broker_ssh_key_path: str | None
    provisioning_remote_unlock_broker_ssh_key_passphrase: str | None
    provisioning_remote_unlock_broker_ssh_password: str | None
    provisioning_remote_unlock_broker_become_password: str | None
    provisioning_remote_unlock_broker_wireguard_interface: str
    provisioning_remote_unlock_broker_wireguard_address: str | None
    provisioning_remote_unlock_broker_wireguard_listen_port: int
    provisioning_remote_unlock_broker_probe_port: int
    provisioning_remote_unlock_broker_probe_url_default: str | None
    provisioning_remote_unlock_broker_probe_token: str | None
    provisioning_remote_unlock_broker_probe_ca_cert_path: str | None
    e2e_ems_light_connection_name: str
    provisioning_remote_unlock_broker_vault_addr: str | None
    provisioning_remote_unlock_broker_vault_token: str | None
    provisioning_remote_unlock_broker_vault_kv_mount: str
    provisioning_remote_unlock_broker_vault_kv_prefix: str
    provisioning_wireguard_endpoint_default: str | None
    provisioning_wireguard_peer_public_key_default: str | None
    provisioning_auto_generate_wireguard_private_key: bool
    discovery_mode: str
    discovery_ssh_username: str | None
    discovery_ssh_port: int
    discovery_ssh_key_path: str | None
    discovery_downstream_probe_ip: str | None
    discovery_connect_timeout_seconds: int
    discovery_command_timeout_seconds: int

    @property
    def oidc_ready(self) -> bool:
        return (
            self.oidc_enabled
            and self.oidc_issuer_url is not None
            and self.oidc_client_id is not None
            and self.oidc_client_secret is not None
        )

    @property
    def keycloak_admin_ready(self) -> bool:
        return (
            self.keycloak_admin_base_url is not None
            and self.keycloak_admin_username is not None
            and self.keycloak_admin_password is not None
            and self.keycloak_managed_realm is not None
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    oidc_issuer_url = _env_str("AUTH_PROTO_OIDC_ISSUER_URL")
    oidc_internal_base_url = _env_str("AUTH_PROTO_OIDC_INTERNAL_BASE_URL")
    keycloak_admin_base_url = _env_str("AUTH_PROTO_KEYCLOAK_ADMIN_BASE_URL") or oidc_internal_base_url
    keycloak_managed_realm = _env_str("AUTH_PROTO_KEYCLOAK_MANAGED_REALM") or _realm_from_issuer_url(
        oidc_issuer_url
    )
    provisioning_remote_unlock_broker_ansible_host = _env_str(
        "AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_ANSIBLE_HOST"
    )
    provisioning_remote_unlock_broker_probe_port = _env_int(
        "AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_PROBE_PORT",
        9443,
    )
    provisioning_remote_unlock_broker_probe_url_default = _env_str(
        "AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_PROBE_URL_DEFAULT"
    )
    if provisioning_remote_unlock_broker_probe_url_default is None and provisioning_remote_unlock_broker_ansible_host:
        provisioning_remote_unlock_broker_probe_url_default = (
            f"https://{provisioning_remote_unlock_broker_ansible_host}:{provisioning_remote_unlock_broker_probe_port}"
        )

    return Settings(
        app_name=os.getenv("AUTH_PROTO_APP_NAME", "Control Plane Auth Prototype"),
        session_secret=os.getenv(
            "AUTH_PROTO_SESSION_SECRET",
            "replace-me-before-exposing-this-prototype-on-the-internet",
        ),
        session_cookie_name=os.getenv("AUTH_PROTO_SESSION_COOKIE", "control_plane_session"),
        secure_cookies=_env_flag("AUTH_PROTO_SECURE_COOKIES", False),
        same_site=os.getenv("AUTH_PROTO_SAMESITE", "lax"),
        session_ttl_seconds=int(os.getenv("AUTH_PROTO_SESSION_TTL_SECONDS", "28800")),
        trusted_hosts=_env_csv(
            "AUTH_PROTO_TRUSTED_HOSTS",
            ("127.0.0.1", "localhost"),
        ),
        database_url=os.getenv("AUTH_PROTO_DATABASE_URL", _default_database_url()),
        database_echo=_env_flag("AUTH_PROTO_DATABASE_ECHO", False),
        public_base_url=_env_str("AUTH_PROTO_PUBLIC_BASE_URL"),
        wazuh_dashboard_url=_env_str("AUTH_PROTO_WAZUH_DASHBOARD_URL"),
        wazuh_alerts_indexer_url=_env_str("AUTH_PROTO_WAZUH_ALERTS_INDEXER_URL"),
        wazuh_alerts_indexer_username=_env_str("AUTH_PROTO_WAZUH_ALERTS_INDEXER_USERNAME"),
        wazuh_alerts_indexer_password=_env_str("AUTH_PROTO_WAZUH_ALERTS_INDEXER_PASSWORD"),
        wazuh_alerts_index_pattern=os.getenv("AUTH_PROTO_WAZUH_ALERTS_INDEX_PATTERN", "wazuh-alerts-*").strip()
        or "wazuh-alerts-*",
        wazuh_alerts_verify_tls=_env_flag("AUTH_PROTO_WAZUH_ALERTS_VERIFY_TLS", True),
        wazuh_alerts_ca_cert_path=_env_str("AUTH_PROTO_WAZUH_ALERTS_CA_CERT_PATH"),
        wazuh_alerts_page_size=_env_int("AUTH_PROTO_WAZUH_ALERTS_PAGE_SIZE", 25),
        wazuh_alerts_min_rule_level=_env_int("AUTH_PROTO_WAZUH_ALERTS_MIN_RULE_LEVEL", 3),
        wazuh_alerts_timeout_seconds=_env_int("AUTH_PROTO_WAZUH_ALERTS_TIMEOUT_SECONDS", 10),
        oidc_enabled=_env_flag("AUTH_PROTO_OIDC_ENABLED", False),
        enable_legacy_login=_env_flag("AUTH_PROTO_ENABLE_LEGACY_LOGIN", False),
        oidc_issuer_url=oidc_issuer_url,
        oidc_discovery_url=_env_str("AUTH_PROTO_OIDC_DISCOVERY_URL"),
        oidc_client_id=_env_str("AUTH_PROTO_OIDC_CLIENT_ID"),
        oidc_client_secret=_env_str("AUTH_PROTO_OIDC_CLIENT_SECRET"),
        oidc_internal_base_url=oidc_internal_base_url,
        oidc_verify_tls=_env_flag("AUTH_PROTO_OIDC_VERIFY_TLS", True),
        oidc_scopes=_env_csv("AUTH_PROTO_OIDC_SCOPES", ("openid", "profile", "email")),
        bootstrap_admin_emails=_env_csv("AUTH_PROTO_BOOTSTRAP_ADMIN_EMAILS", ()),
        jit_default_roles=_env_csv("AUTH_PROTO_JIT_DEFAULT_ROLES", ()),
        keycloak_admin_base_url=keycloak_admin_base_url,
        keycloak_admin_realm=os.getenv("AUTH_PROTO_KEYCLOAK_ADMIN_REALM", "master"),
        keycloak_admin_username=_env_str("AUTH_PROTO_KEYCLOAK_ADMIN_USERNAME"),
        keycloak_admin_password=_env_str("AUTH_PROTO_KEYCLOAK_ADMIN_PASSWORD"),
        keycloak_managed_realm=keycloak_managed_realm,
        provisioning_playbook_root=_env_str("AUTH_PROTO_PROVISIONING_PLAYBOOK_ROOT") or _default_provisioning_playbook_root(),
        provisioning_default_playbook=os.getenv(
            "AUTH_PROTO_PROVISIONING_DEFAULT_PLAYBOOK", "full-ipc-wireguard-onboarding"
        ),
        provisioning_execution_mode=os.getenv("AUTH_PROTO_PROVISIONING_EXECUTION_MODE", "mock").strip().lower(),
        provisioning_ssh_key_path=_env_str("AUTH_PROTO_PROVISIONING_SSH_KEY_PATH"),
        provisioning_ssh_key_passphrase=_env_str("AUTH_PROTO_PROVISIONING_SSH_KEY_PASSPHRASE"),
        provisioning_ssh_password=_env_str("AUTH_PROTO_PROVISIONING_SSH_PASSWORD"),
        provisioning_become_password=_env_str("AUTH_PROTO_PROVISIONING_BECOME_PASSWORD"),
        provisioning_step_timeout_seconds=_env_int("AUTH_PROTO_PROVISIONING_STEP_TIMEOUT_SECONDS", 900),
        provisioning_nats_server_ca_cert_path=_env_str(
            "AUTH_PROTO_PROVISIONING_NATS_SERVER_CA_CERT_PATH"
        ),
        provisioning_wazuh_manager_address_default=_env_str(
            "AUTH_PROTO_PROVISIONING_WAZUH_MANAGER_ADDRESS_DEFAULT"
        ),
        provisioning_wazuh_manager_port_default=_env_int(
            "AUTH_PROTO_PROVISIONING_WAZUH_MANAGER_PORT_DEFAULT",
            1514,
        ),
        provisioning_wazuh_registration_server_default=_env_str(
            "AUTH_PROTO_PROVISIONING_WAZUH_REGISTRATION_SERVER_DEFAULT"
        ),
        provisioning_wazuh_registration_port_default=_env_int(
            "AUTH_PROTO_PROVISIONING_WAZUH_REGISTRATION_PORT_DEFAULT",
            1515,
        ),
        provisioning_wazuh_agent_group_default=_env_str(
            "AUTH_PROTO_PROVISIONING_WAZUH_AGENT_GROUP_DEFAULT"
        ),
        provisioning_wazuh_registration_password=_env_str(
            "AUTH_PROTO_PROVISIONING_WAZUH_REGISTRATION_PASSWORD"
        ),
        provisioning_wazuh_registration_ca_cert_path=_env_str(
            "AUTH_PROTO_PROVISIONING_WAZUH_REGISTRATION_CA_CERT_PATH"
        ),
        provisioning_ipc_alloy_mimir_remote_write_url_default=_env_str(
            "AUTH_PROTO_PROVISIONING_IPC_ALLOY_MIMIR_REMOTE_WRITE_URL_DEFAULT"
        ),
        provisioning_ipc_alloy_scrape_interval_default=(
            _env_str("AUTH_PROTO_PROVISIONING_IPC_ALLOY_SCRAPE_INTERVAL_DEFAULT")
            or "15s"
        ),
        provisioning_ipc_alloy_scrape_timeout_default=(
            _env_str("AUTH_PROTO_PROVISIONING_IPC_ALLOY_SCRAPE_TIMEOUT_DEFAULT")
            or "10s"
        ),
        provisioning_ipc_alloy_tenant_default=_env_str(
            "AUTH_PROTO_PROVISIONING_IPC_ALLOY_TENANT_DEFAULT"
        )
        or "classic",
        provisioning_ipc_alloy_retention_profile_default=(
            _env_str("AUTH_PROTO_PROVISIONING_IPC_ALLOY_RETENTION_PROFILE_DEFAULT")
            or "classic"
        ),
        provisioning_ipc_alloy_mimir_username=_env_str(
            "AUTH_PROTO_PROVISIONING_IPC_ALLOY_MIMIR_USERNAME"
        ),
        provisioning_ipc_alloy_mimir_password=_env_str(
            "AUTH_PROTO_PROVISIONING_IPC_ALLOY_MIMIR_PASSWORD"
        ),
        provisioning_ipc_alloy_mimir_verify_tls=_env_flag(
            "AUTH_PROTO_PROVISIONING_IPC_ALLOY_MIMIR_VERIFY_TLS",
            True,
        ),
        provisioning_ipc_alloy_mimir_ca_cert_path=_env_str(
            "AUTH_PROTO_PROVISIONING_IPC_ALLOY_MIMIR_CA_CERT_PATH"
        ),
        provisioning_remote_unlock_broker_url_default=_env_str(
            "AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_URL_DEFAULT"
        ),
        provisioning_remote_unlock_broker_inventory_hostname=_env_str(
            "AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_INVENTORY_HOSTNAME"
        ),
        provisioning_remote_unlock_broker_ansible_host=provisioning_remote_unlock_broker_ansible_host,
        provisioning_remote_unlock_broker_ansible_user=_env_str(
            "AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_ANSIBLE_USER"
        ),
        provisioning_remote_unlock_broker_ansible_port=_env_int(
            "AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_ANSIBLE_PORT",
            22,
        ),
        provisioning_remote_unlock_broker_ssh_key_path=_env_str(
            "AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_SSH_KEY_PATH"
        ),
        provisioning_remote_unlock_broker_ssh_key_passphrase=_env_str(
            "AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_SSH_KEY_PASSPHRASE"
        ),
        provisioning_remote_unlock_broker_ssh_password=_env_str(
            "AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_SSH_PASSWORD"
        ),
        provisioning_remote_unlock_broker_become_password=_env_str(
            "AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_BECOME_PASSWORD"
        ),
        provisioning_remote_unlock_broker_wireguard_interface=(
            _env_str("AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_WIREGUARD_INTERFACE") or "wg0"
        ),
        provisioning_remote_unlock_broker_wireguard_address=_env_str(
            "AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_WIREGUARD_ADDRESS"
        ),
        provisioning_remote_unlock_broker_wireguard_listen_port=_env_int(
            "AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_WIREGUARD_LISTEN_PORT",
            51820,
        ),
        provisioning_remote_unlock_broker_probe_port=provisioning_remote_unlock_broker_probe_port,
        provisioning_remote_unlock_broker_probe_url_default=provisioning_remote_unlock_broker_probe_url_default,
        provisioning_remote_unlock_broker_probe_token=_env_str(
            "AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_PROBE_TOKEN"
        ),
        provisioning_remote_unlock_broker_probe_ca_cert_path=_env_str(
            "AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_PROBE_CA_CERT_PATH"
        ),
        e2e_ems_light_connection_name=(
            _env_str("AUTH_PROTO_E2E_EMS_LIGHT_CONNECTION_NAME")
            or "iec104-bridge"
        ),
        provisioning_remote_unlock_broker_vault_addr=_env_str(
            "AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_VAULT_ADDR"
        ),
        provisioning_remote_unlock_broker_vault_token=_env_str(
            "AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_VAULT_TOKEN"
        ),
        provisioning_remote_unlock_broker_vault_kv_mount=(
            _env_str("AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_VAULT_KV_MOUNT")
            or "secret"
        ),
        provisioning_remote_unlock_broker_vault_kv_prefix=(
            _env_str("AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_VAULT_KV_PREFIX")
            or "remote-unlock"
        ),
        provisioning_wireguard_endpoint_default=_env_str(
            "AUTH_PROTO_PROVISIONING_WIREGUARD_ENDPOINT_DEFAULT"
        ),
        provisioning_wireguard_peer_public_key_default=_env_str(
            "AUTH_PROTO_PROVISIONING_WIREGUARD_PEER_PUBLIC_KEY_DEFAULT"
        ),
        provisioning_auto_generate_wireguard_private_key=_env_flag(
            "AUTH_PROTO_PROVISIONING_AUTO_GENERATE_WIREGUARD_PRIVATE_KEY",
            True,
        ),
        discovery_mode=os.getenv("AUTH_PROTO_DISCOVERY_MODE", "auto").strip().lower(),
        discovery_ssh_username=_env_str("AUTH_PROTO_DISCOVERY_SSH_USERNAME"),
        discovery_ssh_port=_env_int("AUTH_PROTO_DISCOVERY_SSH_PORT", 22),
        discovery_ssh_key_path=_env_str("AUTH_PROTO_DISCOVERY_SSH_KEY_PATH"),
        discovery_downstream_probe_ip=_env_str("AUTH_PROTO_DISCOVERY_DOWNSTREAM_PROBE_IP"),
        discovery_connect_timeout_seconds=_env_int("AUTH_PROTO_DISCOVERY_CONNECT_TIMEOUT_SECONDS", 5),
        discovery_command_timeout_seconds=_env_int("AUTH_PROTO_DISCOVERY_COMMAND_TIMEOUT_SECONDS", 15),
    )
