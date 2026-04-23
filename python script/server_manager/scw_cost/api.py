from __future__ import annotations

import json
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ApiError(RuntimeError):
    """Raised when the Scaleway API returns an error."""


class ScalewayApiClient:
    def __init__(self, secret_key: str, timeout_seconds: int = 30) -> None:
        self.secret_key = secret_key
        self.timeout_seconds = timeout_seconds
        self.base_url = "https://api.scaleway.com"
        self._ssl_context = ssl.create_default_context()

    def get_json(
        self, path: str, params: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any], dict[str, str]]:
        query = urlencode(
            {key: value for key, value in (params or {}).items() if value is not None}
        )
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        request = Request(
            url,
            headers={
                "X-Auth-Token": self.secret_key,
                "Content-Type": "application/json",
            },
            method="GET",
        )
        try:
            with urlopen(
                request,
                timeout=self.timeout_seconds,
                context=self._ssl_context,
            ) as response:
                payload = response.read().decode("utf-8")
                headers = {key: value for key, value in response.headers.items()}
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise ApiError(f"{exc.code} for {path}: {details}") from exc
        except URLError as exc:
            raise ApiError(f"Network error for {path}: {exc}") from exc

        if not payload.strip():
            return {}, headers
        return json.loads(payload), headers

    def list_paginated(
        self, path: str, list_key: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        page = 1
        per_page = 100
        items: list[dict[str, Any]] = []
        while True:
            page_params = dict(params or {})
            page_params.update({"page": page, "per_page": per_page})
            payload, headers = self.get_json(path, page_params)
            page_items = payload.get(list_key, [])
            if not isinstance(page_items, list):
                raise ApiError(
                    f"Unexpected payload for {path}: key {list_key!r} is not a list"
                )
            items.extend(page_items)

            total_count = int(headers.get("X-Total-Count", "0") or 0)
            if not page_items:
                break
            if total_count and len(items) >= total_count:
                break
            if len(page_items) < per_page:
                break
            page += 1
        return items

    def list_servers(self, zone: str) -> list[dict[str, Any]]:
        return self.list_paginated(f"/instance/v1/zones/{zone}/servers", "servers")

    def list_instance_volumes(self, zone: str) -> list[dict[str, Any]]:
        return self.list_paginated(f"/instance/v1/zones/{zone}/volumes", "volumes")

    def list_block_volumes(self, zone: str) -> list[dict[str, Any]]:
        return self.list_paginated(f"/block/v1/zones/{zone}/volumes", "volumes")

    def list_ips(self, zone: str) -> list[dict[str, Any]]:
        return self.list_paginated(f"/instance/v1/zones/{zone}/ips", "ips")

    def list_security_groups(self, zone: str) -> list[dict[str, Any]]:
        return self.list_paginated(
            f"/instance/v1/zones/{zone}/security_groups",
            "security_groups",
        )

    def list_security_group_rules(
        self, zone: str, security_group_id: str
    ) -> list[dict[str, Any]]:
        return self.list_paginated(
            f"/instance/v1/zones/{zone}/security_groups/{security_group_id}/rules",
            "rules",
        )

    def get_server_products(self, zone: str) -> dict[str, Any]:
        payload, _ = self.get_json(f"/instance/v1/zones/{zone}/products/servers")
        return payload
