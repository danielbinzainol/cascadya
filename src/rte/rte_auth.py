from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from types import ModuleType

from fastapi import HTTPException
from pydantic import SecretStr

DEFAULT_RTE_TOKEN_URL = "https://digital.iservices.rte-france.com/token/oauth/"
LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class RteResolvedAuthEnv:
    access_token: SecretStr | None
    client_id: str | None
    client_secret: SecretStr | None
    basic_authorization_b64: SecretStr | None
    token_url: str


def _get_hvac_module() -> ModuleType:
    try:
        import hvac  # type: ignore
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Vault access is configured but 'hvac' is not installed. "
                "Install it with: pip install hvac"
            ),
        ) from exc
    return hvac


def _read_rte_basic_auth_b64_from_vault() -> str | None:
    vault_addr = os.getenv("RTE_VAULT_ADDR") or os.getenv("VAULT_ADDR")
    rte_vault_token_raw = os.getenv("RTE_VAULT_TOKEN") or os.getenv("RTE_VAULT_TOKEN")
    vault_mount_point = os.getenv("RTE_VAULT_MOUNT_POINT", "secret")
    rte_vault_secret_path = os.getenv("RTE_VAULT_SECRET_PATH")
    vault_secret_key = os.getenv("RTE_VAULT_SECRET_KEY", "RTE_BASIC_AUTH_B64")

    if not vault_addr or not rte_vault_token_raw or not rte_vault_secret_path:
        return None
    rte_vault_token = SecretStr(rte_vault_token_raw)

    hvac = _get_hvac_module()
    client = hvac.Client(
        url=vault_addr,
        token=rte_vault_token.get_secret_value(),
    )

    if not client.is_authenticated():
        raise HTTPException(
            status_code=500,
            detail="Vault authentication failed for configured RTE credentials.",
        )

    try:
        read_response = client.secrets.kv.v2.read_secret_version(
            path=rte_vault_secret_path,
            mount_point=vault_mount_point,
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Failed to read RTE secret from Vault.")
        raise HTTPException(
            status_code=500, detail="Failed to read RTE secret from Vault."
        ) from exc

    secret_data = read_response.get("data", {}).get("data", {})
    secret_value = secret_data.get(vault_secret_key)
    if isinstance(secret_value, str) and secret_value.strip():
        return secret_value.strip()
    return None


def resolve_rte_auth_env() -> RteResolvedAuthEnv:
    access_token_raw = os.getenv("RTE_ACCESS_TOKEN")
    client_id = os.getenv("RTE_CLIENT_ID")
    client_secret_raw = os.getenv("RTE_CLIENT_SECRET")
    basic_authorization_b64_raw = os.getenv("RTE_BASIC_AUTH_B64")
    token_url = os.getenv("RTE_TOKEN_URL", DEFAULT_RTE_TOKEN_URL)
    access_token = SecretStr(access_token_raw) if access_token_raw else None
    client_secret = SecretStr(client_secret_raw) if client_secret_raw else None
    basic_authorization_b64 = (
        SecretStr(basic_authorization_b64_raw) if basic_authorization_b64_raw else None
    )

    has_client_credentials = bool(client_id and client_secret_raw)
    if not access_token and not basic_authorization_b64 and not has_client_credentials:
        vault_basic_auth_b64 = _read_rte_basic_auth_b64_from_vault()
        basic_authorization_b64 = (
            SecretStr(vault_basic_auth_b64) if vault_basic_auth_b64 else None
        )

    if not access_token and not basic_authorization_b64 and not has_client_credentials:
        raise HTTPException(
            status_code=400,
            detail=(
                "Missing RTE credentials. Set RTE_ACCESS_TOKEN, "
                "or set RTE_BASIC_AUTH_B64, "
                "or set RTE_CLIENT_ID and RTE_CLIENT_SECRET."
            ),
        )

    return RteResolvedAuthEnv(
        access_token=access_token,
        client_id=client_id,
        client_secret=client_secret,
        basic_authorization_b64=basic_authorization_b64,
        token_url=token_url,
    )
