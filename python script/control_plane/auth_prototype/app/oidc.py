from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse

from .config import Settings, get_settings


class OIDCError(RuntimeError):
    """Raised when the OIDC provider cannot complete the requested action."""


@dataclass(frozen=True)
class OIDCProviderMetadata:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    end_session_endpoint: str | None
    introspection_endpoint: str | None


def _require_oidc(settings: Settings) -> None:
    if not settings.oidc_ready:
        raise OIDCError("OIDC is not fully configured.")


def _rewrite_backchannel_url(url: str, internal_base_url: str | None) -> str:
    if not internal_base_url:
        return url

    parsed = urlparse(url)
    internal = urlparse(internal_base_url)
    return urlunparse(
        (
            internal.scheme,
            internal.netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def _http_client(settings: Settings) -> Any:
    try:
        import httpx
    except ImportError as exc:
        raise OIDCError(
            "The 'httpx' dependency is required for OIDC. Install auth_prototype/requirements.txt first."
        ) from exc

    return httpx.Client(
        timeout=10.0,
        follow_redirects=True,
        verify=settings.oidc_verify_tls,
        headers={"Accept": "application/json"},
    )


@lru_cache(maxsize=1)
def fetch_provider_metadata() -> OIDCProviderMetadata:
    settings = get_settings()
    _require_oidc(settings)

    discovery_url = settings.oidc_discovery_url or (
        f"{settings.oidc_issuer_url.rstrip('/')}/.well-known/openid-configuration"
    )
    with _http_client(settings) as client:
        response = client.get(discovery_url)
        response.raise_for_status()
        payload = response.json()

    issuer = payload.get("issuer")
    authorization_endpoint = payload.get("authorization_endpoint")
    token_endpoint = payload.get("token_endpoint")
    userinfo_endpoint = payload.get("userinfo_endpoint")
    if not isinstance(issuer, str):
        raise OIDCError("OIDC discovery document is missing 'issuer'.")
    if not isinstance(authorization_endpoint, str):
        raise OIDCError("OIDC discovery document is missing 'authorization_endpoint'.")
    if not isinstance(token_endpoint, str):
        raise OIDCError("OIDC discovery document is missing 'token_endpoint'.")
    if not isinstance(userinfo_endpoint, str):
        raise OIDCError("OIDC discovery document is missing 'userinfo_endpoint'.")

    end_session_endpoint = payload.get("end_session_endpoint")
    if not isinstance(end_session_endpoint, str):
        end_session_endpoint = None

    introspection_endpoint = payload.get("introspection_endpoint")
    if not isinstance(introspection_endpoint, str):
        introspection_endpoint = None

    return OIDCProviderMetadata(
        issuer=issuer,
        authorization_endpoint=authorization_endpoint,
        token_endpoint=_rewrite_backchannel_url(token_endpoint, settings.oidc_internal_base_url),
        userinfo_endpoint=_rewrite_backchannel_url(userinfo_endpoint, settings.oidc_internal_base_url),
        end_session_endpoint=end_session_endpoint,
        introspection_endpoint=_rewrite_backchannel_url(
            introspection_endpoint,
            settings.oidc_internal_base_url,
        )
        if introspection_endpoint
        else None,
    )


def build_authorization_url(*, redirect_uri: str, state: str) -> str:
    settings = get_settings()
    _require_oidc(settings)
    metadata = fetch_provider_metadata()
    query = urlencode(
        {
            "client_id": settings.oidc_client_id,
            "response_type": "code",
            "scope": " ".join(settings.oidc_scopes),
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    return f"{metadata.authorization_endpoint}?{query}"


def exchange_authorization_code(*, code: str, redirect_uri: str) -> dict[str, Any]:
    settings = get_settings()
    _require_oidc(settings)
    metadata = fetch_provider_metadata()
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": settings.oidc_client_id,
        "client_secret": settings.oidc_client_secret,
    }
    with _http_client(settings) as client:
        response = client.post(metadata.token_endpoint, data=payload)
        response.raise_for_status()
        return response.json()


def fetch_userinfo(*, access_token: str) -> dict[str, Any]:
    settings = get_settings()
    _require_oidc(settings)
    metadata = fetch_provider_metadata()
    with _http_client(settings) as client:
        response = client.get(
            metadata.userinfo_endpoint,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()


def introspect_access_token(*, access_token: str) -> dict[str, Any]:
    settings = get_settings()
    _require_oidc(settings)
    metadata = fetch_provider_metadata()
    if metadata.introspection_endpoint is None:
        raise OIDCError("OIDC provider does not expose an introspection endpoint.")

    payload = {
        "token": access_token,
        "client_id": settings.oidc_client_id,
        "client_secret": settings.oidc_client_secret,
    }
    with _http_client(settings) as client:
        response = client.post(metadata.introspection_endpoint, data=payload)
        response.raise_for_status()
        return response.json()


def build_logout_url(*, post_logout_redirect_uri: str, id_token_hint: str | None = None) -> str | None:
    settings = get_settings()
    if not settings.oidc_ready:
        return None

    metadata = fetch_provider_metadata()
    if metadata.end_session_endpoint is None:
        return None

    payload = {"post_logout_redirect_uri": post_logout_redirect_uri}
    if id_token_hint:
        payload["id_token_hint"] = id_token_hint
    elif settings.oidc_client_id:
        # Keycloak can reject post-logout redirects without either an
        # id_token_hint or a client_id. The client_id fallback lets older local
        # sessions logout cleanly even if they were created before we stored the
        # ID token in the signed session.
        payload["client_id"] = settings.oidc_client_id
    return f"{metadata.end_session_endpoint}?{urlencode(payload)}"
