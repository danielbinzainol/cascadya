from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import Role, User
from .oidc import OIDCError, fetch_userinfo, introspect_access_token
from .rbac import ROLE_DEFINITIONS


class ManagedUserError(RuntimeError):
    """Base error for RBAC and managed-user operations."""


class ManagedUserNotFoundError(ManagedUserError):
    """Raised when a managed user does not exist."""


class ManagedRoleError(ManagedUserError):
    """Raised when a managed role change cannot be applied."""


class ManagedUserProvisionError(ManagedUserError):
    """Raised when a managed user cannot be provisioned from Keycloak data."""


@dataclass(frozen=True)
class DemoUserRecord:
    username: str
    display_name: str
    password_hash: str
    roles: tuple[str, ...]


@dataclass(frozen=True)
class SessionUser:
    user_id: int | None
    keycloak_uuid: str | None
    username: str
    email: str | None
    display_name: str
    roles: tuple[str, ...]
    permissions: tuple[str, ...]
    is_active: bool
    auth_source: str

    def has_permission(self, permission_name: str) -> bool:
        return permission_name in self.permissions

    @property
    def is_admin(self) -> bool:
        return "admin" in self.roles


DEFAULT_DEMO_USERS: dict[str, DemoUserRecord] = {
    "operator": DemoUserRecord(
        username="operator",
        display_name="Operator Demo",
        password_hash=(
            "scrypt$16384$8$1$DMkSaLUGNt/Aq8oIfv0ejQ==$"
            "gLusWRIdT4dKs+IlKt/CMNlqS2+OmRwRJrTHQF6W0ROlq/nildXS2cO0LBu5GxuZYkdYGYGOt5N3C6cR+rUzsA=="
        ),
        roles=("operator",),
    ),
    "admin": DemoUserRecord(
        username="admin",
        display_name="Admin Demo",
        password_hash=(
            "scrypt$16384$8$1$OfwC/A0oRn1uIhF5E7AxQA==$"
            "xXPEQQlMUwyJx5yTFOmRJ6GkHFOcHr7VvQtaKIn82WUza27TAwk+IaANCQjlsqD/yCepz0wV+EtSej8vzaEa4A=="
        ),
        roles=("operator", "admin"),
    ),
}


ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    definition.name: tuple(sorted(definition.permission_names))
    for definition in ROLE_DEFINITIONS
}


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, n_raw, r_raw, p_raw, salt_b64, digest_b64 = password_hash.split("$", 5)
    except ValueError:
        return False

    if algorithm != "scrypt":
        return False

    try:
        salt = base64.b64decode(salt_b64)
        expected_digest = base64.b64decode(digest_b64)
        derived_digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n_raw),
            r=int(r_raw),
            p=int(p_raw),
        )
    except (ValueError, TypeError):
        return False

    return hmac.compare_digest(derived_digest, expected_digest)


def _permissions_for_role_names(role_names: tuple[str, ...]) -> tuple[str, ...]:
    permissions: set[str] = set()
    for role_name in role_names:
        permissions.update(ROLE_PERMISSIONS.get(role_name, ()))
    return tuple(sorted(permissions))


def authenticate_legacy(username: str, password: str) -> SessionUser | None:
    record = DEFAULT_DEMO_USERS.get(username.strip().lower())
    if record is None or not verify_password(password, record.password_hash):
        return None
    return SessionUser(
        user_id=None,
        keycloak_uuid=None,
        username=record.username,
        email=None,
        display_name=record.display_name,
        roles=record.roles,
        permissions=_permissions_for_role_names(record.roles),
        is_active=True,
        auth_source="legacy",
    )


def build_session_payload(user: SessionUser, *, id_token: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"auth_source": user.auth_source}
    if user.user_id is not None:
        payload["user_id"] = user.user_id
        payload["keycloak_uuid"] = user.keycloak_uuid
        payload["id_token"] = id_token
        return payload

    payload.update(
        {
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "roles": list(user.roles),
            "permissions": list(user.permissions),
            "is_active": user.is_active,
        }
    )
    return payload


