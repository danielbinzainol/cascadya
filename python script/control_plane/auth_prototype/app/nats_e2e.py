from __future__ import annotations

import asyncio
import json
import re
import ssl
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

DEFAULT_NATS_E2E_TIMEOUT_SECONDS = 10.0
DEFAULT_NATS_MONITORING_PORT = 8222
DIRECT_NATS_PROBE_MODE = "direct_nats"
BROKER_PROXY_PROBE_MODE = "broker_proxy"

_DURATION_RE = re.compile(r"^\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>ns|us|ms|s|m|h)?\s*$")


class NatsE2EProbeError(RuntimeError):
    """Raised when the NATS request/reply probe cannot complete successfully."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso_timestamp_ms(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        normalized = cleaned[:-1] + "+00:00" if cleaned.endswith("Z") else cleaned
        return datetime.fromisoformat(normalized).timestamp() * 1000.0
    except ValueError:
        return None


def _derive_edge_round_trip_ms(reply_payload: Any) -> float | None:
    if not isinstance(reply_payload, dict):
        return None
    received_ms = _parse_iso_timestamp_ms(reply_payload.get("edge_received_at"))
    replied_ms = _parse_iso_timestamp_ms(reply_payload.get("edge_replied_at"))
    if received_ms is None or replied_ms is None:
        return None
    return round(max(replied_ms - received_ms, 0.0), 3)


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def derive_nats_monitoring_url(nats_url: str | None, *, explicit_url: str | None = None) -> str | None:
    explicit = _clean_optional(explicit_url)
    if explicit is not None:
        if "://" in explicit:
            return explicit
        return f"http://{explicit}"

    cleaned_nats_url = _clean_optional(nats_url)
    if cleaned_nats_url is None:
        return None

    parsed = urlsplit(cleaned_nats_url if "://" in cleaned_nats_url else f"tls://{cleaned_nats_url}")
    hostname = parsed.hostname
    if hostname is None:
        return None

    netloc = f"[{hostname}]" if ":" in hostname and not hostname.startswith("[") else hostname
    return urlunsplit(("http", f"{netloc}:{DEFAULT_NATS_MONITORING_PORT}", "", "", ""))


def parse_nats_duration_ms(raw_value: Any) -> float | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, (int, float)):
        return round(float(raw_value), 3)

    cleaned = _clean_optional(str(raw_value))
    if cleaned is None:
        return None
    cleaned = cleaned.replace("Âµ", "u").replace("µ", "u").replace("μ", "u")

    match = _DURATION_RE.match(cleaned)
    if match is None:
        return None

    value = float(match.group("value"))
    unit = match.group("unit") or "ms"
    multipliers = {
        "ns": 0.000001,
        "us": 0.001,
        "ms": 1.0,
        "s": 1000.0,
        "m": 60000.0,
        "h": 3600000.0,
    }
    return round(value * multipliers[unit], 3)


def _build_tls_context(*, ca_cert_path: str, client_cert_path: str, client_key_path: str) -> ssl.SSLContext:
    tls_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=ca_cert_path)
    tls_context.load_cert_chain(certfile=client_cert_path, keyfile=client_key_path)
    tls_context.check_hostname = False
    tls_context.verify_mode = ssl.CERT_REQUIRED
    return tls_context


def _build_https_verify_context(*, ca_cert_path: str | None) -> ssl.SSLContext | bool:
    if ca_cert_path is None:
        return True
    resolved_ca_cert = _ensure_file_exists(ca_cert_path, label="Broker probe CA certificate")
    tls_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=resolved_ca_cert)
    tls_context.check_hostname = False
    tls_context.verify_mode = ssl.CERT_REQUIRED
    return tls_context


def _ensure_file_exists(path: str, *, label: str) -> str:
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists():
        raise NatsE2EProbeError(f"{label} introuvable: {file_path}")
    if not file_path.is_file():
        raise NatsE2EProbeError(f"{label} n'est pas un fichier regulier: {file_path}")
    return str(file_path)


async def _fetch_monitoring_json(
    client: Any,
    url: str,
    *,
    warnings: list[str],
    label: str,
) -> dict[str, Any] | None:
    try:
        response = await client.get(url)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        warnings.append(f"Impossible de lire {label} sur {url}: {exc.__class__.__name__}: {exc}")
        return None

    if not isinstance(payload, dict):
        warnings.append(f"Le endpoint {label} a retourne un payload inattendu.")
        return None
    return payload


def _find_connection_by_name(
    connections: list[dict[str, Any]],
    *,
    exact_name: str | None = None,
    name_prefix: str | None = None,
) -> dict[str, Any] | None:
    for connection in connections:
        name = str(connection.get("name") or "")
        if exact_name is not None and name == exact_name:
            return connection
        if name_prefix is not None and name.startswith(name_prefix):
            return connection
    return None


def _serialize_connection_snapshot(connection: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(connection, dict):
        return None

    snapshot = {
        "cid": connection.get("cid"),
        "name": connection.get("name"),
        "ip": connection.get("ip"),
        "lang": connection.get("lang"),
        "version": connection.get("version"),
        "subscriptions": connection.get("subscriptions"),
        "in_msgs": connection.get("in_msgs"),
        "out_msgs": connection.get("out_msgs"),
        "in_bytes": connection.get("in_bytes"),
        "out_bytes": connection.get("out_bytes"),
        "pending_bytes": connection.get("pending_bytes"),
        "uptime": connection.get("uptime"),
        "idle": connection.get("idle"),
        "rtt": connection.get("rtt"),
    }
    snapshot["rtt_ms"] = parse_nats_duration_ms(connection.get("rtt"))
    return snapshot


def _empty_monitoring_connections() -> dict[str, Any]:
    return {
        "control_panel_probe": None,
        "gateway_modbus": None,
        "telemetry_publisher": None,
        "ems_light_bridge": None,
    }


def _summarize_varz(varz: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(varz, dict):
        return None
    return {
        "server_id": varz.get("server_id"),
        "server_name": varz.get("server_name"),
        "version": varz.get("version"),
        "host": varz.get("host"),
        "port": varz.get("port"),
        "connections": varz.get("connections"),
        "total_connections": varz.get("total_connections"),
        "routes": varz.get("routes"),
        "slow_consumers": varz.get("slow_consumers"),
        "in_msgs": varz.get("in_msgs"),
        "out_msgs": varz.get("out_msgs"),
        "in_bytes": varz.get("in_bytes"),
        "out_bytes": varz.get("out_bytes"),
    }


async def _fetch_monitoring_snapshot(
    *,
    monitoring_url: str | None,
    timeout_seconds: float,
    probe_connection_name: str,
    asset_name: str,
) -> dict[str, Any]:
    try:
        import httpx
    except ModuleNotFoundError as exc:
        return {
            "url": monitoring_url,
            "available": False,
            "warnings": [
                "La dependance Python 'httpx' est requise pour lire les endpoints de monitoring NATS.",
                f"ImportError: {exc}",
            ],
            "healthz": None,
            "varz": None,
            "connections": _empty_monitoring_connections(),
        }

    warnings: list[str] = []

    if monitoring_url is None:
        return {
            "url": None,
            "available": False,
            "warnings": ["Aucune URL de monitoring NATS n'a pu etre deduite pour ce broker."],
            "healthz": None,
            "varz": None,
            "connections": _empty_monitoring_connections(),
        }

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        base_url = monitoring_url.rstrip("/")
        healthz = await _fetch_monitoring_json(client, f"{base_url}/healthz", warnings=warnings, label="healthz")
        varz = await _fetch_monitoring_json(client, f"{base_url}/varz", warnings=warnings, label="varz")
        connz = await _fetch_monitoring_json(
            client,
            f"{base_url}/connz?limit=1024",
            warnings=warnings,
            label="connz",
        )

    raw_connections = connz.get("connections") if isinstance(connz, dict) else None
    connections = [item for item in raw_connections if isinstance(item, dict)] if isinstance(raw_connections, list) else []

    control_panel_probe = _find_connection_by_name(connections, exact_name=probe_connection_name)
    gateway_modbus = _find_connection_by_name(connections, exact_name=f"gateway_modbus_edge:{asset_name}")
    telemetry_publisher = _find_connection_by_name(
        connections,
        exact_name=f"telemetry_publisher_edge:{asset_name}",
    )

    return {
        "url": monitoring_url,
        "available": bool(healthz or varz or connz),
        "warnings": warnings,
        "healthz": healthz,
        "varz": _summarize_varz(varz),
        "connections": {
            "control_panel_probe": _serialize_connection_snapshot(control_panel_probe),
            "gateway_modbus": _serialize_connection_snapshot(gateway_modbus),
            "telemetry_publisher": _serialize_connection_snapshot(telemetry_publisher),
            "ems_light_bridge": None,
        },
    }


async def _fetch_monitoring_snapshot_for_named_connection(
    *,
    monitoring_url: str | None,
    timeout_seconds: float,
    connection_name: str,
) -> dict[str, Any]:
    try:
        import httpx
    except ModuleNotFoundError as exc:
        return {
            "url": monitoring_url,
            "available": False,
            "warnings": [
                "La dependance Python 'httpx' est requise pour lire les endpoints de monitoring NATS.",
                f"ImportError: {exc}",
            ],
            "healthz": None,
            "varz": None,
            "connections": _empty_monitoring_connections(),
        }

    warnings: list[str] = []

    if monitoring_url is None:
        return {
            "url": None,
            "available": False,
            "warnings": ["Aucune URL de monitoring NATS n'a pu etre deduite pour ce broker."],
            "healthz": None,
            "varz": None,
            "connections": _empty_monitoring_connections(),
        }

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        base_url = monitoring_url.rstrip("/")
        healthz = await _fetch_monitoring_json(client, f"{base_url}/healthz", warnings=warnings, label="healthz")
        varz = await _fetch_monitoring_json(client, f"{base_url}/varz", warnings=warnings, label="varz")
        connz = await _fetch_monitoring_json(
            client,
            f"{base_url}/connz?limit=1024",
            warnings=warnings,
            label="connz",
        )

    raw_connections = connz.get("connections") if isinstance(connz, dict) else None
    connections = [item for item in raw_connections if isinstance(item, dict)] if isinstance(raw_connections, list) else []
    ems_light_bridge = _find_connection_by_name(connections, exact_name=connection_name)
    if ems_light_bridge is None:
        warnings.append(f"Aucune connexion NATS nommee '{connection_name}' n'a ete trouvee dans /connz.")

    return {
        "url": monitoring_url,
        "available": bool(healthz or varz or connz),
        "warnings": warnings,
        "healthz": healthz,
        "varz": _summarize_varz(varz),
        "connections": {
            **_empty_monitoring_connections(),
            "ems_light_bridge": _serialize_connection_snapshot(ems_light_bridge),
        },
    }


async def run_nats_request_reply_probe_async(
    *,
    asset_name: str,
    nats_url: str,
    ping_subject: str,
    ca_cert_path: str,
    client_cert_path: str,
    client_key_path: str,
    monitoring_url: str | None = None,
    timeout_seconds: float = DEFAULT_NATS_E2E_TIMEOUT_SECONDS,
    probe_value: int | None = None,
) -> dict[str, Any]:
    try:
        import nats
    except ModuleNotFoundError as exc:
        raise NatsE2EProbeError(
            "La dependance Python 'nats-py' est requise pour lancer le probe E2E NATS."
        ) from exc

    cleaned_asset_name = _clean_optional(asset_name)
    cleaned_nats_url = _clean_optional(nats_url)
    cleaned_ping_subject = _clean_optional(ping_subject)

    if cleaned_asset_name is None:
        raise NatsE2EProbeError("Le nom d'asset/inventory_hostname est obligatoire pour le probe.")
    if cleaned_nats_url is None:
        raise NatsE2EProbeError("L'URL NATS edge-agent est obligatoire pour le probe.")
    if cleaned_ping_subject is None:
        raise NatsE2EProbeError("Le sujet NATS de ping edge-agent est obligatoire pour le probe.")

    resolved_ca_cert = _ensure_file_exists(ca_cert_path, label="CA certificate")
    resolved_client_cert = _ensure_file_exists(client_cert_path, label="Client certificate")
    resolved_client_key = _ensure_file_exists(client_key_path, label="Client key")

    request_id = uuid.uuid4().hex
    connection_name = f"control_panel_e2e_probe:{cleaned_asset_name}:{request_id[:8]}"
    request_counter = int(probe_value) if probe_value is not None else int(time.time() * 1000) % 32767
    request_payload = {
        "compteur": request_counter,
        "request_id": request_id,
        "control_panel_sent_at": _utcnow_iso(),
        "asset_name": cleaned_asset_name,
    }

    client = None
    raw_reply: Any = None
    round_trip_ms: float | None = None
    probe_nats_connect_ms: float | None = None
    probe_monitoring_fetch_ms: float | None = None

    try:
        connect_started = time.perf_counter()
        client = await nats.connect(
            cleaned_nats_url,
            tls=_build_tls_context(
                ca_cert_path=resolved_ca_cert,
                client_cert_path=resolved_client_cert,
                client_key_path=resolved_client_key,
            ),
            connect_timeout=timeout_seconds,
            name=connection_name,
        )
        await client.flush(timeout=timeout_seconds)
        probe_nats_connect_ms = round((time.perf_counter() - connect_started) * 1000.0, 3)

        started = time.perf_counter()
        reply_message = await client.request(
            cleaned_ping_subject,
            json.dumps(request_payload).encode("utf-8"),
            timeout=timeout_seconds,
        )
        round_trip_ms = round((time.perf_counter() - started) * 1000.0, 3)

        try:
            raw_reply = json.loads(reply_message.data.decode("utf-8"))
        except json.JSONDecodeError:
            raw_reply = {"raw": reply_message.data.decode("utf-8", errors="replace")}

        monitoring_started = time.perf_counter()
        monitoring = await _fetch_monitoring_snapshot(
            monitoring_url=derive_nats_monitoring_url(cleaned_nats_url, explicit_url=monitoring_url),
            timeout_seconds=timeout_seconds,
            probe_connection_name=connection_name,
            asset_name=cleaned_asset_name,
        )
        probe_monitoring_fetch_ms = round((time.perf_counter() - monitoring_started) * 1000.0, 3)
    except Exception as exc:
        raise NatsE2EProbeError(
            f"Echec du round-trip NATS edge-agent sur {cleaned_asset_name}: {exc.__class__.__name__}: {exc}"
        ) from exc
    finally:
        if client is not None:
            try:
                await client.close()
            except Exception:
                pass

    if not isinstance(raw_reply, dict):
        raise NatsE2EProbeError("La reponse du probe edge-agent n'est pas un objet JSON exploitable.")

    reply_status = str(raw_reply.get("status") or "").strip().lower()
    if reply_status != "ok":
        raise NatsE2EProbeError(
            f"Le probe edge-agent a repondu avec le statut '{reply_status or 'unknown'}': {raw_reply}"
        )

    probe_connection = monitoring["connections"]["control_panel_probe"]
    gateway_connection = monitoring["connections"]["gateway_modbus"]
    telemetry_connection = monitoring["connections"]["telemetry_publisher"]

    hops = [
        {
            "key": "control_panel_to_broker",
            "label": "Control panel probe channel RTT (/connz snapshot)",
            "latency_ms": probe_connection.get("rtt_ms") if isinstance(probe_connection, dict) else None,
            "source": "connz.rtt",
        },
        {
            "key": "broker_to_ipc_gateway",
            "label": "Industrial PC gateway_modbus channel RTT (/connz snapshot)",
            "latency_ms": gateway_connection.get("rtt_ms") if isinstance(gateway_connection, dict) else None,
            "source": "connz.rtt",
        },
        {
            "key": "broker_to_ipc_telemetry",
            "label": "Industrial PC telemetry_publisher channel RTT (/connz snapshot)",
            "latency_ms": telemetry_connection.get("rtt_ms") if isinstance(telemetry_connection, dict) else None,
            "source": "connz.rtt",
        },
        {
            "key": "nats_request_reply_total",
            "label": "Control Panel -> Broker -> Industrial PC -> Broker -> Control Panel",
            "latency_ms": round_trip_ms,
            "source": "request_reply.round_trip_ms",
        },
    ]

    warnings = list(monitoring.get("warnings") or [])
    if not monitoring.get("available"):
        warnings.append("Les endpoints de monitoring NATS ne sont pas accessibles depuis le control plane.")

    probe_internal_overhead_ms = (
        round(float(probe_nats_connect_ms or 0.0) + float(probe_monitoring_fetch_ms or 0.0), 3)
        if probe_nats_connect_ms is not None or probe_monitoring_fetch_ms is not None
        else None
    )

    return {
        "tested_at": _utcnow_iso(),
        "flow_key": "ems_site",
        "flow_label": "ems-site",
        "probe_mode": DIRECT_NATS_PROBE_MODE,
        "round_trip_label": "Control Panel -> Broker -> Industrial PC -> Broker -> Control Panel",
        "monitoring_visibility": "control_plane_direct",
        "request_id": request_id,
        "asset_name": cleaned_asset_name,
        "nats_url": cleaned_nats_url,
        "monitoring_url": monitoring.get("url"),
        "subject": cleaned_ping_subject,
        "request_payload": request_payload,
        "reply_payload": raw_reply,
        "summary": {
            "round_trip_ms": round_trip_ms,
            "control_plane_total_ms": round_trip_ms,
            "active_request_reply_ms": round_trip_ms,
            "transport_overhead_ms": None,
            "probe_internal_overhead_ms": probe_internal_overhead_ms,
            "probe_nats_connect_ms": probe_nats_connect_ms,
            "probe_monitoring_fetch_ms": probe_monitoring_fetch_ms,
            "broker_proxy_internal_ms": None,
            "probe_connection_rtt_ms": probe_connection.get("rtt_ms") if isinstance(probe_connection, dict) else None,
            "gateway_connection_rtt_ms": (
                gateway_connection.get("rtt_ms") if isinstance(gateway_connection, dict) else None
            ),
            "telemetry_connection_rtt_ms": (
                telemetry_connection.get("rtt_ms") if isinstance(telemetry_connection, dict) else None
            ),
            "ems_light_connection_rtt_ms": None,
            "reply_status": reply_status,
            "reply_value": raw_reply.get("valeur_retour"),
        },
        "hops": hops,
        "monitoring": monitoring,
        "warnings": warnings,
    }


async def run_monitoring_connection_probe_async(
    *,
    connection_name: str,
    connection_label: str,
    monitoring_url: str,
    timeout_seconds: float = DEFAULT_NATS_E2E_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    cleaned_connection_name = _clean_optional(connection_name)
    cleaned_connection_label = _clean_optional(connection_label) or cleaned_connection_name
    cleaned_monitoring_url = _clean_optional(monitoring_url)

    if cleaned_connection_name is None:
        raise NatsE2EProbeError("Le nom de connexion NATS a observer est obligatoire.")
    if cleaned_connection_label is None:
        raise NatsE2EProbeError("Le libelle de connexion NATS a observer est obligatoire.")
    if cleaned_monitoring_url is None:
        raise NatsE2EProbeError("L'URL de monitoring NATS est obligatoire pour observer une connexion.")

    monitoring_started = time.perf_counter()
    monitoring = await _fetch_monitoring_snapshot_for_named_connection(
        monitoring_url=cleaned_monitoring_url,
        timeout_seconds=timeout_seconds,
        connection_name=cleaned_connection_name,
    )
    monitoring_fetch_ms = round((time.perf_counter() - monitoring_started) * 1000.0, 3)

    observed_connection = monitoring["connections"]["ems_light_bridge"]
    if not isinstance(observed_connection, dict):
        raise NatsE2EProbeError(
            f"La connexion NATS '{cleaned_connection_name}' est introuvable dans /connz."
        )

    observed_rtt_ms = observed_connection.get("rtt_ms")
    if not isinstance(observed_rtt_ms, (int, float)):
        raise NatsE2EProbeError(
            f"La connexion NATS '{cleaned_connection_name}' n'expose pas de RTT exploitable dans /connz."
        )

    warnings = list(monitoring.get("warnings") or [])
    if not monitoring.get("available"):
        warnings.append("Les endpoints de monitoring NATS ne sont pas accessibles depuis le broker.")

    return {
        "tested_at": _utcnow_iso(),
        "request_id": uuid.uuid4().hex,
        "asset_name": cleaned_connection_label,
        "nats_url": "",
        "monitoring_url": monitoring.get("url"),
        "subject": cleaned_connection_name,
        "request_payload": {
            "probe_kind": "monitoring_connection",
            "connection_name": cleaned_connection_name,
            "connection_label": cleaned_connection_label,
        },
        "reply_payload": observed_connection,
        "summary": {
            "round_trip_ms": observed_rtt_ms,
            "control_plane_total_ms": observed_rtt_ms,
            "active_request_reply_ms": observed_rtt_ms,
            "transport_overhead_ms": None,
            "probe_internal_overhead_ms": monitoring_fetch_ms,
            "probe_monitoring_fetch_ms": monitoring_fetch_ms,
            "probe_connection_rtt_ms": None,
            "gateway_connection_rtt_ms": None,
            "telemetry_connection_rtt_ms": None,
            "ems_light_connection_rtt_ms": observed_rtt_ms,
            "reply_status": "ok",
            "reply_value": None,
        },
        "hops": [
            {
                "key": "ems_light_connection",
                "label": f"Broker VM -> {cleaned_connection_label} RTT (/connz snapshot)",
                "latency_ms": observed_rtt_ms,
                "source": "connz.rtt",
            },
            {
                "key": "nats_request_reply_total",
                "label": f"Broker VM -> {cleaned_connection_label}",
                "latency_ms": observed_rtt_ms,
                "source": "connz.rtt",
            },
        ],
        "monitoring": monitoring,
        "warnings": warnings,
    }


def _broker_probe_endpoint(broker_probe_url: str) -> str:
    cleaned_url = broker_probe_url.rstrip("/")
    if cleaned_url.endswith("/nats/e2e-probe"):
        return cleaned_url
    return f"{cleaned_url}/nats/e2e-probe"


def _broker_orders_endpoint(broker_probe_url: str) -> str:
    cleaned_url = broker_probe_url.rstrip("/")
    if cleaned_url.endswith("/orders/live"):
        return cleaned_url
    return f"{cleaned_url}/orders/live"


async def run_orders_probe_via_broker_async(
    *,
    broker_probe_url: str,
    broker_probe_token: str,
    broker_probe_ca_cert_path: str | None = None,
    limit: int = 50,
    timeout_seconds: float = DEFAULT_NATS_E2E_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    try:
        import httpx
    except ModuleNotFoundError as exc:
        raise NatsE2EProbeError(
            "La dependance Python 'httpx' est requise pour appeler le flux Orders cote broker."
        ) from exc

    cleaned_broker_probe_url = _clean_optional(broker_probe_url)
    cleaned_broker_probe_token = _clean_optional(broker_probe_token)

    if cleaned_broker_probe_url is None:
        raise NatsE2EProbeError("L'URL du probe broker control-plane est obligatoire.")
    if cleaned_broker_probe_token is None:
        raise NatsE2EProbeError("Le token du probe broker control-plane est obligatoire.")

    endpoint = _broker_orders_endpoint(cleaned_broker_probe_url)
    verify = _build_https_verify_context(ca_cert_path=broker_probe_ca_cert_path)
    safe_limit = max(1, min(int(limit), 500))
    http_timeout_seconds = max(float(timeout_seconds) + 5.0, float(timeout_seconds) * 1.25)

    try:
        async with httpx.AsyncClient(timeout=http_timeout_seconds, verify=verify) as client:
            response = await client.get(
                endpoint,
                headers={"Authorization": f"Bearer {cleaned_broker_probe_token}"},
                params={"limit": safe_limit},
            )
    except Exception as exc:
        raise NatsE2EProbeError(
            "Echec de lecture du flux Orders sur le broker "
            f"({cleaned_broker_probe_url}): {exc.__class__.__name__}: {exc}"
        ) from exc

    try:
        parsed_payload = response.json()
    except Exception:
        parsed_payload = None
    response_payload = parsed_payload if isinstance(parsed_payload, dict) else None

    if response.status_code >= 400:
        detail = (
            response_payload.get("detail")
            if response_payload is not None and response_payload.get("detail") is not None
            else response_payload.get("error")
            if response_payload is not None and response_payload.get("error") is not None
            else response.text
        )
        raise NatsE2EProbeError(
            f"Le broker control-plane a refuse le flux Orders ({response.status_code}): {detail}"
        )

    if response_payload is None:
        raise NatsE2EProbeError("Le broker control-plane a retourne un payload JSON inattendu pour le flux Orders.")

    return response_payload


async def run_nats_command_request_async(
    *,
    nats_url: str,
    command_subject: str,
    command_payload: dict[str, Any],
    ca_cert_path: str,
    client_cert_path: str,
    client_key_path: str,
    timeout_seconds: float = DEFAULT_NATS_E2E_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    try:
        import nats
    except ModuleNotFoundError as exc:
        raise NatsE2EProbeError(
            "La dependance Python 'nats-py' est requise pour envoyer une commande NATS."
        ) from exc

    cleaned_nats_url = _clean_optional(nats_url)
    cleaned_command_subject = _clean_optional(command_subject)
    if cleaned_nats_url is None:
        raise NatsE2EProbeError("L'URL NATS est obligatoire pour envoyer une commande.")
    if cleaned_command_subject is None:
        raise NatsE2EProbeError("Le sujet NATS de commande est obligatoire.")

    resolved_ca_cert = _ensure_file_exists(ca_cert_path, label="CA certificate")
    resolved_client_cert = _ensure_file_exists(client_cert_path, label="Client certificate")
    resolved_client_key = _ensure_file_exists(client_key_path, label="Client key")

    request_id = uuid.uuid4().hex
    payload = dict(command_payload)
    payload.setdefault("request_id", request_id)
    payload.setdefault("control_panel_sent_at", _utcnow_iso())

    client = None
    raw_reply: Any = None
    round_trip_ms: float | None = None

    try:
        client = await nats.connect(
            cleaned_nats_url,
            tls=_build_tls_context(
                ca_cert_path=resolved_ca_cert,
                client_cert_path=resolved_client_cert,
                client_key_path=resolved_client_key,
            ),
            connect_timeout=timeout_seconds,
            name=f"control_panel_order_dispatch:{request_id[:8]}",
        )
        await client.flush(timeout=timeout_seconds)

        started = time.perf_counter()
        reply_message = await client.request(
            cleaned_command_subject,
            json.dumps(payload).encode("utf-8"),
            timeout=timeout_seconds,
        )
        round_trip_ms = round((time.perf_counter() - started) * 1000.0, 3)

        try:
            raw_reply = json.loads(reply_message.data.decode("utf-8"))
        except json.JSONDecodeError:
            raw_reply = {"raw": reply_message.data.decode("utf-8", errors="replace")}
    except Exception as exc:
        raise NatsE2EProbeError(
            f"Echec de la commande NATS sur {cleaned_command_subject}: {exc.__class__.__name__}: {exc}"
        ) from exc
    finally:
        if client is not None:
            try:
                await client.close()
            except Exception:
                pass

    return {
        "status": "ok",
        "request_id": request_id,
        "subject": cleaned_command_subject,
        "tested_at": _utcnow_iso(),
        "round_trip_ms": round_trip_ms,
        "request_payload": payload,
        "reply_payload": raw_reply if isinstance(raw_reply, dict) else {"raw": raw_reply},
    }


async def run_nats_command_request_via_broker_async(
    *,
    broker_probe_url: str,
    broker_probe_token: str,
    command_subject: str,
    command_payload: dict[str, Any],
    broker_probe_ca_cert_path: str | None = None,
    timeout_seconds: float = DEFAULT_NATS_E2E_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    try:
        import httpx
    except ModuleNotFoundError as exc:
        raise NatsE2EProbeError(
            "La dependance Python 'httpx' est requise pour appeler le broker de commande."
        ) from exc

    cleaned_broker_probe_url = _clean_optional(broker_probe_url)
    cleaned_broker_probe_token = _clean_optional(broker_probe_token)
    cleaned_command_subject = _clean_optional(command_subject)

    if cleaned_broker_probe_url is None:
        raise NatsE2EProbeError("L'URL du probe broker control-plane est obligatoire.")
    if cleaned_broker_probe_token is None:
        raise NatsE2EProbeError("Le token du probe broker control-plane est obligatoire.")
    if cleaned_command_subject is None:
        raise NatsE2EProbeError("Le sujet NATS de commande est obligatoire.")

    endpoint = f"{cleaned_broker_probe_url.rstrip('/')}/orders/dispatch"
    verify = _build_https_verify_context(ca_cert_path=broker_probe_ca_cert_path)
    http_timeout_seconds = max(float(timeout_seconds) + 5.0, float(timeout_seconds) * 1.25)

    try:
        async with httpx.AsyncClient(timeout=http_timeout_seconds, verify=verify) as client:
            response = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {cleaned_broker_probe_token}"},
                json={
                    "subject": cleaned_command_subject,
                    "timeout_seconds": timeout_seconds,
                    "command_payload": command_payload,
                },
            )
    except Exception as exc:
        raise NatsE2EProbeError(
            "Echec de l'envoi de commande via le broker "
            f"({cleaned_broker_probe_url}): {exc.__class__.__name__}: {exc}"
        ) from exc

    try:
        parsed_payload = response.json()
    except Exception:
        parsed_payload = None
    response_payload = parsed_payload if isinstance(parsed_payload, dict) else None

    if response.status_code >= 400:
        detail = (
            response_payload.get("detail")
            if response_payload is not None and response_payload.get("detail") is not None
            else response_payload.get("error")
            if response_payload is not None and response_payload.get("error") is not None
            else response.text
        )
        raise NatsE2EProbeError(
            f"Le broker control-plane a refuse la commande ({response.status_code}): {detail}"
        )

    if response_payload is None:
        raise NatsE2EProbeError("Le broker control-plane a retourne un payload JSON inattendu pour la commande.")

    return response_payload


async def run_nats_request_reply_probe_via_broker_async(
    *,
    asset_name: str,
    ping_subject: str,
    broker_probe_url: str,
    broker_probe_token: str,
    broker_probe_ca_cert_path: str | None = None,
    timeout_seconds: float = DEFAULT_NATS_E2E_TIMEOUT_SECONDS,
    probe_value: int | None = None,
) -> dict[str, Any]:
    try:
        import httpx
    except ModuleNotFoundError as exc:
        raise NatsE2EProbeError(
            "La dependance Python 'httpx' est requise pour appeler le probe broker cote control-plane."
        ) from exc

    cleaned_asset_name = _clean_optional(asset_name)
    cleaned_ping_subject = _clean_optional(ping_subject)
    cleaned_broker_probe_url = _clean_optional(broker_probe_url)
    cleaned_broker_probe_token = _clean_optional(broker_probe_token)

    if cleaned_asset_name is None:
        raise NatsE2EProbeError("Le nom d'asset/inventory_hostname est obligatoire pour le probe.")
    if cleaned_ping_subject is None:
        raise NatsE2EProbeError("Le sujet NATS de ping edge-agent est obligatoire pour le probe.")
    if cleaned_broker_probe_url is None:
        raise NatsE2EProbeError("L'URL du probe broker control-plane est obligatoire.")
    if cleaned_broker_probe_token is None:
        raise NatsE2EProbeError("Le token du probe broker control-plane est obligatoire.")

    endpoint = _broker_probe_endpoint(cleaned_broker_probe_url)
    request_payload = {
        "asset_name": cleaned_asset_name,
        "ping_subject": cleaned_ping_subject,
        "timeout_seconds": timeout_seconds,
    }
    if probe_value is not None:
        request_payload["probe_value"] = int(probe_value)

    verify = _build_https_verify_context(ca_cert_path=broker_probe_ca_cert_path)
    http_timeout_seconds = max(float(timeout_seconds) + 5.0, float(timeout_seconds) * 1.25)

    try:
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=http_timeout_seconds, verify=verify) as client:
            response = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {cleaned_broker_probe_token}"},
                json=request_payload,
            )
        control_plane_total_ms = round((time.perf_counter() - started) * 1000.0, 3)
    except Exception as exc:
        raise NatsE2EProbeError(
            "Echec du probe broker control-plane "
            f"pour {cleaned_asset_name}: {exc.__class__.__name__}: {exc}"
        ) from exc

    response_payload: dict[str, Any] | None
    try:
        parsed_payload = response.json()
    except Exception:
        parsed_payload = None
    response_payload = parsed_payload if isinstance(parsed_payload, dict) else None

    if response.status_code >= 400:
        detail = (
            response_payload.get("detail")
            if response_payload is not None and response_payload.get("detail") is not None
            else response_payload.get("error")
            if response_payload is not None and response_payload.get("error") is not None
            else response.text
        )
        raise NatsE2EProbeError(
            f"Le broker control-plane a refuse le probe ({response.status_code}): {detail}"
        )

    if response_payload is None:
        raise NatsE2EProbeError("Le broker control-plane a retourne un payload JSON inattendu pour le probe.")

    summary = response_payload.get("summary")
    broker_local_request_reply_ms = None
    if isinstance(summary, dict):
        broker_local_request_reply_ms = summary.get("round_trip_ms")
        if not isinstance(broker_local_request_reply_ms, (int, float)):
            broker_local_request_reply_ms = None
        broker_proxy_handler_ms = summary.get("broker_proxy_handler_ms")
        if not isinstance(broker_proxy_handler_ms, (int, float)):
            broker_proxy_handler_ms = None
        probe_internal_overhead_ms = summary.get("probe_internal_overhead_ms")
        if not isinstance(probe_internal_overhead_ms, (int, float)):
            probe_internal_overhead_ms = (
                round(max(float(broker_proxy_handler_ms) - float(broker_local_request_reply_ms), 0.0), 3)
                if broker_proxy_handler_ms is not None and broker_local_request_reply_ms is not None
                else None
            )
        modbus_simulator_round_trip_ms = _derive_edge_round_trip_ms(response_payload.get("reply_payload"))
        control_panel_to_broker_active_ms = (
            round(max(control_plane_total_ms - float(broker_proxy_handler_ms), 0.0), 3)
            if broker_proxy_handler_ms is not None
            else None
        )
        broker_to_ipc_active_ms = (
            round(
                max(float(broker_local_request_reply_ms) - float(modbus_simulator_round_trip_ms), 0.0),
                3,
            )
            if broker_local_request_reply_ms is not None and modbus_simulator_round_trip_ms is not None
            else (
                round(float(summary.get("gateway_connection_rtt_ms")), 3)
                if isinstance(summary.get("gateway_connection_rtt_ms"), (int, float))
                else None
            )
        )
        transport_overhead_ms = (
            round(max(control_plane_total_ms - float(broker_local_request_reply_ms), 0.0), 3)
            if broker_local_request_reply_ms is not None
            else None
        )
        reconstructed_active_total_ms = (
            round(
                float(control_panel_to_broker_active_ms)
                + float(probe_internal_overhead_ms)
                + float(broker_to_ipc_active_ms)
                + float(modbus_simulator_round_trip_ms),
                3,
            )
            if control_panel_to_broker_active_ms is not None
            and probe_internal_overhead_ms is not None
            and broker_to_ipc_active_ms is not None
            and modbus_simulator_round_trip_ms is not None
            else None
        )
        summary["control_plane_total_ms"] = control_plane_total_ms
        summary["active_request_reply_ms"] = broker_local_request_reply_ms
        summary["transport_overhead_ms"] = transport_overhead_ms
        summary["round_trip_ms"] = control_plane_total_ms
        summary["broker_proxy_internal_ms"] = probe_internal_overhead_ms
        summary["control_panel_to_broker_active_ms"] = control_panel_to_broker_active_ms
        summary["broker_to_ipc_active_ms"] = broker_to_ipc_active_ms
        summary["modbus_simulator_round_trip_ms"] = modbus_simulator_round_trip_ms
        summary["reconstructed_active_total_ms"] = reconstructed_active_total_ms

    total_hop = next(
        (
            hop
            for hop in response_payload.get("hops", [])
            if isinstance(hop, dict) and hop.get("key") == "nats_request_reply_total"
        ),
        None,
    )
    probe_hop = next(
        (
            hop
            for hop in response_payload.get("hops", [])
            if isinstance(hop, dict) and hop.get("key") == "control_panel_to_broker"
        ),
        None,
    )
    if isinstance(probe_hop, dict):
        probe_hop["label"] = "Broker-local probe <-> NATS RTT (/connz snapshot)"

    if isinstance(summary, dict) and isinstance(broker_local_request_reply_ms, (int, float)):
        response_payload.setdefault("hops", []).insert(
            1,
            {
                "key": "broker_local_request_reply",
                "label": "Broker-local probe -> Industrial PC -> Broker-local probe",
                "latency_ms": broker_local_request_reply_ms,
                "source": "broker.request_reply.round_trip_ms",
            },
        )
        response_payload.setdefault("hops", []).insert(
            2,
            {
                "key": "broker_proxy_transport_overhead",
                "label": "Control Panel <-> Broker VM access",
                "latency_ms": summary.get("transport_overhead_ms"),
                "source": "broker_proxy.transport_overhead_ms",
            },
        )
    if isinstance(total_hop, dict):
        total_hop["label"] = "Control Panel -> Broker -> Industrial PC -> Broker -> Control Panel"
        total_hop["latency_ms"] = control_plane_total_ms

    response_payload["probe_mode"] = BROKER_PROXY_PROBE_MODE
    response_payload["flow_key"] = "ems_site"
    response_payload["flow_label"] = "ems-site"
    response_payload["round_trip_label"] = "Control Panel -> Broker -> Industrial PC -> Broker -> Control Panel"
    response_payload["monitoring_visibility"] = "broker_internal"
    return response_payload


async def run_monitoring_connection_probe_via_broker_async(
    *,
    broker_probe_url: str,
    broker_probe_token: str,
    connection_name: str,
    flow_label: str,
    broker_probe_ca_cert_path: str | None = None,
    timeout_seconds: float = DEFAULT_NATS_E2E_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    try:
        import httpx
    except ModuleNotFoundError as exc:
        raise NatsE2EProbeError(
            "La dependance Python 'httpx' est requise pour appeler le probe broker cote control-plane."
        ) from exc

    cleaned_broker_probe_url = _clean_optional(broker_probe_url)
    cleaned_broker_probe_token = _clean_optional(broker_probe_token)
    cleaned_connection_name = _clean_optional(connection_name)
    cleaned_flow_label = _clean_optional(flow_label) or cleaned_connection_name

    if cleaned_broker_probe_url is None:
        raise NatsE2EProbeError("L'URL du probe broker control-plane est obligatoire.")
    if cleaned_broker_probe_token is None:
        raise NatsE2EProbeError("Le token du probe broker control-plane est obligatoire.")
    if cleaned_connection_name is None:
        raise NatsE2EProbeError("Le nom de connexion ems-light a observer est obligatoire.")
    if cleaned_flow_label is None:
        raise NatsE2EProbeError("Le libelle du flux ems-light est obligatoire.")

    endpoint = _broker_probe_endpoint(cleaned_broker_probe_url)
    request_payload = {
        "probe_kind": "monitoring_connection",
        "connection_name": cleaned_connection_name,
        "connection_label": cleaned_flow_label,
        "timeout_seconds": timeout_seconds,
    }

    verify = _build_https_verify_context(ca_cert_path=broker_probe_ca_cert_path)
    http_timeout_seconds = max(float(timeout_seconds) + 5.0, float(timeout_seconds) * 1.25)

    try:
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=http_timeout_seconds, verify=verify) as client:
            response = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {cleaned_broker_probe_token}"},
                json=request_payload,
            )
        observed_http_total_ms = round((time.perf_counter() - started) * 1000.0, 3)
    except Exception as exc:
        raise NatsE2EProbeError(
            "Echec du probe broker control-plane "
            f"pour le flux {cleaned_flow_label}: {exc.__class__.__name__}: {exc}"
        ) from exc

    response_payload: dict[str, Any] | None
    try:
        parsed_payload = response.json()
    except Exception:
        parsed_payload = None
    response_payload = parsed_payload if isinstance(parsed_payload, dict) else None

    if response.status_code >= 400:
        detail = (
            response_payload.get("detail")
            if response_payload is not None and response_payload.get("detail") is not None
            else response_payload.get("error")
            if response_payload is not None and response_payload.get("error") is not None
            else response.text
        )
        raise NatsE2EProbeError(
            f"Le broker control-plane a refuse le probe ems-light ({response.status_code}): {detail}"
        )

    if response_payload is None:
        raise NatsE2EProbeError("Le broker control-plane a retourne un payload JSON inattendu pour le probe ems-light.")

    summary = response_payload.get("summary")
    broker_to_ems_light_ms = None
    if isinstance(summary, dict):
        broker_to_ems_light_ms = summary.get("ems_light_connection_rtt_ms")
        if not isinstance(broker_to_ems_light_ms, (int, float)):
            broker_to_ems_light_ms = summary.get("round_trip_ms")
        if not isinstance(broker_to_ems_light_ms, (int, float)):
            broker_to_ems_light_ms = None

        broker_handler_ms = summary.get("broker_proxy_handler_ms")
        if not isinstance(broker_handler_ms, (int, float)):
            broker_handler_ms = None

        control_panel_to_broker_active_ms = (
            round(max(observed_http_total_ms - float(broker_handler_ms), 0.0), 3)
            if broker_handler_ms is not None
            else observed_http_total_ms
        )
        broker_processing_ms = (
            round(float(broker_handler_ms), 3) if broker_handler_ms is not None else None
        )
        reconstructed_active_total_ms = (
            round(
                float(control_panel_to_broker_active_ms)
                + float(broker_processing_ms)
                + float(broker_to_ems_light_ms),
                3,
            )
            if broker_processing_ms is not None and broker_to_ems_light_ms is not None
            else (
                round(float(control_panel_to_broker_active_ms) + float(broker_to_ems_light_ms), 3)
                if broker_to_ems_light_ms is not None
                else control_panel_to_broker_active_ms
            )
        )

        summary["control_plane_total_ms"] = observed_http_total_ms
        summary["active_request_reply_ms"] = broker_to_ems_light_ms
        summary["transport_overhead_ms"] = control_panel_to_broker_active_ms
        summary["probe_connection_rtt_ms"] = control_panel_to_broker_active_ms
        summary["control_panel_to_broker_active_ms"] = control_panel_to_broker_active_ms
        summary["broker_proxy_internal_ms"] = broker_processing_ms
        summary["reconstructed_active_total_ms"] = reconstructed_active_total_ms
        summary["round_trip_ms"] = observed_http_total_ms

    total_hop = next(
        (
            hop
            for hop in response_payload.get("hops", [])
            if isinstance(hop, dict) and hop.get("key") == "nats_request_reply_total"
        ),
        None,
    )
    response_payload.setdefault("hops", []).insert(
        0,
        {
            "key": "control_panel_to_broker_proxy",
            "label": "Control Panel -> Broker VM",
            "latency_ms": summary.get("control_panel_to_broker_active_ms") if isinstance(summary, dict) else observed_http_total_ms,
            "source": "https.round_trip_ms",
        },
    )
    if isinstance(summary, dict):
        response_payload.setdefault("hops", []).insert(
            1,
            {
                "key": "broker_processing",
                "label": "Traitement broker",
                "latency_ms": summary.get("broker_proxy_internal_ms"),
                "source": "broker.handler_ms",
            },
        )
    if isinstance(total_hop, dict):
        total_hop["label"] = f"Control Panel -> Broker -> {cleaned_flow_label} -> Broker -> Control Panel"
        total_hop["latency_ms"] = (
            summary.get("reconstructed_active_total_ms")
            if isinstance(summary, dict) and summary.get("reconstructed_active_total_ms") is not None
            else summary.get("round_trip_ms") if isinstance(summary, dict) else None
        )

    response_payload["probe_mode"] = BROKER_PROXY_PROBE_MODE
    response_payload["flow_key"] = "ems_light"
    response_payload["flow_label"] = cleaned_flow_label
    response_payload["round_trip_label"] = f"Control Panel -> Broker -> {cleaned_flow_label} -> Broker -> Control Panel"
    response_payload["monitoring_visibility"] = "broker_internal"
    return response_payload


def run_nats_request_reply_probe(**kwargs: Any) -> dict[str, Any]:
    return asyncio.run(run_nats_request_reply_probe_async(**kwargs))


def run_nats_request_reply_probe_via_broker(**kwargs: Any) -> dict[str, Any]:
    return asyncio.run(run_nats_request_reply_probe_via_broker_async(**kwargs))


def run_monitoring_connection_probe(**kwargs: Any) -> dict[str, Any]:
    return asyncio.run(run_monitoring_connection_probe_async(**kwargs))


def run_monitoring_connection_probe_via_broker(**kwargs: Any) -> dict[str, Any]:
    return asyncio.run(run_monitoring_connection_probe_via_broker_async(**kwargs))


def run_orders_probe_via_broker(**kwargs: Any) -> dict[str, Any]:
    return asyncio.run(run_orders_probe_via_broker_async(**kwargs))


def run_nats_command_request(**kwargs: Any) -> dict[str, Any]:
    return asyncio.run(run_nats_command_request_async(**kwargs))


def run_nats_command_request_via_broker(**kwargs: Any) -> dict[str, Any]:
    return asyncio.run(run_nats_command_request_via_broker_async(**kwargs))
