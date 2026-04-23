from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import Settings, get_settings


class KeycloakAdminError(RuntimeError):
    """Raised when the Keycloak admin API cannot complete an operation."""


@dataclass(frozen=True)
class KeycloakManagedUser:
    keycloak_uuid: str
    username: str
    email: str
    first_name: str | None
    last_name: str | None
    enabled: bool
    email_verified: bool

    @property
    def display_name(self) -> str:
        full_name = " ".join(part for part in (self.first_name, self.last_name) if part)
        return full_name or self.username or self.email


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise KeycloakAdminError("L'email fourni n'est pas valide.")
    local_part, _, domain_part = normalized.partition("@")
    if "." not in domain_part or not local_part or not domain_part:
        raise KeycloakAdminError("L'email fourni n'est pas valide.")
    return normalized


def _require_keycloak_admin(settings: Settings) -> None:
    if not settings.keycloak_admin_ready:
        raise KeycloakAdminError(
            "Le control panel n'a pas encore les credentials d'administration Keycloak. "
            "Configure AUTH_PROTO_KEYCLOAK_ADMIN_* dans l'environnement."
        )


def _http_client() -> Any:
    try:
        import httpx
    except ImportError as exc:
        raise KeycloakAdminError(
            "La dependance 'httpx' est requise pour l'administration Keycloak."
        ) from exc

    return httpx.Client(
        timeout=10.0,
        follow_redirects=True,
        headers={"Accept": "application/json"},
    )


def _httpx_module() -> Any:
    try:
        import httpx
    except ImportError as exc:
        raise KeycloakAdminError(
            "La dependance 'httpx' est requise pour l'administration Keycloak."
        ) from exc
    return httpx


def _raise_for_response(response: Any, *, context: str) -> None:
    if response.is_success:
        return

    detail = response.text.strip()
    if detail:
        raise KeycloakAdminError(f"{context} (HTTP {response.status_code}): {detail}")
    raise KeycloakAdminError(f"{context} (HTTP {response.status_code}).")


