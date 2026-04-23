from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from .config import Settings


class OIDCError(RuntimeError):
    """Raised when the OIDC provider cannot complete a portal auth step."""


@dataclass(frozen=True)
class OIDCProviderMetadata:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    end_session_endpoint: str | None


def _build_ssl_context(settings: Settings) -> ssl.SSLContext:
    if settings.oidc_ca_cert_path:
        return ssl.create_default_context(cafile=settings.oidc_ca_cert_path)
    context = ssl.create_default_context()
    if not settings.oidc_verify_tls:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


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


def _json_request(
    settings: Settings,
    *,
    url: str,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    request = Request(
        url=url,
        data=data,
        method=method,
        headers=headers or {"Accept": "application/json"},
    )
    if "Accept" not in request.headers:
        request.add_header("Accept", "application/json")

    try:
        with urlopen(
            request,
            timeout=10,
            context=_build_ssl_context(settings),
        ) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as exc:  # pragma: no cover - exercised via integration only
        details = exc.read().decode("utf-8", errors="replace")
        raise OIDCError(f"OIDC endpoint {url} rejected the request: {exc.code} {details}") from exc
    except URLError as exc:  # pragma: no cover - exercised via integration only
        raise OIDCError(f"OIDC endpoint {url} is unreachable: {exc.reason}") from exc

    try:
        candidate = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise OIDCError(f"OIDC endpoint {url} did not return valid JSON.") from exc
    if not isinstance(candidate, dict):
        raise OIDCError(f"OIDC endpoint {url} returned an unexpected payload.")
    return candidate


@lru_cache(maxsize=8)
def fetch_provider_metadata(settings: Settings) -> OIDCProviderMetadata:
    if not settings.oidc_ready:
        raise OIDCError("OIDC is not fully configured for the portal.")

    discovery_url = settings.oidc_discovery_url or (
        f"{settings.oidc_issuer_url.rstrip('/')}/.well-known/openid-configuration"
    )
    payload = _json_request(settings, url=discovery_url)

    issuer = payload.get("issuer")
    authorization_endpoint = payload.get("authorization_endpoint")
    token_endpoint = payload.get("token_endpoint")
    userinfo_endpoint = payload.get("userinfo_endpoint")
    if not isinstance(issuer, str):
        raise OIDCError("OIDC discovery payload is missing 'issuer'.")
    if not isinstance(authorization_endpoint, str):
        raise OIDCError("OIDC discovery payload is missing 'authorization_endpoint'.")
    if not isinstance(token_endpoint, str):
        raise OIDCError("OIDC discovery payload is missing 'token_endpoint'.")
    if not isinstance(userinfo_endpoint, str):
        raise OIDCError("OIDC discovery payload is missing 'userinfo_endpoint'.")

    end_session_endpoint = payload.get("end_session_endpoint")
    if not isinstance(end_session_endpoint, str):
        end_session_endpoint = None

    return OIDCProviderMetadata(
        issuer=issuer,
        authorization_endpoint=authorization_endpoint,
        token_endpoint=_rewrite_backchannel_url(token_endpoint, settings.oidc_internal_base_url),
        userinfo_endpoint=_rewrite_backchannel_url(userinfo_endpoint, settings.oidc_internal_base_url),
        end_session_endpoint=end_session_endpoint,
    )


def build_authorization_url(settings: Settings, *, redirect_uri: str, state: str) -> str:
    metadata = fetch_provider_metadata(settings)
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


def exchange_authorization_code(
    settings: Settings,
    *,
    code: str,
    redirect_uri: str,
) -> dict[str, Any]:
    metadata = fetch_provider_metadata(settings)
    payload = urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": settings.oidc_client_id,
            "client_secret": settings.oidc_client_secret,
        }
    ).encode("utf-8")
    return _json_request(
        settings,
        url=metadata.token_endpoint,
        method="POST",
        data=payload,
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
    )


def fetch_userinfo(settings: Settings, *, access_token: str) -> dict[str, Any]:
    metadata = fetch_provider_metadata(settings)
    return _json_request(
        settings,
        url=metadata.userinfo_endpoint,
        headers={"Accept": "application/json", "Authorization": f"Bearer {access_token}"},
    )


def build_logout_url(
    settings: Settings,
    *,
    post_logout_redirect_uri: str,
    id_token_hint: str | None,
) -> str | None:
    if not settings.oidc_ready:
        return None

    metadata = fetch_provider_metadata(settings)
    if metadata.end_session_endpoint is None:
        return None

    payload = {
        "client_id": settings.oidc_client_id,
        "post_logout_redirect_uri": post_logout_redirect_uri,
    }
    if id_token_hint:
        payload["id_token_hint"] = id_token_hint
    return f"{metadata.end_session_endpoint}?{urlencode(payload)}"