def extract_id_token(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    id_token = payload.get("id_token")
    return id_token if isinstance(id_token, str) and id_token else None


def _session_user_from_legacy_payload(payload: dict[str, Any]) -> SessionUser | None:
    username = payload.get("username")
    display_name = payload.get("display_name")
    email = payload.get("email")
    roles = payload.get("roles")
    permissions = payload.get("permissions")
    is_active = payload.get("is_active", True)
    if not isinstance(username, str) or not isinstance(display_name, str):
        return None
    if not isinstance(email, (str, type(None))):
        return None
    if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
        return None
    if not isinstance(permissions, list) or not all(isinstance(permission, str) for permission in permissions):
        return None
    if not isinstance(is_active, bool):
        return None

    return SessionUser(
        user_id=None,
        keycloak_uuid=None,
        username=username,
        email=email,
        display_name=display_name,
        roles=tuple(sorted(roles)),
        permissions=tuple(sorted(permissions)),
        is_active=is_active,
        auth_source="legacy",
    )


def _build_session_user_from_model(user: User, *, auth_source: str) -> SessionUser:
    roles = tuple(sorted(role.name for role in user.roles))
    permissions = tuple(
        sorted(
            {
                permission.name
                for role in user.roles
                for permission in role.permissions
            }
        )
    )
    username = user.preferred_username or user.email
    return SessionUser(
        user_id=user.id,
        keycloak_uuid=user.keycloak_uuid,
        username=username,
        email=user.email,
        display_name=user.display_name,
        roles=roles,
        permissions=permissions,
        is_active=user.is_active,
        auth_source=auth_source,
    )


def _user_query() -> Any:
    return select(User).options(selectinload(User.roles).selectinload(Role.permissions))


def _fetch_user_by_id(session: Session, user_id: int) -> User | None:
    return session.scalar(_user_query().where(User.id == user_id))


def _fetch_user_by_keycloak_uuid(session: Session, keycloak_uuid: str) -> User | None:
    return session.scalar(_user_query().where(User.keycloak_uuid == keycloak_uuid))


def _fetch_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(_user_query().where(User.email == email))


def load_session_user(session: Session, payload: Any) -> SessionUser | None:
    if not isinstance(payload, dict):
        return None

    auth_source = payload.get("auth_source")
    if auth_source == "legacy":
        return _session_user_from_legacy_payload(payload)

    user_id = payload.get("user_id")
    if not isinstance(user_id, int):
        return None

    user = _fetch_user_by_id(session, user_id)
    if user is None:
        return None
    return _build_session_user_from_model(user, auth_source="oidc")


def _normalize_claim(claims: dict[str, Any], key: str) -> str | None:
    value = claims.get(key)
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _resolve_display_name(claims: dict[str, Any], email: str) -> str:
    return (
        _normalize_claim(claims, "name")
        or _normalize_claim(claims, "preferred_username")
        or email
    )


def _resolve_username(claims: dict[str, Any], email: str) -> str:
    return _normalize_claim(claims, "preferred_username") or email


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _fetch_roles_by_name(session: Session, role_names: tuple[str, ...]) -> list[Role]:
    requested = tuple(sorted({name for name in role_names if name}))
    if not requested:
        return []

    roles = session.scalars(select(Role).where(Role.name.in_(requested)).order_by(Role.name)).all()
    missing = sorted(set(requested) - {role.name for role in roles})
    if missing:
        raise ManagedRoleError(f"Unknown role(s): {', '.join(missing)}")
    return roles


def sync_user_from_oidc_claims(
    session: Session,
    claims: dict[str, Any],
    *,
    default_role_names: tuple[str, ...] = (),
    bootstrap_admin_emails: tuple[str, ...] = (),
) -> SessionUser:
    keycloak_uuid = _normalize_claim(claims, "sub")
    email = _normalize_email(_normalize_claim(claims, "email") or "")
    if keycloak_uuid is None or not email:
        raise OIDCError("OIDC userinfo is missing the 'sub' or 'email' claim.")

    user = _fetch_user_by_keycloak_uuid(session, keycloak_uuid)
    was_new = user is None
    if user is None:
        user = _fetch_user_by_email(session, email)

    if user is None:
        user = User(
            keycloak_uuid=keycloak_uuid,
            email=email,
            preferred_username=_resolve_username(claims, email),
            display_name=_resolve_display_name(claims, email),
            is_active=True,
        )
        session.add(user)
    else:
        user.keycloak_uuid = keycloak_uuid
        user.email = email
        user.preferred_username = _resolve_username(claims, email)
        user.display_name = _resolve_display_name(claims, email)

    if was_new and default_role_names:
        user.roles = _fetch_roles_by_name(session, default_role_names)

    normalized_admin_emails = {item.lower() for item in bootstrap_admin_emails}
    if email in normalized_admin_emails:
        admin_role = _fetch_roles_by_name(session, ("admin",))[0]
        existing_role_names = {role.name for role in user.roles}
        if admin_role.name not in existing_role_names:
            user.roles.append(admin_role)

    user.last_login_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(user)
    user = _fetch_user_by_id(session, user.id)
    assert user is not None
    return _build_session_user_from_model(user, auth_source="oidc")


def provision_managed_user(
    session: Session,
    *,
    keycloak_uuid: str,
    email: str,
    preferred_username: str | None,
    display_name: str,
    role_names: tuple[str, ...] | None = (),
    is_active: bool = True,
) -> SessionUser:
    normalized_uuid = keycloak_uuid.strip()
    normalized_email = _normalize_email(email)
    normalized_display_name = display_name.strip()
    normalized_username = preferred_username.strip() if isinstance(preferred_username, str) else ""

    if not normalized_uuid or not normalized_email or not normalized_display_name:
        raise ManagedUserProvisionError(
            "Impossible de provisionner le compte miroir: donnees Keycloak incompletes."
        )

    user = _fetch_user_by_keycloak_uuid(session, normalized_uuid) or _fetch_user_by_email(session, normalized_email)
    if user is None:
        user = User(
            keycloak_uuid=normalized_uuid,
            email=normalized_email,
            preferred_username=normalized_username or normalized_email,
            display_name=normalized_display_name,
            is_active=is_active,
        )
        session.add(user)
    else:
        user.keycloak_uuid = normalized_uuid
        user.email = normalized_email
        user.preferred_username = normalized_username or normalized_email
        user.display_name = normalized_display_name
        user.is_active = is_active

    if role_names is not None:
        user.roles = _fetch_roles_by_name(session, role_names)
    session.commit()
    session.refresh(user)
    user = get_managed_user(session, user.id)
    return _build_session_user_from_model(user, auth_source="oidc")


def update_managed_user_profile(
    session: Session,
    user_id: int,
    *,
    keycloak_uuid: str,
    email: str,
    preferred_username: str | None,
    display_name: str,
    is_active: bool | None = None,
) -> SessionUser:
    user = get_managed_user(session, user_id)

    normalized_uuid = keycloak_uuid.strip()
    normalized_email = _normalize_email(email)
    normalized_display_name = display_name.strip()
    normalized_username = preferred_username.strip() if isinstance(preferred_username, str) else ""

    if not normalized_uuid or not normalized_email or not normalized_display_name:
        raise ManagedUserProvisionError(
            "Impossible de mettre a jour le compte miroir: donnees Keycloak incompletes."
        )

    existing_user = _fetch_user_by_email(session, normalized_email)
    if existing_user is not None and existing_user.id != user.id:
        raise ManagedUserProvisionError(
            f"Un autre utilisateur miroir utilise deja l'email {normalized_email}."
        )

    user.keycloak_uuid = normalized_uuid
    user.email = normalized_email
    user.preferred_username = normalized_username or normalized_email
    user.display_name = normalized_display_name
    if is_active is not None:
        user.is_active = is_active

    session.commit()
    session.refresh(user)
    user = get_managed_user(session, user_id)
    return _build_session_user_from_model(user, auth_source="oidc")


def delete_managed_user(session: Session, user_id: int) -> User:
    user = get_managed_user(session, user_id)
    session.delete(user)
    session.commit()
    return user


def authenticate_bearer_user(
    session: Session,
    access_token: str,
    *,
    default_role_names: tuple[str, ...] = (),
    bootstrap_admin_emails: tuple[str, ...] = (),
) -> SessionUser:
    token_data = introspect_access_token(access_token=access_token)
    if not token_data.get("active"):
        raise OIDCError("Access token is inactive.")

    claims = fetch_userinfo(access_token=access_token)
    return sync_user_from_oidc_claims(
        session,
        claims,
        default_role_names=default_role_names,
        bootstrap_admin_emails=bootstrap_admin_emails,
    )


def list_managed_users(session: Session) -> list[User]:
    return session.scalars(_user_query().order_by(User.display_name, User.email)).all()


def list_roles(session: Session) -> list[Role]:
    statement = (
        select(Role)
        .options(selectinload(Role.permissions))
        .order_by(Role.name)
    )
    return session.scalars(statement).all()


def get_managed_user(session: Session, user_id: int) -> User:
    user = _fetch_user_by_id(session, user_id)
    if user is None:
        raise ManagedUserNotFoundError(f"Unknown user id {user_id}.")
    return user


def set_user_active(session: Session, user_id: int, *, is_active: bool) -> SessionUser:
    user = get_managed_user(session, user_id)
    user.is_active = is_active
    session.commit()
    session.refresh(user)
    user = get_managed_user(session, user_id)
    return _build_session_user_from_model(user, auth_source="oidc")


def replace_user_roles(session: Session, user_id: int, role_names: tuple[str, ...]) -> SessionUser:
    user = get_managed_user(session, user_id)
    user.roles = _fetch_roles_by_name(session, role_names)
    session.commit()
    session.refresh(user)
    user = get_managed_user(session, user_id)
    return _build_session_user_from_model(user, auth_source="oidc")


def serialize_user(user: User | SessionUser) -> dict[str, Any]:
    if isinstance(user, SessionUser):
        return {
            "id": user.user_id,
            "keycloak_uuid": user.keycloak_uuid,
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "roles": list(user.roles),
            "permissions": list(user.permissions),
            "is_active": user.is_active,
            "auth_source": user.auth_source,
        }

    return {
        "id": user.id,
        "keycloak_uuid": user.keycloak_uuid,
        "username": user.preferred_username or user.email,
        "email": user.email,
        "display_name": user.display_name,
        "roles": sorted(role.name for role in user.roles),
        "permissions": sorted(
            {
                permission.name
                for role in user.roles
                for permission in role.permissions
            }
        ),
        "is_active": user.is_active,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "auth_source": "oidc",
    }


def serialize_role(role: Role) -> dict[str, Any]:
    return {
        "name": role.name,
        "description": role.description,
        "permissions": sorted(permission.name for permission in role.permissions),
    }
