from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import src.rte.rte_auth as rte_auth


def test_resolve_rte_auth_env_uses_plain_environment_value(monkeypatch) -> None:
    monkeypatch.setenv("RTE_BASIC_AUTH_B64", "env-basic-value")
    monkeypatch.delenv("RTE_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("RTE_CLIENT_ID", raising=False)
    monkeypatch.delenv("RTE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("RTE_VAULT_ADDR", raising=False)
    monkeypatch.delenv("RTE_VAULT_TOKEN", raising=False)
    monkeypatch.delenv("RTE_VAULT_SECRET_PATH", raising=False)

    resolved = rte_auth.resolve_rte_auth_env()

    assert resolved.basic_authorization_b64 is not None
    assert resolved.basic_authorization_b64.get_secret_value() == "env-basic-value"


def test_resolve_rte_auth_env_reads_basic_auth_from_vault(monkeypatch) -> None:
    captured: dict[str, str] = {}

    class FakeKVV2:
        def read_secret_version(self, *, path: str, mount_point: str):  # noqa: ANN001
            captured["path"] = path
            captured["mount_point"] = mount_point
            return {"data": {"data": {"RTE_BASIC_AUTH_B64": "vault-basic-value"}}}

    class FakeClient:
        def __init__(self, *, url: str, token: str) -> None:
            captured["url"] = url
            captured["token"] = token
            self.secrets = SimpleNamespace(kv=SimpleNamespace(v2=FakeKVV2()))

        def is_authenticated(self) -> bool:
            return True

    monkeypatch.delenv("RTE_BASIC_AUTH_B64", raising=False)
    monkeypatch.delenv("RTE_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("RTE_CLIENT_ID", raising=False)
    monkeypatch.delenv("RTE_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("RTE_VAULT_ADDR", "https://vault.scaleway.example:8200")
    monkeypatch.setenv("RTE_VAULT_TOKEN", "vault-token")
    monkeypatch.setenv("RTE_VAULT_SECRET_PATH", "rte/api")
    monkeypatch.setenv("RTE_VAULT_MOUNT_POINT", "kv")
    monkeypatch.setitem(sys.modules, "hvac", SimpleNamespace(Client=FakeClient))

    resolved = rte_auth.resolve_rte_auth_env()

    assert resolved.basic_authorization_b64 is not None
    assert resolved.basic_authorization_b64.get_secret_value() == "vault-basic-value"
    assert captured["url"] == "https://vault.scaleway.example:8200"
    assert captured["token"] == "vault-token"
    assert captured["path"] == "rte/api"
    assert captured["mount_point"] == "kv"


def test_resolve_rte_auth_env_raises_when_vault_configured_but_hvac_missing(monkeypatch) -> None:
    monkeypatch.delenv("RTE_BASIC_AUTH_B64", raising=False)
    monkeypatch.delenv("RTE_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("RTE_CLIENT_ID", raising=False)
    monkeypatch.delenv("RTE_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("RTE_VAULT_ADDR", "https://vault.scaleway.example:8200")
    monkeypatch.setenv("RTE_VAULT_TOKEN", "vault-token")
    monkeypatch.setenv("RTE_VAULT_SECRET_PATH", "rte/api")
    def _raise_missing_hvac():  # noqa: ANN202
        raise HTTPException(status_code=500, detail="Vault access is configured but 'hvac' is not installed.")

    monkeypatch.setattr(rte_auth, "_get_hvac_module", _raise_missing_hvac)

    with pytest.raises(HTTPException, match="hvac"):
        rte_auth.resolve_rte_auth_env()
