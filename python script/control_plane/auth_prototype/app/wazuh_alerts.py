from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from .config import Settings


class WazuhAlertsError(RuntimeError):
    """Raised when the Wazuh alert connector cannot complete a request."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_timestamp(value: str | None) -> str:
    cleaned = _clean_optional(value)
    if cleaned is None:
        return _utcnow_iso()

    candidate = cleaned
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    elif len(candidate) >= 5 and candidate[-5] in {"+", "-"} and candidate[-3] != ":":
        candidate = f"{candidate[:-2]}:{candidate[-2:]}"

    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return cleaned

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _httpx_module() -> Any:
    try:
        import httpx
    except ImportError as exc:
        raise WazuhAlertsError("La dependance 'httpx' est requise pour lire les alertes Wazuh.") from exc
    return httpx


def _verify_context(settings: Settings) -> bool | str:
    return settings.wazuh_alerts_ca_cert_path or settings.wazuh_alerts_verify_tls


def _severity_and_priority(rule_level: int) -> tuple[str, int]:
    if rule_level >= 12:
        return "critical", 1
    if rule_level >= 7:
        return "warning", 2
    if rule_level >= 4:
        return "degraded", 3
    return "info", 4


def _build_owner_hint(agent_id: str | None, groups: list[str]) -> str:
    if agent_id == "000":
        return "Equipe plateforme / cyber"
    if any(group in {"cascadya", "gateway_modbus", "telemetry_publisher"} for group in groups):
        return "Equipe exploitation / IPC"
    return "Equipe exploitation / cyber"


def _build_next_step(agent_id: str | None, groups: list[str]) -> str:
    if "gateway_modbus" in groups:
        return "Ouvrir Wazuh puis verifier gateway_modbus.service et le chemin Modbus sur l'IPC."
    if "telemetry_publisher" in groups:
        return "Ouvrir Wazuh puis verifier telemetry_publisher.service et le flux NATS cote IPC."
    if agent_id == "000":
        return "Ouvrir Wazuh puis verifier les services du manager et la sante de la VM centrale."
    return "Ouvrir Wazuh puis qualifier l'alerte avant de lancer la remediation cible."


def _sanitize_tag(value: str) -> str:
    return value.strip().lower().replace(" ", "-").replace("/", "-")


def _build_tags(
    *,
    rule_id: str | None,
    rule_level: int,
    groups: list[str],
    agent_name: str | None,
) -> list[str]:
    tags = ["wazuh", f"level:{rule_level}"]
    if rule_id:
        tags.append(f"rule:{rule_id}")
    if agent_name:
        tags.append(f"agent:{_sanitize_tag(agent_name)}")
    for group in groups[:4]:
        tags.append(_sanitize_tag(group))
    return tags


def _normalize_hit(hit: dict[str, Any]) -> dict[str, Any] | None:
    source = hit.get("_source")
    if not isinstance(source, dict):
        return None

    rule = source.get("rule") if isinstance(source.get("rule"), dict) else {}
    agent = source.get("agent") if isinstance(source.get("agent"), dict) else {}
    manager = source.get("manager") if isinstance(source.get("manager"), dict) else {}

    timestamp = _normalize_timestamp(source.get("@timestamp") if isinstance(source.get("@timestamp"), str) else None)
    rule_id = _clean_optional(str(rule.get("id"))) if rule.get("id") is not None else None
    rule_level = _safe_int(rule.get("level"), 3)
    rule_description = _clean_optional(rule.get("description") if isinstance(rule.get("description"), str) else None)
    groups = [
        item.strip()
        for item in (rule.get("groups") if isinstance(rule.get("groups"), list) else [])
        if isinstance(item, str) and item.strip()
    ]
    agent_id = _clean_optional(agent.get("id") if isinstance(agent.get("id"), str) else None)
    agent_name = _clean_optional(agent.get("name") if isinstance(agent.get("name"), str) else None)
    agent_ip = _clean_optional(agent.get("ip") if isinstance(agent.get("ip"), str) else None)
    manager_name = _clean_optional(manager.get("name") if isinstance(manager.get("name"), str) else None) or "wazuh-dev1-s"
    location = _clean_optional(source.get("location") if isinstance(source.get("location"), str) else None)
    full_log = _clean_optional(source.get("full_log") if isinstance(source.get("full_log"), str) else None)

    severity, priority = _severity_and_priority(rule_level)
    title = rule_description or "Alerte Wazuh"
    summary = full_log or location or title
    site_label = agent_name or manager_name
    company = "Plateforme" if agent_id == "000" or site_label == manager_name else "Site / IPC"
    region = " / ".join(part for part in (agent_ip, manager_name) if part) or "Dev1"
    alert_id = _clean_optional(hit.get("_id") if isinstance(hit.get("_id"), str) else None)
    if alert_id is None:
        alert_id = f"wazuh-{timestamp}-{rule_id or 'unknown'}"

    return {
        "id": alert_id,
        "title": title,
        "summary": summary,
        "source": "Wazuh",
        "severity": severity,
        "priority": priority,
        "state": "new",
        "raised_at": timestamp,
        "company": company,
        "site_label": site_label,
        "region": region,
        "owner_hint": _build_owner_hint(agent_id, groups),
        "next_step": _build_next_step(agent_id, groups),
        "tags": _build_tags(rule_id=rule_id, rule_level=rule_level, groups=groups, agent_name=agent_name),
    }


def _connector_disabled_snapshot(message: str) -> dict[str, Any]:
    return {
        "source": {
            "kind": "wazuh-indexer",
            "configured": False,
            "healthy": False,
            "message": message,
        },
        "alerts": [],
        "generated_at": _utcnow_iso(),
    }


def _connector_error_snapshot(message: str) -> dict[str, Any]:
    return {
        "source": {
            "kind": "wazuh-indexer",
            "configured": True,
            "healthy": False,
            "message": message,
        },
        "alerts": [],
        "generated_at": _utcnow_iso(),
    }


async def build_live_alerts_snapshot(settings: Settings) -> dict[str, Any]:
    indexer_url = _clean_optional(settings.wazuh_alerts_indexer_url)
    username = _clean_optional(settings.wazuh_alerts_indexer_username)
    password = _clean_optional(settings.wazuh_alerts_indexer_password)

    if indexer_url is None or username is None or password is None:
        return _connector_disabled_snapshot(
            "Configurer AUTH_PROTO_WAZUH_ALERTS_INDEXER_URL, AUTH_PROTO_WAZUH_ALERTS_INDEXER_USERNAME "
            "et AUTH_PROTO_WAZUH_ALERTS_INDEXER_PASSWORD pour activer les alertes Wazuh live."
        )

    httpx = _httpx_module()
    safe_limit = max(1, min(settings.wazuh_alerts_page_size, 100))
    safe_min_rule_level = max(0, min(settings.wazuh_alerts_min_rule_level, 16))
    safe_timeout_seconds = max(3, settings.wazuh_alerts_timeout_seconds)
    encoded_index_pattern = quote(settings.wazuh_alerts_index_pattern, safe="*,-_")
    endpoint = f"{indexer_url.rstrip('/')}/{encoded_index_pattern}/_search"

    filters: list[dict[str, Any]] = []
    if safe_min_rule_level > 0:
        filters.append({"range": {"rule.level": {"gte": safe_min_rule_level}}})

    query: dict[str, Any] = {
        "size": safe_limit,
        "track_total_hits": False,
        "_source": [
            "@timestamp",
            "rule.id",
            "rule.level",
            "rule.description",
            "rule.groups",
            "agent.id",
            "agent.name",
            "agent.ip",
            "manager.name",
            "location",
            "full_log",
        ],
        "sort": [
            {"@timestamp": {"order": "desc", "unmapped_type": "date"}},
            {"rule.level": {"order": "desc", "unmapped_type": "long"}},
        ],
        "query": {"bool": {"filter": filters}} if filters else {"match_all": {}},
    }

    try:
        async with httpx.AsyncClient(
            timeout=safe_timeout_seconds,
            verify=_verify_context(settings),
            follow_redirects=True,
            headers={"Accept": "application/json"},
        ) as client:
            response = await client.post(
                endpoint,
                auth=(username, password),
                params={"ignore_unavailable": "true", "expand_wildcards": "open"},
                json=query,
            )
    except httpx.RequestError as exc:
        return _connector_error_snapshot(
            f"Echec d'acces a l'indexer Wazuh prive ({indexer_url}): {exc.__class__.__name__}: {exc}"
        )

    try:
        payload = response.json()
    except ValueError:
        payload = None

    if response.status_code >= 400:
        detail = response.text.strip()
        if isinstance(payload, dict):
            error_payload = payload.get("error")
            if isinstance(error_payload, dict):
                detail = str(error_payload.get("reason") or error_payload.get("root_cause") or detail)
            elif error_payload is not None:
                detail = str(error_payload)
        return _connector_error_snapshot(
            f"L'indexer Wazuh a refuse la requete d'alertes (HTTP {response.status_code}): {detail or 'aucun detail'}"
        )

    if not isinstance(payload, dict):
        return _connector_error_snapshot("L'indexer Wazuh a retourne un payload JSON inattendu.")

    hits_container = payload.get("hits")
    hits = hits_container.get("hits") if isinstance(hits_container, dict) else None
    if not isinstance(hits, list):
        return _connector_error_snapshot("La reponse de l'indexer Wazuh ne contient pas de liste d'alertes exploitable.")

    alerts = [normalized for hit in hits if isinstance(hit, dict) for normalized in [_normalize_hit(hit)] if normalized]
    message = (
        f"{len(alerts)} alertes Wazuh chargees depuis l'indexer prive."
        if alerts
        else "Aucune alerte Wazuh recente n'a ete retournee par l'indexer prive."
    )
    return {
        "source": {
            "kind": "wazuh-indexer",
            "configured": True,
            "healthy": True,
            "message": message,
        },
        "alerts": alerts,
        "generated_at": _utcnow_iso(),
    }