def _admin_token(settings: Settings) -> str:
    _require_keycloak_admin(settings)
    token_url = (
        f"{settings.keycloak_admin_base_url.rstrip('/')}/realms/"
        f"{settings.keycloak_admin_realm}/protocol/openid-connect/token"
    )
    httpx = _httpx_module()
    try:
        with _http_client() as client:
            response = client.post(
                token_url,
                data={
                    "client_id": "admin-cli",
                    "grant_type": "password",
                    "username": settings.keycloak_admin_username,
                    "password": settings.keycloak_admin_password,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            _raise_for_response(response, context="Echec de l'authentification admin Keycloak")
            payload = response.json()
    except httpx.RequestError as exc:
        raise KeycloakAdminError(
            f"Echec de connexion vers l'API admin Keycloak: {exc}"
        ) from exc

    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise KeycloakAdminError("Keycloak n'a pas retourne de token admin exploitable.")
    return access_token


def _deserialize_user(payload: dict[str, Any]) -> KeycloakManagedUser:
    keycloak_uuid = payload.get("id")
    username = payload.get("username")
    email = payload.get("email")
    if not isinstance(keycloak_uuid, str) or not isinstance(username, str) or not isinstance(email, str):
        raise KeycloakAdminError("La reponse Keycloak utilisateur est incomplete.")

    return KeycloakManagedUser(
        keycloak_uuid=keycloak_uuid,
        username=username,
        email=email.strip().lower(),
        first_name=_normalize_text(payload.get("firstName") if isinstance(payload.get("firstName"), str) else None),
        last_name=_normalize_text(payload.get("lastName") if isinstance(payload.get("lastName"), str) else None),
        enabled=bool(payload.get("enabled", True)),
        email_verified=bool(payload.get("emailVerified", False)),
    )


def _admin_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _managed_realm_users_url(settings: Settings) -> str:
    assert settings.keycloak_managed_realm is not None
    return f"{settings.keycloak_admin_base_url.rstrip('/')}/admin/realms/{settings.keycloak_managed_realm}/users"


def _managed_user_url(settings: Settings, keycloak_uuid: str) -> str:
    return f"{_managed_realm_users_url(settings)}/{keycloak_uuid}"


def _find_user_by_uuid(settings: Settings, token: str, keycloak_uuid: str) -> KeycloakManagedUser | None:
    httpx = _httpx_module()
    try:
        with _http_client() as client:
            response = client.get(
                _managed_user_url(settings, keycloak_uuid),
                headers=_admin_headers(token),
            )
    except httpx.RequestError as exc:
        raise KeycloakAdminError(
            f"Impossible de lire l'utilisateur Keycloak {keycloak_uuid}: {exc}"
        ) from exc

    if response.status_code == 404:
        return None
    _raise_for_response(response, context="Lecture de l'utilisateur Keycloak impossible")
    payload = response.json()
    if not isinstance(payload, dict):
        raise KeycloakAdminError("La reponse Keycloak utilisateur est invalide.")
    return _deserialize_user(payload)


def _find_user_by_email(settings: Settings, token: str, email: str) -> KeycloakManagedUser | None:
    url = _managed_realm_users_url(settings)
    httpx = _httpx_module()
    try:
        with _http_client() as client:
            response = client.get(
                url,
                params={"email": email, "exact": "true", "max": 5},
                headers=_admin_headers(token),
            )
            _raise_for_response(response, context="Lecture des utilisateurs Keycloak impossible")
            payload = response.json()
    except httpx.RequestError as exc:
        raise KeycloakAdminError(
            f"Impossible de lire les utilisateurs Keycloak: {exc}"
        ) from exc

    if not isinstance(payload, list):
        return None
    for raw_item in payload:
        if not isinstance(raw_item, dict):
            continue
        raw_email = raw_item.get("email")
        if isinstance(raw_email, str) and raw_email.strip().lower() == email:
            return _deserialize_user(raw_item)
    return None


def _find_user_by_username(settings: Settings, token: str, username: str) -> KeycloakManagedUser | None:
    url = _managed_realm_users_url(settings)
    httpx = _httpx_module()
    try:
        with _http_client() as client:
            response = client.get(
                url,
                params={"username": username, "exact": "true", "max": 5},
                headers=_admin_headers(token),
            )
            _raise_for_response(response, context="Lecture des utilisateurs Keycloak impossible")
            payload = response.json()
    except httpx.RequestError as exc:
        raise KeycloakAdminError(
            f"Impossible de lire les utilisateurs Keycloak: {exc}"
        ) from exc

    if not isinstance(payload, list):
        return None
    for raw_item in payload:
        if not isinstance(raw_item, dict):
            continue
        raw_username = raw_item.get("username")
        if isinstance(raw_username, str) and raw_username.strip().lower() == username:
            return _deserialize_user(raw_item)
    return None


def provision_keycloak_user(
    *,
    email: str,
    first_name: str | None = None,
    last_name: str | None = None,
) -> KeycloakManagedUser:
    settings = get_settings()
    _require_keycloak_admin(settings)

    normalized_email = _normalize_email(email)
    normalized_first_name = _normalize_text(first_name)
    normalized_last_name = _normalize_text(last_name)
    username = normalized_email
    token = _admin_token(settings)
    managed_user = _find_user_by_email(settings, token, normalized_email) or _find_user_by_username(
        settings,
        token,
        username,
    )

    payload = {
        "username": username,
        "email": normalized_email,
        "firstName": normalized_first_name if normalized_first_name is not None else (managed_user.first_name if managed_user else None),
        "lastName": normalized_last_name if normalized_last_name is not None else (managed_user.last_name if managed_user else None),
        "enabled": True,
        "emailVerified": managed_user.email_verified if managed_user else False,
    }

    httpx = _httpx_module()
    try:
        with _http_client() as client:
            if managed_user is None:
                response = client.post(
                    _managed_realm_users_url(settings),
                    headers=_admin_headers(token),
                    json=payload,
                )
                _raise_for_response(response, context="Creation de l'utilisateur Keycloak impossible")
            else:
                response = client.put(
                    f"{_managed_realm_users_url(settings)}/{managed_user.keycloak_uuid}",
                    headers=_admin_headers(token),
                    json=payload,
                )
                _raise_for_response(response, context="Mise a jour de l'utilisateur Keycloak impossible")
    except httpx.RequestError as exc:
        raise KeycloakAdminError(
            f"Impossible de creer ou mettre a jour l'utilisateur Keycloak: {exc}"
        ) from exc

    refreshed_user = _find_user_by_email(settings, token, normalized_email)
    if refreshed_user is None:
        raise KeycloakAdminError("Utilisateur Keycloak cree, mais introuvable ensuite via l'API admin.")
    return refreshed_user


def update_keycloak_user(
    *,
    keycloak_uuid: str,
    email: str,
    first_name: str | None = None,
    last_name: str | None = None,
    enabled: bool | None = None,
) -> KeycloakManagedUser:
    settings = get_settings()
    _require_keycloak_admin(settings)

    normalized_uuid = keycloak_uuid.strip()
    normalized_email = _normalize_email(email)
    normalized_first_name = _normalize_text(first_name)
    normalized_last_name = _normalize_text(last_name)
    if not normalized_uuid:
        raise KeycloakAdminError("Le Keycloak UUID est obligatoire pour mettre a jour un utilisateur.")

    token = _admin_token(settings)
    managed_user = _find_user_by_uuid(settings, token, normalized_uuid)
    if managed_user is None:
        raise KeycloakAdminError(f"Utilisateur Keycloak introuvable: {normalized_uuid}")

    payload = {
        "username": normalized_email,
        "email": normalized_email,
        "firstName": normalized_first_name if normalized_first_name is not None else managed_user.first_name,
        "lastName": normalized_last_name if normalized_last_name is not None else managed_user.last_name,
        "enabled": managed_user.enabled if enabled is None else bool(enabled),
        "emailVerified": managed_user.email_verified,
    }

    httpx = _httpx_module()
    try:
        with _http_client() as client:
            response = client.put(
                _managed_user_url(settings, normalized_uuid),
                headers=_admin_headers(token),
                json=payload,
            )
            _raise_for_response(response, context="Mise a jour de l'utilisateur Keycloak impossible")
    except httpx.RequestError as exc:
        raise KeycloakAdminError(
            f"Impossible de mettre a jour l'utilisateur Keycloak: {exc}"
        ) from exc

    refreshed_user = _find_user_by_uuid(settings, token, normalized_uuid)
    if refreshed_user is None:
        raise KeycloakAdminError(
            "Utilisateur Keycloak mis a jour, mais introuvable ensuite via l'API admin."
        )
    return refreshed_user


def delete_keycloak_user(*, keycloak_uuid: str, ignore_missing: bool = False) -> bool:
    settings = get_settings()
    _require_keycloak_admin(settings)

    normalized_uuid = keycloak_uuid.strip()
    if not normalized_uuid:
        raise KeycloakAdminError("Le Keycloak UUID est obligatoire pour supprimer un utilisateur.")

    token = _admin_token(settings)
    httpx = _httpx_module()
    try:
        with _http_client() as client:
            response = client.delete(
                _managed_user_url(settings, normalized_uuid),
                headers=_admin_headers(token),
            )
    except httpx.RequestError as exc:
        raise KeycloakAdminError(
            f"Impossible de supprimer l'utilisateur Keycloak: {exc}"
        ) from exc

    if response.status_code == 404 and ignore_missing:
        return False
    _raise_for_response(response, context="Suppression de l'utilisateur Keycloak impossible")
    return True
