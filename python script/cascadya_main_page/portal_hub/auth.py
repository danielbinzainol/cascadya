from __future__ import annotations

import base64
import json
from typing import Any
from urllib.parse import urlparse


def safe_next_path(raw_value: str | None, default: str = "/") -> str:
    if not raw_value:
        return default

    parsed = urlparse(raw_value)
    if parsed.scheme or parsed.netloc:
        return default
    if not raw_value.startswith("/") or raw_value.startswith("//"):
        return default
    return raw_value


def merge_claim_sets(*claim_sets: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for claim_set in claim_sets:
        merged = _deep_merge(merged, claim_set)
    return merged


def _deep_merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def decode_jwt_payload(token: str | None) -> dict[str, Any]:
    if not token:
        return {}

    parts = token.split(".")
    if len(parts) < 2:
        return {}

    payload = parts[1]
    padding = "=" * ((4 - (len(payload) % 4)) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload + padding)
        candidate = json.loads(decoded.decode("utf-8"))
    except (ValueError, TypeError, UnicodeDecodeError):
        return {}
    return candidate if isinstance(candidate, dict) else {}


def build_identity_from_claims(
    claims: dict[str, Any],
    *,
    client_id: str | None,
    auth_source: str,
    id_token: str | None = None,
) -> dict[str, Any]:
    sub = _claim_str(claims, "sub")
    email = _claim_str(claims, "email")
    username = (
        _claim_str(claims, "preferred_username")
        or _claim_str(claims, "username")
        or email
        or sub
        or "unknown"
    )
    display_name = _claim_str(claims, "name") or _display_name_from_parts(claims) or username
    roles = extract_role_names(claims, client_id=client_id)
    groups = extract_group_names(claims)
    tags = tuple(sorted(set(roles) | set(_group_tags(groups))))

    return {
        "sub": sub or username,
        "username": username,
        "display_name": display_name,
        "email": email,
        "roles": list(roles),
        "groups": list(groups),
        "tags": list(tags),
        "auth_source": auth_source,
        "id_token": id_token,
    }


def build_dev_identity(
    *,
    username: str,
    display_name: str,
    email: str,
    roles: tuple[str, ...],
) -> dict[str, Any]:
    tags = tuple(sorted(set(roles)))
    return {
        "sub": f"dev-{username}",
        "username": username,
        "display_name": display_name,
        "email": email,
        "roles": list(sorted(roles)),
        "groups": [],
        "tags": list(tags),
        "auth_source": "dev",
        "id_token": None,
    }


def normalize_session_identity(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    username = payload.get("username")
    display_name = payload.get("display_name")
    auth_source = payload.get("auth_source")
    if not isinstance(username, str) or not username:
        return None
    if not isinstance(display_name, str) or not display_name:
        return None
    if not isinstance(auth_source, str) or not auth_source:
        return None

    email = payload.get("email")
    sub = payload.get("sub")
    id_token = payload.get("id_token")
    roles = _normalize_str_list(payload.get("roles"))
    groups = _normalize_str_list(payload.get("groups"))
    tags = _normalize_str_list(payload.get("tags"))
    if sub is not None and not isinstance(sub, str):
        return None
    if email is not None and not isinstance(email, str):
        return None
    if id_token is not None and not isinstance(id_token, str):
        return None

    return {
        "sub": sub or username,
        "username": username,
        "display_name": display_name,
        "email": email,
        "roles": roles,
        "groups": groups,
        "tags": tags,
        "auth_source": auth_source,
        "id_token": id_token,
    }


def identity_has_any_tag(identity: dict[str, Any], required_tags: tuple[str, ...]) -> bool:
    if not required_tags:
        return True
    identity_tags = set(_normalize_str_list(identity.get("tags")))
    return bool(identity_tags.intersection(required_tags))


def extract_role_names(claims: dict[str, Any], *, client_id: str | None) -> tuple[str, ...]:
    role_names: set[str] = set(_normalize_str_list(claims.get("roles")))

    single_role = _claim_str(claims, "role")
    if single_role:
        role_names.add(single_role)

    realm_access = claims.get("realm_access")
    if isinstance(realm_access, dict):
        role_names.update(_normalize_str_list(realm_access.get("roles")))

    resource_access = claims.get("resource_access")
    if isinstance(resource_access, dict):
        for resource_name, resource_value in resource_access.items():
            if not isinstance(resource_value, dict):
                continue
            roles = _normalize_str_list(resource_value.get("roles"))
            role_names.update(roles)
            if client_id and resource_name == client_id:
                role_names.update(roles)

    return tuple(sorted(role_names))


def extract_group_names(claims: dict[str, Any]) -> tuple[str, ...]:
    group_names = set(_normalize_str_list(claims.get("groups")))
    group_names.update(_normalize_str_list(claims.get("group_membership")))
    return tuple(sorted(group_names))


def _display_name_from_parts(claims: dict[str, Any]) -> str | None:
    first_name = _claim_str(claims, "given_name")
    last_name = _claim_str(claims, "family_name")
    parts = [part for part in (first_name, last_name) if part]
    if parts:
        return " ".join(parts)
    return None


def _group_tags(groups: tuple[str, ...]) -> tuple[str, ...]:
    tags: set[str] = set()
    for group in groups:
        if not group:
            continue
        tags.add(group)
        trimmed = group.strip("/")
        if trimmed:
            tags.add(trimmed)
            tags.add(trimmed.split("/")[-1])
    return tuple(sorted(tags))


def _normalize_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _claim_str(claims: dict[str, Any], key: str) -> str | None:
    value = claims.get(key)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
