from __future__ import annotations

import copy
import ipaddress
import json
import os
import queue
import re
import shlex
import shutil
import socket
import subprocess
import threading
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .config import Settings
from .models import InventoryAsset, InventoryScan, ProvisioningJob, Site
from .nats_e2e import derive_nats_monitoring_url

_REMOTE_SECTION_RE = re.compile(r"^__([A-Z0-9_]+)__$")
_REMOTE_IPV4_RE = re.compile(r"^\d+:\s+([^\s:]+)(?:@[^ ]+)?\s+inet\s+([0-9.]+)/(\d+)\b")
_REMOTE_MAC_RE = re.compile(r"^[0-9a-f]{2}(?::[0-9a-f]{2}){5}$", re.IGNORECASE)
DEFAULT_EDGE_AGENT_MODBUS_HOST = "192.168.50.2"
DEFAULT_EDGE_AGENT_NATS_URL = "tls://10.30.0.1:4222"
LEGACY_EDGE_AGENT_NATS_URLS = {
    "100.103.71.126:4222",
    "nats://100.103.71.126:4222",
    "tls://100.103.71.126:4222",
}
DEFAULT_EDGE_AGENT_VAULT_PKI_MOUNT = "pki_int"
DEFAULT_EDGE_AGENT_VAULT_ROLE = "devices-role"
DEFAULT_EDGE_AGENT_CERT_TTL = "720h"
DEFAULT_WAZUH_AGENT_MANAGER_PORT = 1514
DEFAULT_WAZUH_AGENT_REGISTRATION_PORT = 1515
DEFAULT_WAZUH_AGENT_PROTOCOL = "tcp"
DEFAULT_IPC_ALLOY_MIMIR_REMOTE_WRITE_URL = "http://10.42.1.4:9009/api/v1/push"
DEFAULT_IPC_ALLOY_SCRAPE_INTERVAL = "15s"
DEFAULT_IPC_ALLOY_SCRAPE_TIMEOUT = "10s"
DEFAULT_IPC_ALLOY_TENANT = "classic"
DEFAULT_IPC_ALLOY_RETENTION_PROFILE = "classic"
IPC_ALLOY_ALLOWED_TENANTS = ("classic", "lts-1y", "lts-5y")
DEFAULT_IPC_ALLOY_NODE_EXPORTER_PORT = 9100
DEFAULT_IPC_ALLOY_HTTP_LISTEN_ADDRESS = "127.0.0.1:12345"
DEFAULT_REMOTE_UNLOCK_BROKER_URL = "https://10.30.0.1:8443"
DEFAULT_REMOTE_UNLOCK_WG_INTERFACE = "wg0"
DEFAULT_REMOTE_UNLOCK_BOOTSTRAP_NAMESERVERS = ["1.1.1.1", "8.8.8.8"]
DEFAULT_REMOTE_UNLOCK_ALLOWED_IPS = ["10.30.0.1/32"]
DEFAULT_REMOTE_UNLOCK_WG_ENDPOINT = "REPLACE_BROKER_IP:51820"
DEFAULT_REMOTE_UNLOCK_PEER_PUBLIC_KEY = "REPLACE_BROKER_PUBLIC_KEY"
DEFAULT_REMOTE_UNLOCK_PRIVATE_KEY = "REPLACE_DEVICE_PRIVATE_KEY"
DEFAULT_PROVISIONING_WORKFLOW_KEY = "full-ipc-wireguard-onboarding"
PROVISIONING_DISPATCH_MODES = {"auto", "manual"}
REMOTE_UNLOCK_SEED_VAULT_STEP_KEY = "remote-unlock-seed-vault-secret"
REMOTE_UNLOCK_SEED_VAULT_PLAYBOOK = "remote-unlock-seed-vault-secret.yml"
IPC_NETWORK_PERSIST_STEP_KEY = "ipc-persist-network-routing"
IPC_NETWORK_PERSIST_PLAYBOOK = "ipc-persist-network-routing.yml"
EDGE_AGENT_GENERATE_CERTS_STEP_KEY = "edge-agent-generate-certs"
EDGE_AGENT_GENERATE_CERTS_PLAYBOOK = "edge-agent-generate-certs.yml"
EDGE_AGENT_NATS_ROUNDTRIP_STEP_KEY = "edge-agent-nats-roundtrip"
EDGE_AGENT_NATS_ROUNDTRIP_PLAYBOOK = "edge-agent-nats-roundtrip.yml"
WAZUH_AGENT_DEPLOY_STEP_KEY = "wazuh-agent-deploy"
WAZUH_AGENT_DEPLOY_PLAYBOOK = "wazuh-agent-deploy.yml"
WAZUH_AGENT_VALIDATE_STEP_KEY = "wazuh-agent-validate"
WAZUH_AGENT_VALIDATE_PLAYBOOK = "wazuh-agent-validate.yml"
IPC_ALLOY_DEPLOY_STEP_KEY = "ipc-alloy-deploy"
IPC_ALLOY_DEPLOY_PLAYBOOK = "ipc-alloy-deploy.yml"
IPC_ALLOY_VALIDATE_STEP_KEY = "ipc-alloy-validate"
IPC_ALLOY_VALIDATE_PLAYBOOK = "ipc-alloy-validate.yml"
MAX_COMMAND_PREVIEW_LENGTH = 2000


class FleetError(RuntimeError):
    """Base error for sites, inventory and provisioning operations."""


class FleetNotFoundError(FleetError):
    """Raised when a requested fleet entity does not exist."""


class FleetValidationError(FleetError):
    """Raised when a fleet operation cannot be applied."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _clean_required(value: str | None, field_name: str) -> str:
    cleaned = _clean_optional(value)
    if cleaned is None:
        raise FleetValidationError(f"Le champ '{field_name}' est obligatoire.")
    return cleaned


def _normalize_edge_agent_nats_url(value: Any) -> str:
    cleaned = _clean_optional(str(value)) if value is not None else None
    if cleaned is None:
        return DEFAULT_EDGE_AGENT_NATS_URL
    if cleaned.rstrip("/").lower() in LEGACY_EDGE_AGENT_NATS_URLS:
        return DEFAULT_EDGE_AGENT_NATS_URL
    return cleaned


def _normalize_ip(value: str | None, *, field_name: str) -> str | None:
    cleaned = _clean_optional(value)
    if cleaned is None:
        return None
    try:
        return str(ipaddress.ip_address(cleaned))
    except ValueError as exc:
        raise FleetValidationError(f"Le champ '{field_name}' doit contenir une adresse IP valide.") from exc


def _slugify(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .strip()
        .lower()
    )
    return re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")


def _normalize_site_code(value: str | None) -> str:
    cleaned = _clean_required(value, "site_code")
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "-", cleaned).strip("-").upper()
    if not normalized:
        raise FleetValidationError("Le code site ne peut pas etre vide.")
    return normalized


def _normalize_hostname(value: str | None, *, field_name: str) -> str:
    cleaned = _clean_required(value, field_name).lower()
    normalized = re.sub(r"[^a-z0-9-]+", "-", cleaned).strip("-")
    if not normalized:
        raise FleetValidationError(f"Le champ '{field_name}' ne produit pas un hostname valide.")
    return normalized


def _normalize_dispatch_mode(value: Any) -> str:
    cleaned = _clean_optional(str(value)) if value is not None else None
    normalized = (cleaned or "auto").lower()
    if normalized not in PROVISIONING_DISPATCH_MODES:
        raise FleetValidationError("Le mode de lancement doit etre 'auto' ou 'manual'.")
    return normalized


def _default_gateway_for_ip(target_ip: str) -> str:
    network = ipaddress.ip_interface(f"{target_ip}/24").network
    hosts = list(network.hosts())
    if not hosts:
        return target_ip
    return str(hosts[0])


def _mac_from_ip(target_ip: str) -> str:
    octets = [int(part) for part in target_ip.split(".")]
    return ":".join(f"{value:02X}" for value in (0x02, 0xCA, *octets))


def _suggest_device_identity(target_ip: str) -> dict[str, str]:
    octets = [int(part) for part in target_ip.split(".")]
    selector = sum(octets) % 3
    suggestions = [
        {"vendor": "Advantech", "model": "UNO-2484G", "management_interface": "enp3s0", "uplink_interface": "enp2s0"},
        {"vendor": "OnLogic", "model": "Helix 401", "management_interface": "enp3s0", "uplink_interface": "enp2s0"},
        {"vendor": "Beckhoff", "model": "C6030", "management_interface": "enp3s0", "uplink_interface": "enp2s0"},
    ]
    choice = suggestions[selector]
    return {
        **choice,
        "hostname": f"ipc-{octets[2]}-{octets[3]}",
        "inventory_hostname": f"cascadya-ipc-{octets[2]}-{octets[3]}",
        "wireguard_address": f"10.30.{octets[2]}.{octets[3]}/32",
    }


def _default_provisioning_vars(
    *,
    management_interface: str | None,
    uplink_interface: str | None,
    ansible_user: str | None = None,
    ansible_port: int | None = None,
    modbus_host: str | None = None,
) -> dict[str, str]:
    defaults = {
        "remote_unlock_transport_mode": "wireguard",
        "remote_unlock_management_interface": management_interface or "enp3s0",
        "remote_unlock_uplink_interface": uplink_interface or "enp2s0",
        "edge_agent_modbus_host": modbus_host or DEFAULT_EDGE_AGENT_MODBUS_HOST,
        "edge_agent_nats_url": DEFAULT_EDGE_AGENT_NATS_URL,
    }
    if ansible_user:
        defaults["ansible_user"] = ansible_user
    if ansible_port:
        defaults["ansible_port"] = str(ansible_port)
    return defaults


def _clean_provisioning_vars(provisioning_vars: dict[str, Any] | None) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in (provisioning_vars or {}).items():
        if not isinstance(key, str):
            continue
        if value is None:
            continue
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                continue
            cleaned[key] = _normalize_edge_agent_nats_url(stripped) if key == "edge_agent_nats_url" else stripped
            continue
        cleaned[key] = _normalize_edge_agent_nats_url(value) if key == "edge_agent_nats_url" else value
    return cleaned


def _coerce_string_list(value: Any, *, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        return [cleaned for item in value if (cleaned := _clean_optional(str(item)))]
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [cleaned for item in parsed if (cleaned := _clean_optional(str(item)))]
        cleaned = _clean_optional(stripped)
        if cleaned:
            return [cleaned]
    return list(fallback)


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    cleaned = _clean_optional(str(value))
    if cleaned is None:
        return default
    return cleaned.lower() in {"1", "true", "yes", "on"}


def _json_preview(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def _normalize_port(value: int | None, *, field_name: str, default: int) -> int:
    candidate = default if value is None else value
    if candidate < 1 or candidate > 65535:
        raise FleetValidationError(f"Le champ '{field_name}' doit etre un port TCP valide.")
    return candidate


def _coerce_optional_int(value: Any, *, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise FleetValidationError(f"Le champ '{field_name}' doit etre un entier.")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    cleaned = _clean_optional(str(value))
    if cleaned is None:
        return None
    try:
        return int(cleaned)
    except ValueError as exc:
        raise FleetValidationError(f"Le champ '{field_name}' doit etre un entier valide.") from exc


def _extract_endpoint_host_and_port(value: Any) -> tuple[str | None, int | None]:
    cleaned = _clean_optional(str(value)) if value is not None else None
    if cleaned is None:
        return None, None
    parsed = urlsplit(cleaned if "://" in cleaned else f"//{cleaned}")
    return _clean_optional(parsed.hostname), parsed.port


def _normalize_ipc_alloy_profile(value: Any, *, field_name: str) -> str | None:
    cleaned = _clean_optional(str(value)) if value is not None else None
    if cleaned is None:
        return None
    if cleaned not in IPC_ALLOY_ALLOWED_TENANTS:
        raise FleetValidationError(
            f"Le champ '{field_name}' doit valoir classic, lts-1y ou lts-5y."
        )
    return cleaned


def _resolve_ipc_alloy_contract(
    provisioning_vars: dict[str, Any],
    *,
    settings: Settings,
) -> tuple[str, str]:
    default_tenant = _normalize_ipc_alloy_profile(
        settings.provisioning_ipc_alloy_tenant_default,
        field_name="AUTH_PROTO_PROVISIONING_IPC_ALLOY_TENANT_DEFAULT",
    ) or DEFAULT_IPC_ALLOY_TENANT
    default_retention_profile = _normalize_ipc_alloy_profile(
        settings.provisioning_ipc_alloy_retention_profile_default,
        field_name="AUTH_PROTO_PROVISIONING_IPC_ALLOY_RETENTION_PROFILE_DEFAULT",
    ) or default_tenant
    if default_tenant != default_retention_profile:
        raise FleetValidationError(
            "La configuration globale IPC Alloy du control-panel doit garder "
            "AUTH_PROTO_PROVISIONING_IPC_ALLOY_TENANT_DEFAULT et "
            "AUTH_PROTO_PROVISIONING_IPC_ALLOY_RETENTION_PROFILE_DEFAULT alignes."
        )

    tenant = _normalize_ipc_alloy_profile(
        provisioning_vars.get("ipc_alloy_mimir_tenant"),
        field_name="ipc_alloy_mimir_tenant",
    )
    retention_profile = _normalize_ipc_alloy_profile(
        provisioning_vars.get("ipc_alloy_retention_profile"),
        field_name="ipc_alloy_retention_profile",
    )
    if tenant is not None and retention_profile is not None and tenant != retention_profile:
        raise FleetValidationError(
            "Le contrat IPC Alloy doit garder ipc_alloy_mimir_tenant et "
            "ipc_alloy_retention_profile alignes (`classic`, `lts-1y`, `lts-5y`)."
        )

    effective_profile = tenant or retention_profile or default_tenant
    return effective_profile, effective_profile


def _normalize_discovery_mode(value: str | None) -> str:
    normalized = (value or "auto").strip().lower()
    if normalized not in {"auto", "mock", "tcp", "ssh"}:
        raise FleetValidationError(
            "AUTH_PROTO_DISCOVERY_MODE doit etre l'une des valeurs suivantes: auto, mock, tcp, ssh."
        )
    return normalized


def _strip_interface_alias(interface_name: str) -> str:
    return interface_name.split("@", 1)[0].strip()


def _first_non_empty(lines: list[str]) -> str | None:
    for line in lines:
        cleaned = line.strip()
        if cleaned:
            return cleaned
    return None


def _format_socket_error(exc: OSError) -> str:
    message = str(exc).strip()
    if message:
        return message
    return exc.__class__.__name__


def _probe_tcp_port(host: str, *, port: int, timeout_seconds: int) -> dict[str, Any]:
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return {"reachable": True, "error": None}
    except OSError as exc:
        return {"reachable": False, "error": _format_socket_error(exc)}


def _build_remote_discovery_script() -> str:
    return """#!/bin/sh
set -u
DOWNSTREAM_IP="${1:-}"

echo "__HOSTNAME__"
(hostnamectl --static 2>/dev/null || hostname 2>/dev/null || true) | head -n 1

echo "__IPV4__"
ip -o -4 addr show scope global 2>/dev/null || true

echo "__ROUTE_DEFAULT__"
ip route show default 2>/dev/null || true

echo "__ROUTE_DOWNSTREAM__"
if [ -n "$DOWNSTREAM_IP" ]; then
  ip route get "$DOWNSTREAM_IP" 2>/dev/null || true
fi

echo "__MACS__"
for dev in /sys/class/net/*; do
  name="$(basename "$dev")"
  if [ -r "$dev/address" ]; then
    printf '%s %s\\n' "$name" "$(cat "$dev/address")"
  fi
done

echo "__SYS_VENDOR__"
cat /sys/devices/virtual/dmi/id/sys_vendor 2>/dev/null || true

echo "__PRODUCT_NAME__"
cat /sys/devices/virtual/dmi/id/product_name 2>/dev/null || true

echo "__PRODUCT_SERIAL__"
cat /sys/devices/virtual/dmi/id/product_serial 2>/dev/null || true

echo "__DOWNSTREAM_PING__"
if [ -n "$DOWNSTREAM_IP" ]; then
  if ping -c 1 -W 1 "$DOWNSTREAM_IP" >/dev/null 2>&1; then
    echo "reachable"
  else
    echo "unreachable"
  fi
fi

echo "__END__"
"""


def _split_remote_sections(output: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current_section: str | None = None
    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        match = _REMOTE_SECTION_RE.match(line.strip())
        if match:
            current_section = match.group(1)
            sections.setdefault(current_section, [])
            continue
        if current_section is not None:
            sections[current_section].append(line)
    return sections


def _parse_remote_ipv4(lines: list[str]) -> list[dict[str, str]]:
    addresses: list[dict[str, str]] = []
    for line in lines:
        match = _REMOTE_IPV4_RE.match(line.strip())
        if not match:
            continue
        interface_name = _strip_interface_alias(match.group(1))
        ip_value = match.group(2)
        prefix = match.group(3)
        addresses.append(
            {
                "interface": interface_name,
                "ip": ip_value,
                "cidr": f"{ip_value}/{prefix}",
            }
        )
    return addresses


def _parse_remote_macs(lines: list[str]) -> dict[str, str]:
    macs: dict[str, str] = {}
    for line in lines:
        parts = line.strip().split()
        if len(parts) < 2:
            continue
        interface_name = _strip_interface_alias(parts[0])
        mac_address = parts[1].lower()
        if not _REMOTE_MAC_RE.match(mac_address):
            continue
        macs[interface_name] = mac_address.upper()
    return macs


def _parse_default_route(lines: list[str]) -> tuple[str | None, str | None]:
    route_line = _first_non_empty(lines)
    if route_line is None:
        return None, None
    gateway_match = re.search(r"\bvia\s+([0-9.]+)\b", route_line)
    interface_match = re.search(r"\bdev\s+(\S+)\b", route_line)
    return (
        gateway_match.group(1) if gateway_match else None,
        _strip_interface_alias(interface_match.group(1)) if interface_match else None,
    )


def _parse_route_get(lines: list[str]) -> tuple[str | None, str | None]:
    route_line = _first_non_empty(lines)
    if route_line is None:
        return None, None
    interface_match = re.search(r"\bdev\s+(\S+)\b", route_line)
    source_match = re.search(r"\bsrc\s+([0-9.]+)\b", route_line)
    return (
        _strip_interface_alias(interface_match.group(1)) if interface_match else None,
        source_match.group(1) if source_match else None,
    )


def _suggest_inventory_hostname(hostname: str | None, *, fallback: str) -> str:
    if hostname is None:
        return fallback
    slug = _slugify(hostname)
    if not slug:
        return fallback
    return slug if slug.startswith("cascadya-") else f"cascadya-{slug}"


def _mock_discovery_result(
    *,
    target_ip: str,
    teltonika_router_ip: str | None,
    ssh_username: str,
    ssh_port: int,
    downstream_probe_ip: str | None,
) -> dict[str, Any]:
    suggested = _suggest_device_identity(target_ip)
    return {
        "probe_mode": "mock",
        "status": "warning",
        "warnings": ["Scan simule: aucune sonde reseau reelle n'a ete executee."],
        "ssh_username": ssh_username,
        "ssh_port": ssh_port,
        "target_ip": target_ip,
        "teltonika_router_ip": teltonika_router_ip,
        "management_ip": target_ip,
        "mac_address": _mac_from_ip(target_ip),
        "hostname": suggested["hostname"],
        "inventory_hostname": suggested["inventory_hostname"],
        "vendor": suggested["vendor"],
        "model": suggested["model"],
        "serial_number": None,
        "management_interface": suggested["management_interface"],
        "uplink_interface": suggested["uplink_interface"],
        "gateway_ip": teltonika_router_ip or _default_gateway_for_ip(target_ip),
        "wireguard_address": suggested["wireguard_address"],
        "downstream_probe_ip": downstream_probe_ip,
        "downstream_ping": None,
        "discovered_ips": [],
        "provisioning_vars": _default_provisioning_vars(
            management_interface=suggested["management_interface"],
            uplink_interface=suggested["uplink_interface"],
            ansible_user=ssh_username,
            ansible_port=ssh_port,
            modbus_host=downstream_probe_ip,
        ),
        "summary": {
            "probe_mode": "mock",
            "tcp_22_reachable": None,
            "ssh_authenticated": False,
            "ssh_username": ssh_username,
            "ssh_port": ssh_port,
            "entrypoint_ip": target_ip,
            "teltonika_router_ip": teltonika_router_ip,
            "downstream_probe_ip": downstream_probe_ip,
            "warnings": ["Scan simule: aucune sonde reseau reelle n'a ete executee."],
        },
    }


def _tcp_discovery_result(
    *,
    target_ip: str,
    teltonika_router_ip: str | None,
    ssh_username: str,
    ssh_port: int,
    downstream_probe_ip: str | None,
    tcp_probe: dict[str, Any],
    warning: str | None = None,
) -> dict[str, Any]:
    suggested = _suggest_device_identity(target_ip)
    warnings = [warning] if warning else []
    return {
        "probe_mode": "tcp",
        "status": "warning",
        "warnings": warnings,
        "ssh_username": ssh_username,
        "ssh_port": ssh_port,
        "target_ip": target_ip,
        "teltonika_router_ip": teltonika_router_ip,
        "management_ip": target_ip,
        "mac_address": None,
        "hostname": suggested["hostname"],
        "inventory_hostname": suggested["inventory_hostname"],
        "vendor": suggested["vendor"],
        "model": suggested["model"],
        "serial_number": None,
        "management_interface": suggested["management_interface"],
        "uplink_interface": suggested["uplink_interface"],
        "gateway_ip": teltonika_router_ip or _default_gateway_for_ip(target_ip),
        "wireguard_address": suggested["wireguard_address"],
        "downstream_probe_ip": downstream_probe_ip,
        "downstream_ping": None,
        "discovered_ips": [],
        "provisioning_vars": _default_provisioning_vars(
            management_interface=suggested["management_interface"],
            uplink_interface=suggested["uplink_interface"],
            ansible_user=ssh_username,
            ansible_port=ssh_port,
            modbus_host=downstream_probe_ip,
        ),
        "summary": {
            "probe_mode": "tcp",
            "tcp_22_reachable": bool(tcp_probe.get("reachable")),
            "tcp_error": tcp_probe.get("error"),
            "ssh_authenticated": False,
            "ssh_username": ssh_username,
            "ssh_port": ssh_port,
            "entrypoint_ip": target_ip,
            "teltonika_router_ip": teltonika_router_ip,
            "downstream_probe_ip": downstream_probe_ip,
            "warnings": warnings,
        },
    }


def _run_remote_ssh_discovery(
    *,
    settings: Settings,
    target_ip: str,
    ssh_username: str,
    ssh_port: int,
    downstream_probe_ip: str | None,
) -> dict[str, Any]:
    ssh_binary = shutil.which("ssh")
    if ssh_binary is None:
        raise FleetValidationError(
            "Le binaire 'ssh' est introuvable sur la VM du control panel. Impossible de lancer une decouverte reelle."
        )

    command = [
        ssh_binary,
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={settings.discovery_connect_timeout_seconds}",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-p",
        str(ssh_port),
    ]
    if settings.discovery_ssh_key_path:
        key_path = Path(settings.discovery_ssh_key_path).expanduser()
        if not key_path.exists():
            raise FleetValidationError(
                f"La cle SSH configuree pour la decouverte est introuvable: {key_path.as_posix()}."
            )
        command.extend(["-i", str(key_path)])
    command.extend([f"{ssh_username}@{target_ip}", "sh", "-s", "--", downstream_probe_ip or ""])

    try:
        result = subprocess.run(
            command,
            input=_build_remote_discovery_script(),
            capture_output=True,
            text=True,
            timeout=settings.discovery_command_timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise FleetValidationError(
            f"La decouverte SSH vers {ssh_username}@{target_ip}:{ssh_port} a expire apres "
            f"{settings.discovery_command_timeout_seconds} secondes."
        ) from exc
    except OSError as exc:
        raise FleetValidationError(
            f"Impossible d'executer la commande ssh pour scanner {target_ip}: {_format_socket_error(exc)}."
        ) from exc

    if result.returncode != 0:
        error_tail = _clean_optional(result.stderr) or _clean_optional(result.stdout) or "Aucun detail retourne."
        raise FleetValidationError(
            f"Connexion SSH impossible vers {ssh_username}@{target_ip}:{ssh_port}. Detail: {error_tail}"
        )

    return _parse_remote_ssh_discovery(
        target_ip=target_ip,
        teltonika_router_ip=None,
        ssh_username=ssh_username,
        ssh_port=ssh_port,
        downstream_probe_ip=downstream_probe_ip,
        output=result.stdout,
    )


def _parse_remote_ssh_discovery(
    *,
    target_ip: str,
    teltonika_router_ip: str | None,
    ssh_username: str,
    ssh_port: int,
    downstream_probe_ip: str | None,
    output: str,
) -> dict[str, Any]:
    sections = _split_remote_sections(output)
    suggested = _suggest_device_identity(target_ip)
    discovered_ips = _parse_remote_ipv4(sections.get("IPV4", []))
    macs = _parse_remote_macs(sections.get("MACS", []))
    gateway_ip, default_route_interface = _parse_default_route(sections.get("ROUTE_DEFAULT", []))
    downstream_route_interface, _downstream_source_ip = _parse_route_get(sections.get("ROUTE_DOWNSTREAM", []))
    hostname = _first_non_empty(sections.get("HOSTNAME", [])) or suggested["hostname"]
    vendor = _first_non_empty(sections.get("SYS_VENDOR", [])) or suggested["vendor"]
    model = _first_non_empty(sections.get("PRODUCT_NAME", [])) or suggested["model"]
    serial_number = _first_non_empty(sections.get("PRODUCT_SERIAL", []))
    downstream_ping_state = _first_non_empty(sections.get("DOWNSTREAM_PING", []))
    downstream_ping = None
    if downstream_ping_state is not None:
        downstream_ping = downstream_ping_state.lower() == "reachable"

    warnings: list[str] = []
    management_interface = next(
        (entry["interface"] for entry in discovered_ips if entry["ip"] == target_ip),
        None,
    )
    if management_interface is None:
        warnings.append(
            "Le scan SSH n'a pas retrouve l'IP cible sur une interface locale; l'interface management a ete deduite."
        )
        management_interface = default_route_interface or suggested["management_interface"]

    uplink_interface = downstream_route_interface or default_route_interface
    if uplink_interface is None:
        warnings.append("Impossible de deduire l'interface uplink; une valeur par defaut a ete appliquee.")
        uplink_interface = suggested["uplink_interface"]

    if gateway_ip is None:
        gateway_ip = teltonika_router_ip or _default_gateway_for_ip(target_ip)

    mac_address = macs.get(management_interface or "")
    if mac_address is None and macs:
        mac_address = next(iter(macs.values()))
        warnings.append("La MAC management n'a pas pu etre associee de facon certaine; premiere MAC disponible retenue.")
    if mac_address is None:
        warnings.append("Aucune adresse MAC n'a ete remontee par la sonde SSH.")

    inventory_hostname = _suggest_inventory_hostname(hostname, fallback=suggested["inventory_hostname"])
    management_address = next(
        (entry.get("cidr") for entry in discovered_ips if entry.get("interface") == management_interface),
        None,
    )
    uplink_address = next(
        (entry.get("cidr") for entry in discovered_ips if entry.get("interface") == uplink_interface),
        None,
    )
    provisioning_vars = _default_provisioning_vars(
        management_interface=management_interface,
        uplink_interface=uplink_interface,
        ansible_user=ssh_username,
        ansible_port=ssh_port,
        modbus_host=downstream_probe_ip,
    )
    if isinstance(management_address, str) and management_address:
        provisioning_vars["network_persist_management_address"] = management_address
    if isinstance(uplink_address, str) and uplink_address:
        provisioning_vars["network_persist_uplink_address"] = uplink_address
    if gateway_ip:
        provisioning_vars["network_persist_uplink_gateway_ip"] = gateway_ip

    return {
        "probe_mode": "ssh",
        "status": "online",
        "warnings": warnings,
        "ssh_username": ssh_username,
        "ssh_port": ssh_port,
        "target_ip": target_ip,
        "teltonika_router_ip": teltonika_router_ip,
        "management_ip": target_ip,
        "mac_address": mac_address,
        "hostname": hostname,
        "inventory_hostname": inventory_hostname,
        "vendor": vendor,
        "model": model,
        "serial_number": serial_number,
        "management_interface": management_interface,
        "uplink_interface": uplink_interface,
        "gateway_ip": gateway_ip,
        "wireguard_address": suggested["wireguard_address"],
        "downstream_probe_ip": downstream_probe_ip,
        "downstream_ping": downstream_ping,
        "discovered_ips": discovered_ips,
        "provisioning_vars": provisioning_vars,
        "summary": {
            "probe_mode": "ssh",
            "tcp_22_reachable": True,
            "ssh_authenticated": True,
            "ssh_username": ssh_username,
            "ssh_port": ssh_port,
            "entrypoint_ip": target_ip,
            "teltonika_router_ip": teltonika_router_ip,
            "downstream_probe_ip": downstream_probe_ip,
            "downstream_ping": downstream_ping,
            "management_interface": management_interface,
            "uplink_interface": uplink_interface,
            "gateway_ip": gateway_ip,
            "discovered_ips": discovered_ips,
            "warnings": warnings,
        },
    }


def _probe_inventory_target(
    *,
    settings: Settings,
    target_ip: str,
    teltonika_router_ip: str | None,
    ssh_username: str | None,
    ssh_port: int | None,
    downstream_probe_ip: str | None,
) -> dict[str, Any]:
    effective_mode = _normalize_discovery_mode(settings.discovery_mode)
    effective_username = _clean_optional(ssh_username) or settings.discovery_ssh_username or "cascadya"
    effective_port = _normalize_port(
        ssh_port,
        field_name="ssh_port",
        default=settings.discovery_ssh_port,
    )
    normalized_downstream_ip = _normalize_ip(
        downstream_probe_ip or settings.discovery_downstream_probe_ip,
        field_name="downstream_probe_ip",
    )

    if effective_mode == "mock":
        return _mock_discovery_result(
            target_ip=target_ip,
            teltonika_router_ip=teltonika_router_ip,
            ssh_username=effective_username,
            ssh_port=effective_port,
            downstream_probe_ip=normalized_downstream_ip,
        )

    tcp_probe = _probe_tcp_port(
        target_ip,
        port=effective_port,
        timeout_seconds=settings.discovery_connect_timeout_seconds,
    )
    if not tcp_probe["reachable"]:
        raise FleetValidationError(
            f"Le port SSH {effective_port} est injoignable sur {target_ip}: {tcp_probe['error']}."
        )

    if effective_mode == "tcp":
        return _tcp_discovery_result(
            target_ip=target_ip,
            teltonika_router_ip=teltonika_router_ip,
            ssh_username=effective_username,
            ssh_port=effective_port,
            downstream_probe_ip=normalized_downstream_ip,
            tcp_probe=tcp_probe,
        )

    try:
        discovery = _run_remote_ssh_discovery(
            settings=settings,
            target_ip=target_ip,
            ssh_username=effective_username,
            ssh_port=effective_port,
            downstream_probe_ip=normalized_downstream_ip,
        )
    except FleetValidationError as exc:
        if effective_mode == "ssh":
            raise
        discovery = _tcp_discovery_result(
            target_ip=target_ip,
            teltonika_router_ip=teltonika_router_ip,
            ssh_username=effective_username,
            ssh_port=effective_port,
            downstream_probe_ip=normalized_downstream_ip,
            tcp_probe=tcp_probe,
            warning=str(exc),
        )
    else:
        discovery["teltonika_router_ip"] = teltonika_router_ip
        discovery["summary"]["teltonika_router_ip"] = teltonika_router_ip

    return discovery


def _site_query() -> Any:
    return select(Site).options(
        selectinload(Site.assets),
        selectinload(Site.scans),
        selectinload(Site.provisioning_jobs),
    )


def _asset_query() -> Any:
    return select(InventoryAsset).options(
        selectinload(InventoryAsset.site),
        selectinload(InventoryAsset.discovered_by_scan),
        selectinload(InventoryAsset.provisioning_jobs),
    )


def _scan_query() -> Any:
    return select(InventoryScan).options(
        selectinload(InventoryScan.site),
        selectinload(InventoryScan.discovered_assets).selectinload(InventoryAsset.site),
    )


def _job_query() -> Any:
    return select(ProvisioningJob).options(
        selectinload(ProvisioningJob.site),
        selectinload(ProvisioningJob.asset),
    )


def list_sites(session: Session) -> list[Site]:
    return session.scalars(_site_query().order_by(Site.name, Site.code)).all()


def list_inventory_assets(
    session: Session,
    *,
    site_id: int | None = None,
    registration_status: str | None = None,
) -> list[InventoryAsset]:
    statement = _asset_query().order_by(InventoryAsset.created_at.desc(), InventoryAsset.id.desc())
    if site_id is not None:
        statement = statement.where(InventoryAsset.site_id == site_id)
    if registration_status:
        statement = statement.where(InventoryAsset.registration_status == registration_status)
    return session.scalars(statement).all()


def list_inventory_scans(session: Session, *, site_id: int | None = None) -> list[InventoryScan]:
    statement = _scan_query().order_by(InventoryScan.created_at.desc(), InventoryScan.id.desc())
    if site_id is not None:
        statement = statement.where(InventoryScan.site_id == site_id)
    return session.scalars(statement).all()


def list_provisioning_jobs(session: Session, *, site_id: int | None = None) -> list[ProvisioningJob]:
    statement = _job_query().order_by(ProvisioningJob.created_at.desc(), ProvisioningJob.id.desc())
    if site_id is not None:
        statement = statement.where(ProvisioningJob.site_id == site_id)
    return session.scalars(statement).all()


def get_site(session: Session, site_id: int) -> Site:
    site = session.scalar(_site_query().where(Site.id == site_id))
    if site is None:
        raise FleetNotFoundError(f"Unknown site id {site_id}.")
    return site


def get_inventory_asset(session: Session, asset_id: int) -> InventoryAsset:
    asset = session.scalar(_asset_query().where(InventoryAsset.id == asset_id))
    if asset is None:
        raise FleetNotFoundError(f"Unknown inventory asset id {asset_id}.")
    return asset


def get_inventory_scan(session: Session, scan_id: int) -> InventoryScan:
    scan = session.scalar(_scan_query().where(InventoryScan.id == scan_id))
    if scan is None:
        raise FleetNotFoundError(f"Unknown inventory scan id {scan_id}.")
    return scan


def get_provisioning_job(session: Session, job_id: int) -> ProvisioningJob:
    job = session.scalar(_job_query().where(ProvisioningJob.id == job_id))
    if job is None:
        raise FleetNotFoundError(f"Unknown provisioning job id {job_id}.")
    return job


def delete_inventory_asset(session: Session, asset_id: int) -> dict[str, Any]:
    asset = get_inventory_asset(session, asset_id)
    active_jobs = [job for job in asset.provisioning_jobs if job.status in {"prepared", "running"}]
    if active_jobs:
        active_job_ids = ", ".join(str(job.id) for job in active_jobs)
        raise FleetValidationError(
            "Impossible de supprimer cet asset tant qu'un job de provisioning actif lui est rattache "
            f"(job(s): {active_job_ids})."
        )

    asset_label = asset.inventory_hostname or asset.hostname or f"asset-{asset.id}"
    detached_jobs = 0
    deleted_job_ids: list[int] = []
    deleted_site_id = asset.site_id
    deleted_scan_id = asset.discovered_by_scan_id
    deleted_registration_status = asset.registration_status

    for job in asset.provisioning_jobs:
        detached_jobs += 1
        deleted_job_ids.append(job.id)
        job.asset = None
        context_json = job.context_json if isinstance(job.context_json, dict) else {}
        job.context_json = {
            **context_json,
            "deleted_asset": {
                "id": asset.id,
                "inventory_hostname": asset.inventory_hostname,
                "hostname": asset.hostname,
                "management_ip": asset.management_ip,
            },
        }
        logs = list(job.logs_json or [])
        logs.append(f"{_utcnow().isoformat()} INFO inventory asset {asset_label} deleted and detached from this job")
        job.logs_json = logs

    session.delete(asset)
    session.commit()
    return {
        "status": "ok",
        "deleted_asset_id": asset_id,
        "deleted_asset_label": asset_label,
        "deleted_registration_status": deleted_registration_status,
        "site_id": deleted_site_id,
        "discovered_by_scan_id": deleted_scan_id,
        "detached_job_count": detached_jobs,
        "detached_job_ids": deleted_job_ids,
    }


def _refresh_asset_registration_state(asset: InventoryAsset | None) -> None:
    if asset is None:
        return

    jobs = list(asset.provisioning_jobs or [])
    active_jobs = [job for job in jobs if job.status in {"prepared", "running"}]
    succeeded_jobs = [job for job in jobs if job.status == "succeeded"]

    if active_jobs:
        asset.registration_status = "provisioning"
        return
    if succeeded_jobs:
        asset.registration_status = "active"
        if asset.status in {"unknown", "warning", "offline"}:
            asset.status = "online"
        return
    if asset.site_id is not None:
        asset.registration_status = "registered"
        if asset.status == "unknown":
            asset.status = "warning"
        return

    asset.registration_status = "discovered"
    if asset.status == "online":
        asset.status = "warning"


def _workflow_artifact_log_lines(context: dict[str, Any]) -> list[str]:
    artifacts = context.get("artifacts")
    if not isinstance(artifacts, dict):
        return []

    lines: list[str] = []
    for bundle_name in ("remote_unlock", "remote_unlock_broker", "wazuh_agent", "ipc_alloy", "edge_agent"):
        bundle = artifacts.get(bundle_name)
        if not isinstance(bundle, dict):
            continue
        inventory_abspath = bundle.get("inventory_abspath")
        vars_abspath = bundle.get("vars_abspath")
        if isinstance(inventory_abspath, str) and inventory_abspath:
            lines.append(f"Generated {bundle_name} inventory: {inventory_abspath}")
        if isinstance(vars_abspath, str) and vars_abspath:
            lines.append(f"Generated {bundle_name} vars: {vars_abspath}")
    return lines


def _normalize_generated_filename(inventory_hostname: str, suffix: str, extension: str) -> str:
    normalized = _slugify(inventory_hostname) or "ipc"
    return f"{normalized}.{suffix}.{extension}"


def _build_edge_agent_inventory_preview(asset: InventoryAsset, *, inventory_group: str) -> str:
    if not asset.inventory_hostname or not asset.management_ip:
        raise FleetValidationError("L'asset doit avoir un inventory_hostname et une management_ip avant de preparer un job.")
    provisioning_vars = asset.provisioning_vars if isinstance(asset.provisioning_vars, dict) else {}
    line = (
        f"{asset.inventory_hostname} ansible_host={asset.management_ip}"
        f" ansible_user={provisioning_vars.get('ansible_user', 'cascadya')}"
        f" edge_agent_modbus_host={provisioning_vars.get('edge_agent_modbus_host', DEFAULT_EDGE_AGENT_MODBUS_HOST)}"
        f" edge_agent_nats_url={_normalize_edge_agent_nats_url(provisioning_vars.get('edge_agent_nats_url'))}"
        " edge_agent_nats_telemetry_subject=cascadya.telemetry.live"
        " edge_agent_nats_command_subject=cascadya.routing.command"
        " edge_agent_nats_ping_subject=cascadya.routing.ping"
    )
    ansible_port = provisioning_vars.get("ansible_port")
    if ansible_port:
        line += f" ansible_port={ansible_port}"
    return "\n".join([f"[{inventory_group}]", line])


def _build_wazuh_agent_inventory_preview(asset: InventoryAsset, *, inventory_group: str) -> str:
    if not asset.inventory_hostname or not asset.management_ip:
        raise FleetValidationError("L'asset doit avoir un inventory_hostname et une management_ip avant de preparer un job.")
    provisioning_vars = asset.provisioning_vars if isinstance(asset.provisioning_vars, dict) else {}
    line = (
        f"{asset.inventory_hostname} ansible_host={asset.management_ip}"
        f" ansible_user={provisioning_vars.get('ansible_user', 'cascadya')}"
        " ansible_ssh_transfer_method=piped"
    )
    ansible_port = provisioning_vars.get("ansible_port")
    if ansible_port:
        line += f" ansible_port={ansible_port}"
    return "\n".join([f"[{inventory_group}]", line])


def _build_ipc_alloy_inventory_preview(asset: InventoryAsset, *, inventory_group: str) -> str:
    if not asset.inventory_hostname or not asset.management_ip:
        raise FleetValidationError("L'asset doit avoir un inventory_hostname et une management_ip avant de preparer un job.")
    provisioning_vars = asset.provisioning_vars if isinstance(asset.provisioning_vars, dict) else {}
    line = (
        f"{asset.inventory_hostname} ansible_host={asset.management_ip}"
        f" ansible_user={provisioning_vars.get('ansible_user', 'cascadya')}"
        " ansible_ssh_transfer_method=piped"
    )
    ansible_port = provisioning_vars.get("ansible_port")
    if ansible_port:
        line += f" ansible_port={ansible_port}"
    return "\n".join([f"[{inventory_group}]", line])


def _build_remote_unlock_inventory_preview(asset: InventoryAsset, *, inventory_group: str) -> str:
    if not asset.inventory_hostname or not asset.management_ip:
        raise FleetValidationError("L'asset doit avoir un inventory_hostname et une management_ip avant de preparer un job.")
    provisioning_vars = asset.provisioning_vars if isinstance(asset.provisioning_vars, dict) else {}
    remote_unlock_device_id = provisioning_vars.get("remote_unlock_device_id", asset.inventory_hostname)
    allowed_ips_value = provisioning_vars.get(
        "network_wireguard_allowed_ips",
        json.dumps(DEFAULT_REMOTE_UNLOCK_ALLOWED_IPS, separators=(",", ":")),
    )
    nameservers_value = provisioning_vars.get(
        "network_bootstrap_nameservers",
        json.dumps(DEFAULT_REMOTE_UNLOCK_BOOTSTRAP_NAMESERVERS, separators=(",", ":")),
    )
    line = (
        f"{asset.inventory_hostname} ansible_host={asset.management_ip}"
        f" ansible_user={provisioning_vars.get('ansible_user', 'cascadya')}"
        " ansible_ssh_transfer_method=piped"
        f" remote_unlock_device_id={remote_unlock_device_id}"
        f" remote_unlock_transport_mode={provisioning_vars.get('remote_unlock_transport_mode', 'wireguard')}"
        " remote_unlock_manage_wireguard=true"
        f" remote_unlock_broker_url={provisioning_vars.get('remote_unlock_broker_url', DEFAULT_REMOTE_UNLOCK_BROKER_URL)}"
        f" remote_unlock_management_interface={asset.management_interface or 'enp3s0'}"
        f" remote_unlock_uplink_interface={asset.uplink_interface or 'enp2s0'}"
        f" remote_unlock_gateway_ip={asset.gateway_ip or ''}"
        f" remote_unlock_wg_interface={provisioning_vars.get('remote_unlock_wg_interface', DEFAULT_REMOTE_UNLOCK_WG_INTERFACE)}"
        f" network_uplink_interface={asset.uplink_interface or 'enp2s0'}"
        f" network_uplink_gateway_ip={asset.gateway_ip or ''}"
        f" network_wireguard_address={asset.wireguard_address or ''}"
        f" network_wireguard_private_key={provisioning_vars.get('network_wireguard_private_key', DEFAULT_REMOTE_UNLOCK_PRIVATE_KEY)}"
        f" network_wireguard_peer_public_key={provisioning_vars.get('network_wireguard_peer_public_key', DEFAULT_REMOTE_UNLOCK_PEER_PUBLIC_KEY)}"
        f" network_wireguard_endpoint={provisioning_vars.get('network_wireguard_endpoint', DEFAULT_REMOTE_UNLOCK_WG_ENDPOINT)}"
        f" network_wireguard_allowed_ips={allowed_ips_value}"
        f" network_bootstrap_nameservers={nameservers_value}"
    )
    ansible_port = provisioning_vars.get("ansible_port")
    if ansible_port:
        line += f" ansible_port={ansible_port}"
    return "\n".join([f"[{inventory_group}]", line])


def _build_remote_unlock_broker_inventory_preview(asset: InventoryAsset, *, settings: Settings) -> str:
    broker_host = _clean_optional(settings.provisioning_remote_unlock_broker_ansible_host) or "REPLACE_REMOTE_UNLOCK_BROKER_HOST"
    inventory_hostname = (
        _clean_optional(settings.provisioning_remote_unlock_broker_inventory_hostname)
        or "remote-unlock-broker"
    )
    ansible_user = _clean_optional(settings.provisioning_remote_unlock_broker_ansible_user) or "ubuntu"
    line = (
        f"{inventory_hostname} ansible_host={broker_host}"
        f" ansible_user={ansible_user}"
        " ansible_ssh_transfer_method=piped"
    )
    if settings.provisioning_remote_unlock_broker_ansible_port != 22:
        line += f" ansible_port={settings.provisioning_remote_unlock_broker_ansible_port}"
    return "\n".join(["[remote_unlock_broker]", line])


def _build_edge_agent_vars_preview(asset: InventoryAsset, *, settings: Settings) -> dict[str, Any]:
    provisioning_vars = asset.provisioning_vars if isinstance(asset.provisioning_vars, dict) else {}
    edge_agent_inventory_hostname = asset.inventory_hostname or asset.hostname or "cascadya-ipc"
    edge_agent_nats_url = _normalize_edge_agent_nats_url(provisioning_vars.get("edge_agent_nats_url"))
    edge_agent_probe_nats_url = _clean_optional(str(provisioning_vars.get("edge_agent_probe_nats_url", "") or ""))
    edge_agent_probe_broker_url = _clean_optional(
        str(
            provisioning_vars.get(
                "edge_agent_probe_broker_url",
                settings.provisioning_remote_unlock_broker_probe_url_default or "",
            )
            or ""
        )
    )
    edge_agent_nats_monitoring_url = _clean_optional(
        str(provisioning_vars.get("edge_agent_nats_monitoring_url", "") or "")
    ) or derive_nats_monitoring_url(edge_agent_nats_url)
    edge_agent_probe_monitoring_url = _clean_optional(
        str(provisioning_vars.get("edge_agent_probe_monitoring_url", "") or "")
    ) or (
        derive_nats_monitoring_url(edge_agent_probe_nats_url)
        if edge_agent_probe_nats_url is not None
        else edge_agent_nats_monitoring_url
    )
    return {
        "edge_agent_modbus_host": provisioning_vars.get("edge_agent_modbus_host", DEFAULT_EDGE_AGENT_MODBUS_HOST),
        "edge_agent_nats_url": edge_agent_nats_url,
        "edge_agent_nats_monitoring_url": edge_agent_nats_monitoring_url,
        "edge_agent_probe_nats_url": edge_agent_probe_nats_url,
        "edge_agent_probe_broker_url": edge_agent_probe_broker_url,
        "edge_agent_probe_monitoring_url": edge_agent_probe_monitoring_url,
        "edge_agent_nats_telemetry_subject": "cascadya.telemetry.live",
        "edge_agent_nats_command_subject": "cascadya.routing.command",
        "edge_agent_nats_ping_subject": "cascadya.routing.ping",
        "edge_agent_vault_addr": provisioning_vars.get(
            "edge_agent_vault_addr",
            settings.provisioning_remote_unlock_broker_vault_addr or "",
        ),
        "edge_agent_vault_pki_mount": provisioning_vars.get(
            "edge_agent_vault_pki_mount",
            DEFAULT_EDGE_AGENT_VAULT_PKI_MOUNT,
        ),
        "edge_agent_vault_role": provisioning_vars.get(
            "edge_agent_vault_role",
            DEFAULT_EDGE_AGENT_VAULT_ROLE,
        ),
        "edge_agent_cert_common_name": provisioning_vars.get(
            "edge_agent_cert_common_name",
            f"{edge_agent_inventory_hostname}.cascadya.local",
        ),
        "edge_agent_cert_ttl": provisioning_vars.get(
            "edge_agent_cert_ttl",
            DEFAULT_EDGE_AGENT_CERT_TTL,
        ),
        "edge_agent_nats_server_ca_cert_path": provisioning_vars.get(
            "edge_agent_nats_server_ca_cert_path",
            settings.provisioning_nats_server_ca_cert_path or "",
        ),
    }


def _build_wazuh_agent_vars_preview(asset: InventoryAsset, *, settings: Settings) -> dict[str, Any]:
    provisioning_vars = asset.provisioning_vars if isinstance(asset.provisioning_vars, dict) else {}
    inventory_hostname = asset.inventory_hostname or asset.hostname or "cascadya-ipc"
    manager_address = _clean_optional(
        str(
            provisioning_vars.get(
                "wazuh_agent_manager_address",
                settings.provisioning_wazuh_manager_address_default or "",
            )
            or ""
        )
    )
    registration_server = _clean_optional(
        str(
            provisioning_vars.get(
                "wazuh_agent_registration_server",
                settings.provisioning_wazuh_registration_server_default or "",
            )
            or ""
        )
    ) or manager_address
    manager_port = _normalize_port(
        _coerce_optional_int(
            provisioning_vars.get("wazuh_agent_manager_port"),
            field_name="wazuh_agent_manager_port",
        ),
        field_name="wazuh_agent_manager_port",
        default=settings.provisioning_wazuh_manager_port_default,
    )
    registration_port = _normalize_port(
        _coerce_optional_int(
            provisioning_vars.get("wazuh_agent_registration_port"),
            field_name="wazuh_agent_registration_port",
        ),
        field_name="wazuh_agent_registration_port",
        default=settings.provisioning_wazuh_registration_port_default,
    )
    protocol = _clean_optional(str(provisioning_vars.get("wazuh_agent_protocol") or "")) or DEFAULT_WAZUH_AGENT_PROTOCOL
    return {
        "wazuh_agent_manager_address": manager_address or "",
        "wazuh_agent_manager_port": manager_port,
        "wazuh_agent_protocol": protocol,
        "wazuh_agent_registration_enabled": True,
        "wazuh_agent_registration_server": registration_server or "",
        "wazuh_agent_registration_port": registration_port,
        "wazuh_agent_name": provisioning_vars.get("wazuh_agent_name", inventory_hostname),
        "wazuh_agent_group": provisioning_vars.get(
            "wazuh_agent_group",
            settings.provisioning_wazuh_agent_group_default or "",
        ),
        "wazuh_agent_hold_package": _coerce_bool(
            provisioning_vars.get("wazuh_agent_hold_package"),
            default=True,
        ),
        "wazuh_agent_delay_after_enrollment": _coerce_optional_int(
            provisioning_vars.get("wazuh_agent_delay_after_enrollment"),
            field_name="wazuh_agent_delay_after_enrollment",
        )
        or 20,
        "wazuh_agent_registration_ca_source_path": provisioning_vars.get(
            "wazuh_agent_registration_ca_source_path",
            settings.provisioning_wazuh_registration_ca_cert_path or "",
        ),
        "wazuh_agent_registration_ca_path": provisioning_vars.get(
            "wazuh_agent_registration_ca_path",
            "/var/ossec/etc/rootCA.pem",
        ),
    }


def _build_ipc_alloy_vars_preview(asset: InventoryAsset, *, settings: Settings) -> dict[str, Any]:
    provisioning_vars = _ensure_asset_runtime_provisioning_vars(asset, settings=settings)
    inventory_hostname = asset.inventory_hostname or asset.hostname or "cascadya-ipc"
    remote_write_url = _clean_optional(
        str(
            provisioning_vars.get(
                "ipc_alloy_mimir_remote_write_url",
                settings.provisioning_ipc_alloy_mimir_remote_write_url_default
                or DEFAULT_IPC_ALLOY_MIMIR_REMOTE_WRITE_URL,
            )
            or ""
        )
    )
    remote_write_host, remote_write_port = _extract_endpoint_host_and_port(remote_write_url)
    tenant, retention_profile = _resolve_ipc_alloy_contract(provisioning_vars, settings=settings)
    site_code = _clean_optional(
        str(
            provisioning_vars.get(
                "ipc_alloy_site_code",
                asset.site.code if asset.site is not None else "unassigned",
            )
            or ""
        )
    ) or "unassigned"

    node_exporter_port = _normalize_port(
        _coerce_optional_int(
            provisioning_vars.get("ipc_alloy_node_exporter_port"),
            field_name="ipc_alloy_node_exporter_port",
        ),
        field_name="ipc_alloy_node_exporter_port",
        default=DEFAULT_IPC_ALLOY_NODE_EXPORTER_PORT,
    )
    metrics_source = _clean_optional(
        str(
            provisioning_vars.get(
                "ipc_metrics_source",
                provisioning_vars.get("ipc_alloy_labels_source") or "",
            )
            or ""
        )
    ) or "ipc"
    metrics_role = _clean_optional(
        str(
            provisioning_vars.get(
                "ipc_metrics_role",
                provisioning_vars.get("ipc_alloy_labels_role") or "",
            )
            or ""
        )
    ) or "ipc"
    metrics_node = _clean_optional(
        str(
            provisioning_vars.get(
                "ipc_metrics_node",
                provisioning_vars.get("ipc_alloy_labels_node") or inventory_hostname,
            )
            or ""
        )
    ) or inventory_hostname
    metrics_instance = _clean_optional(
        str(provisioning_vars.get("ipc_metrics_instance") or "")
    ) or f"{metrics_node}:{node_exporter_port}"

    return {
        "ipc_alloy_manage_repo": _coerce_bool(
            provisioning_vars.get("ipc_alloy_manage_repo"),
            default=True,
        ),
        "ipc_alloy_mimir_remote_write_url": remote_write_url or "",
        "ipc_alloy_mimir_remote_write_host": remote_write_host or "",
        "ipc_alloy_mimir_remote_write_port": _normalize_port(
            _coerce_optional_int(
                provisioning_vars.get("ipc_alloy_mimir_remote_write_port") or remote_write_port,
                field_name="ipc_alloy_mimir_remote_write_port",
            ),
            field_name="ipc_alloy_mimir_remote_write_port",
            default=9009,
        ),
        "ipc_alloy_scrape_interval": _clean_optional(
            str(
                provisioning_vars.get(
                    "ipc_alloy_scrape_interval",
                    settings.provisioning_ipc_alloy_scrape_interval_default
                    or DEFAULT_IPC_ALLOY_SCRAPE_INTERVAL,
                )
                or ""
            )
        )
        or DEFAULT_IPC_ALLOY_SCRAPE_INTERVAL,
        "ipc_alloy_scrape_timeout": _clean_optional(
            str(
                provisioning_vars.get(
                    "ipc_alloy_scrape_timeout",
                    settings.provisioning_ipc_alloy_scrape_timeout_default
                    or DEFAULT_IPC_ALLOY_SCRAPE_TIMEOUT,
                )
                or ""
            )
        )
        or DEFAULT_IPC_ALLOY_SCRAPE_TIMEOUT,
        "ipc_alloy_mimir_tenant": tenant,
        "ipc_alloy_mimir_tenant_label": tenant,
        "ipc_alloy_retention_profile": retention_profile,
        "ipc_alloy_send_tenant_header": _coerce_bool(
            provisioning_vars.get("ipc_alloy_send_tenant_header"),
            default=True,
        ),
        "ipc_alloy_mimir_basic_auth_username": _clean_optional(
            str(
                provisioning_vars.get(
                    "ipc_alloy_mimir_basic_auth_username",
                    settings.provisioning_ipc_alloy_mimir_username or "",
                )
                or ""
            )
        )
        or "",
        "ipc_alloy_mimir_verify_tls": _coerce_bool(
            provisioning_vars.get("ipc_alloy_mimir_verify_tls"),
            default=settings.provisioning_ipc_alloy_mimir_verify_tls,
        ),
        "ipc_alloy_mimir_ca_source_path": provisioning_vars.get(
            "ipc_alloy_mimir_ca_source_path",
            settings.provisioning_ipc_alloy_mimir_ca_cert_path or "",
        ),
        "ipc_alloy_mimir_ca_dest_path": provisioning_vars.get(
            "ipc_alloy_mimir_ca_dest_path",
            "/etc/alloy/certs/mimir-ca.crt",
        ),
        "ipc_alloy_node_exporter_port": node_exporter_port,
        "ipc_alloy_node_exporter_target": _clean_optional(
            str(provisioning_vars.get("ipc_alloy_node_exporter_target") or "")
        )
        or f"127.0.0.1:{node_exporter_port}",
        "ipc_alloy_node_exporter_job": _clean_optional(
            str(provisioning_vars.get("ipc_alloy_node_exporter_job") or "")
        )
        or "node-exporter",
        "ipc_alloy_http_listen_address": _clean_optional(
            str(provisioning_vars.get("ipc_alloy_http_listen_address") or "")
        )
        or DEFAULT_IPC_ALLOY_HTTP_LISTEN_ADDRESS,
        "ipc_alloy_labels_source": metrics_source,
        "ipc_alloy_labels_role": metrics_role,
        "ipc_alloy_labels_node": metrics_node,
        "ipc_alloy_labels_site": site_code,
        "ipc_metrics_source": metrics_source,
        "ipc_metrics_role": metrics_role,
        "ipc_metrics_site": site_code,
        "ipc_metrics_node": metrics_node,
        "ipc_metrics_instance": metrics_instance,
        "ipc_metrics_retention_profile": retention_profile,
        "ipc_metrics_tenant_label": tenant,
    }


def _build_default_network_persist_static_routes(
    asset: InventoryAsset,
    *,
    settings: Settings,
    uplink_interface: str,
    uplink_gateway_ip: str,
) -> list[dict[str, str]]:
    if not uplink_gateway_ip:
        return []

    wazuh_agent_vars = _build_wazuh_agent_vars_preview(asset, settings=settings)
    route_targets: list[str] = []
    for candidate in (
        wazuh_agent_vars.get("wazuh_agent_manager_address"),
        wazuh_agent_vars.get("wazuh_agent_registration_server"),
    ):
        cleaned = _clean_optional(str(candidate or ""))
        if cleaned and cleaned not in route_targets:
            route_targets.append(cleaned)

    ipc_alloy_vars = _build_ipc_alloy_vars_preview(asset, settings=settings)
    alloy_remote_write_host = _clean_optional(
        str(ipc_alloy_vars.get("ipc_alloy_mimir_remote_write_host") or "")
    )
    if alloy_remote_write_host and alloy_remote_write_host not in route_targets:
        route_targets.append(alloy_remote_write_host)

    routes: list[dict[str, str]] = []
    for target in route_targets:
        if "/" in target:
            destination = target
        else:
            try:
                parsed_target = ipaddress.ip_address(target)
            except ValueError:
                continue
            destination = f"{parsed_target}/32" if isinstance(parsed_target, ipaddress.IPv4Address) else f"{parsed_target}/128"
        routes.append(
            {
                "to": destination,
                "via": uplink_gateway_ip,
                "dev": uplink_interface,
            }
        )
    return routes


def _remote_unlock_device_id_for_asset(asset: InventoryAsset) -> str:
    provisioning_vars = asset.provisioning_vars if isinstance(asset.provisioning_vars, dict) else {}
    candidate = provisioning_vars.get("remote_unlock_device_id")
    if isinstance(candidate, str):
        cleaned = candidate.strip()
        if cleaned:
            return cleaned
    return asset.inventory_hostname or asset.hostname or "cascadya-ipc"


def _build_remote_unlock_vars_preview(asset: InventoryAsset, *, settings: Settings | None = None) -> dict[str, Any]:
    if settings is None:
        settings = load_settings()
    provisioning_vars = asset.provisioning_vars if isinstance(asset.provisioning_vars, dict) else {}
    uplink_interface = asset.uplink_interface or "enp2s0"
    uplink_gateway_ip = asset.gateway_ip or ""
    ipc_alloy_vars = _build_ipc_alloy_vars_preview(asset, settings=settings)
    default_network_persist_static_routes = _build_default_network_persist_static_routes(
        asset,
        settings=settings,
        uplink_interface=uplink_interface,
        uplink_gateway_ip=uplink_gateway_ip,
    )
    return {
        "remote_unlock_enable": True,
        "remote_unlock_device_id": _remote_unlock_device_id_for_asset(asset),
        "remote_unlock_transport_mode": provisioning_vars.get("remote_unlock_transport_mode", "wireguard"),
        "remote_unlock_manage_wireguard": True,
        "remote_unlock_broker_url": provisioning_vars.get("remote_unlock_broker_url", DEFAULT_REMOTE_UNLOCK_BROKER_URL),
        "remote_unlock_management_interface": asset.management_interface or "enp3s0",
        "remote_unlock_uplink_interface": uplink_interface,
        "remote_unlock_gateway_ip": uplink_gateway_ip,
        "remote_unlock_wg_interface": provisioning_vars.get("remote_unlock_wg_interface", DEFAULT_REMOTE_UNLOCK_WG_INTERFACE),
        "network_uplink_interface": uplink_interface,
        "network_uplink_gateway_ip": uplink_gateway_ip,
        "network_persist_management_interface": asset.management_interface or "enp3s0",
        "network_persist_management_address": provisioning_vars.get("network_persist_management_address", ""),
        "network_persist_uplink_interface": uplink_interface,
        "network_persist_uplink_address": provisioning_vars.get("network_persist_uplink_address", ""),
        "network_persist_uplink_gateway_ip": provisioning_vars.get("network_persist_uplink_gateway_ip", uplink_gateway_ip),
        "network_persist_static_routes": provisioning_vars.get(
            "network_persist_static_routes",
            default_network_persist_static_routes,
        ),
        "ipc_alloy_mimir_remote_write_url": ipc_alloy_vars.get("ipc_alloy_mimir_remote_write_url", ""),
        "ipc_alloy_mimir_remote_write_host": ipc_alloy_vars.get("ipc_alloy_mimir_remote_write_host", ""),
        "network_wireguard_address": asset.wireguard_address or "",
        "network_wireguard_private_key": provisioning_vars.get(
            "network_wireguard_private_key",
            DEFAULT_REMOTE_UNLOCK_PRIVATE_KEY,
        ),
        "network_wireguard_peer_public_key": provisioning_vars.get(
            "network_wireguard_peer_public_key",
            DEFAULT_REMOTE_UNLOCK_PEER_PUBLIC_KEY,
        ),
        "network_wireguard_endpoint": provisioning_vars.get(
            "network_wireguard_endpoint",
            DEFAULT_REMOTE_UNLOCK_WG_ENDPOINT,
        ),
        "network_wireguard_allowed_ips": provisioning_vars.get(
            "network_wireguard_allowed_ips",
            DEFAULT_REMOTE_UNLOCK_ALLOWED_IPS,
        ),
        "network_bootstrap_nameservers": provisioning_vars.get(
            "network_bootstrap_nameservers",
            DEFAULT_REMOTE_UNLOCK_BOOTSTRAP_NAMESERVERS,
        ),
    }


def _extract_remote_unlock_broker_host_and_port(broker_url: str | None) -> tuple[str | None, int | None]:
    return _extract_endpoint_host_and_port(broker_url)


def _remote_unlock_broker_cert_sans(broker_url: str | None) -> tuple[str, str]:
    host, _ = _extract_remote_unlock_broker_host_and_port(broker_url)
    if host is None:
        return "", ""
    try:
        parsed_ip = ipaddress.ip_address(host)
    except ValueError:
        return host, ""
    if isinstance(parsed_ip, ipaddress.IPv4Address):
        return "", str(parsed_ip)
    return host, ""


def _remote_unlock_broker_cert_common_name(
    broker_url: str | None, *, settings: Settings
) -> str:
    broker_san_dns, _ = _remote_unlock_broker_cert_sans(broker_url)
    if broker_san_dns:
        return broker_san_dns
    if settings.provisioning_remote_unlock_broker_inventory_hostname:
        return settings.provisioning_remote_unlock_broker_inventory_hostname
    return "remote-unlock-broker"


def _build_remote_unlock_broker_vars_preview(asset: InventoryAsset, *, settings: Settings) -> dict[str, Any]:
    provisioning_vars = asset.provisioning_vars if isinstance(asset.provisioning_vars, dict) else {}
    broker_url = provisioning_vars.get(
        "remote_unlock_broker_url",
        settings.provisioning_remote_unlock_broker_url_default or DEFAULT_REMOTE_UNLOCK_BROKER_URL,
    )
    _, broker_port = _extract_remote_unlock_broker_host_and_port(str(broker_url))
    probe_enable = _coerce_bool(
        provisioning_vars.get("remote_unlock_broker_control_plane_probe_enable"),
        default=settings.provisioning_remote_unlock_broker_probe_token is not None,
    )
    broker_san_dns, broker_san_ip = _remote_unlock_broker_cert_sans(str(broker_url))
    peer_allowed_ips = _coerce_string_list(
        provisioning_vars.get("remote_unlock_broker_wireguard_peer_allowed_ips"),
        fallback=[asset.wireguard_address] if asset.wireguard_address else [],
    )
    return {
        "remote_unlock_broker_bind_port": broker_port or 8443,
        "remote_unlock_broker_control_plane_probe_enable": probe_enable,
        "remote_unlock_broker_control_plane_probe_bind_port": provisioning_vars.get(
            "remote_unlock_broker_control_plane_probe_bind_port",
            settings.provisioning_remote_unlock_broker_probe_port,
        ),
        "remote_unlock_broker_control_plane_probe_publish_address": provisioning_vars.get(
            "remote_unlock_broker_control_plane_probe_publish_address",
            "",
        ),
        "remote_unlock_broker_control_plane_probe_nats_url": provisioning_vars.get(
            "remote_unlock_broker_control_plane_probe_nats_url",
            "tls://host.docker.internal:4222",
        ),
        "remote_unlock_broker_control_plane_probe_monitoring_url": provisioning_vars.get(
            "remote_unlock_broker_control_plane_probe_monitoring_url",
            "http://host.docker.internal:8222",
        ),
        "remote_unlock_broker_control_plane_probe_ca_cert_src": provisioning_vars.get(
            "remote_unlock_broker_control_plane_probe_ca_cert_src",
            settings.provisioning_nats_server_ca_cert_path or "",
        ),
        "remote_unlock_broker_vault_addr": settings.provisioning_remote_unlock_broker_vault_addr or "",
        "remote_unlock_broker_vault_kv_mount": settings.provisioning_remote_unlock_broker_vault_kv_mount,
        "remote_unlock_broker_vault_kv_prefix": settings.provisioning_remote_unlock_broker_vault_kv_prefix,
        "remote_unlock_device_id": _remote_unlock_device_id_for_asset(asset),
        "remote_unlock_broker_wireguard_interface": settings.provisioning_remote_unlock_broker_wireguard_interface,
        "remote_unlock_broker_wireguard_address": (
            settings.provisioning_remote_unlock_broker_wireguard_address or "10.30.0.1/24"
        ),
        "remote_unlock_broker_wireguard_listen_port": settings.provisioning_remote_unlock_broker_wireguard_listen_port,
        "remote_unlock_broker_wireguard_peer_public_key": provisioning_vars.get(
            "network_wireguard_public_key",
            "",
        ),
        "remote_unlock_broker_wireguard_peer_allowed_ips": peer_allowed_ips,
        "remote_unlock_demo_broker_name": _remote_unlock_broker_cert_common_name(
            broker_url, settings=settings
        ),
        "remote_unlock_demo_broker_san_dns": broker_san_dns,
        "remote_unlock_demo_broker_san_ip": broker_san_ip,
        "remote_unlock_generate_demo_broker_certs_force": provisioning_vars.get(
            "remote_unlock_generate_demo_broker_certs_force",
            False,
        ),
    }


def _wireguard_value_is_missing_or_placeholder(value: Any) -> bool:
    cleaned = _clean_optional(str(value) if value is not None else None)
    if cleaned is None:
        return True
    return cleaned.startswith("REPLACE_")


def _run_wg_command(*args: str, input_text: str | None = None) -> str:
    wg_binary = shutil.which("wg")
    if wg_binary is None:
        raise FleetValidationError(
            "Le binaire 'wg' est introuvable sur la VM control-panel. "
            "Installe wireguard-tools avant de generer automatiquement les cles IPC."
        )

    try:
        result = subprocess.run(
            [wg_binary, *args],
            input=input_text,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise FleetValidationError(
            f"La commande '{wg_binary} {' '.join(args)}' a expire pendant la generation de la cle WireGuard."
        ) from exc
    except OSError as exc:
        raise FleetValidationError(
            f"Impossible d'executer '{wg_binary}' pour gerer les cles WireGuard: {exc}."
        ) from exc

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise FleetValidationError(
            "La commande WireGuard a echoue pendant la preparation du provisioning: "
            + (stderr or f"code {result.returncode}")
        )

    output = (result.stdout or "").strip()
    if not output:
        raise FleetValidationError("La commande WireGuard n'a produit aucune sortie exploitable.")
    return output


def _generate_wireguard_private_key_material() -> str:
    return _run_wg_command("genkey")


def _derive_wireguard_public_key_material(private_key: str) -> str:
    return _run_wg_command("pubkey", input_text=f"{private_key.strip()}\n")


def _ensure_asset_runtime_provisioning_vars(asset: InventoryAsset, *, settings: Settings) -> dict[str, Any]:
    provisioning_vars = _clean_provisioning_vars(
        asset.provisioning_vars if isinstance(asset.provisioning_vars, dict) else {}
    )
    inventory_hostname = asset.inventory_hostname or asset.hostname or "cascadya-ipc"
    provisioning_vars["edge_agent_nats_url"] = _normalize_edge_agent_nats_url(
        provisioning_vars.get("edge_agent_nats_url")
    )
    tenant, retention_profile = _resolve_ipc_alloy_contract(provisioning_vars, settings=settings)
    provisioning_vars["ipc_alloy_mimir_tenant"] = tenant
    provisioning_vars["ipc_alloy_mimir_tenant_label"] = tenant
    provisioning_vars["ipc_alloy_retention_profile"] = retention_profile
    provisioning_vars["ipc_metrics_tenant_label"] = tenant
    provisioning_vars["ipc_metrics_retention_profile"] = retention_profile
    provisioning_vars.setdefault(
        "ipc_metrics_source",
        _clean_optional(str(provisioning_vars.get("ipc_alloy_labels_source") or "")) or "ipc",
    )
    provisioning_vars.setdefault(
        "ipc_metrics_role",
        _clean_optional(str(provisioning_vars.get("ipc_alloy_labels_role") or "")) or "ipc",
    )
    provisioning_vars.setdefault(
        "ipc_metrics_node",
        _clean_optional(str(provisioning_vars.get("ipc_alloy_labels_node") or "")) or inventory_hostname,
    )
    node_exporter_port = _normalize_port(
        _coerce_optional_int(
            provisioning_vars.get("ipc_alloy_node_exporter_port"),
            field_name="ipc_alloy_node_exporter_port",
        ),
        field_name="ipc_alloy_node_exporter_port",
        default=DEFAULT_IPC_ALLOY_NODE_EXPORTER_PORT,
    )
    provisioning_vars.setdefault(
        "ipc_metrics_instance",
        f"{provisioning_vars['ipc_metrics_node']}:{node_exporter_port}",
    )
    provisioning_vars["ipc_alloy_send_tenant_header"] = _coerce_bool(
        provisioning_vars.get("ipc_alloy_send_tenant_header"),
        default=True,
    )

    if (
        settings.provisioning_remote_unlock_broker_url_default
        and _wireguard_value_is_missing_or_placeholder(provisioning_vars.get("remote_unlock_broker_url"))
    ):
        provisioning_vars["remote_unlock_broker_url"] = settings.provisioning_remote_unlock_broker_url_default

    if (
        settings.provisioning_wireguard_endpoint_default
        and _wireguard_value_is_missing_or_placeholder(provisioning_vars.get("network_wireguard_endpoint"))
    ):
        provisioning_vars["network_wireguard_endpoint"] = settings.provisioning_wireguard_endpoint_default

    if (
        settings.provisioning_wireguard_peer_public_key_default
        and _wireguard_value_is_missing_or_placeholder(provisioning_vars.get("network_wireguard_peer_public_key"))
    ):
        provisioning_vars["network_wireguard_peer_public_key"] = (
            settings.provisioning_wireguard_peer_public_key_default
        )

    private_key = provisioning_vars.get("network_wireguard_private_key")
    if (
        settings.provisioning_auto_generate_wireguard_private_key
        and _wireguard_value_is_missing_or_placeholder(private_key)
    ):
        private_key = _generate_wireguard_private_key_material()
        provisioning_vars["network_wireguard_private_key"] = private_key

    if not _wireguard_value_is_missing_or_placeholder(private_key) and _wireguard_value_is_missing_or_placeholder(
        provisioning_vars.get("network_wireguard_public_key")
    ):
        provisioning_vars["network_wireguard_public_key"] = _derive_wireguard_public_key_material(str(private_key))

    asset.provisioning_vars = provisioning_vars
    return provisioning_vars


def list_provisioning_workflows() -> list[dict[str, Any]]:
    return [
        {
            "key": "full-ipc-wireguard-onboarding",
            "label": "IPC complet via WireGuard",
            "description": "Genere les certificats, stage le bundle remote-unlock, prepare le peer broker WireGuard, bootstrap WireGuard, valide le flux, deploie l'agent Wazuh, deploie la chaine node_exporter + Alloy vers Mimir, puis deploie, valide et teste le round-trip NATS de l'edge-agent.",
            "notes": [
                "Suppose qu'un broker/Vault remote-unlock soit deja disponible.",
                "C'est le workflow le plus proche du runbook cible pour un nouvel IPC deja reachable en SSH.",
                "Le secret LUKS remote-unlock est seed automatiquement s'il est absent dans Vault.",
                "Si le secret existe deja avec la meme valeur, le seed devient un no-op idempotent.",
                "Si le secret existe deja avec une autre valeur, l'ecrasement requiert une confirmation explicite au lancement du job.",
                "Une etape dediee peut figer la topologie IP detectee sur l'IPC pour reappliquer les adresses et routes au boot.",
                "Le deploiement Wazuh suppose qu'un manager Wazuh reachable expose deja 1514/TCP et 1515/TCP pour l'IPC, idealement via une IP privee ou un FQDN stable sur overlay WireGuard.",
                "Le deploiement IPC Alloy suppose qu'une VM monitoring expose Mimir en remote_write, idealement sur un endpoint prive stable via l'overlay WireGuard du site.",
                "Le bundle TLS client edge-agent est genere automatiquement depuis Vault avant le deploiement de la telemetrie.",
                "Le workflow termine maintenant par un round-trip NATS request/reply pour mesurer le chemin Control Panel -> Broker -> IPC.",
            ],
            "steps": [
                {
                    "key": "remote-unlock-generate-certs",
                    "label": "Generer les certificats remote-unlock",
                    "playbook_name": "remote-unlock-generate-certs.yml",
                    "inventory_kind": "remote_unlock",
                    "scope": "controller",
                    "phase": "prepare",
                },
                {
                    "key": "remote-unlock-generate-broker-certs",
                    "label": "Initialiser le certificat TLS du broker",
                    "playbook_name": "remote-unlock-generate-broker-certs.yml",
                    "inventory_kind": "remote_unlock_broker",
                    "scope": "controller",
                    "phase": "prepare",
                },
                {
                    "key": "remote-unlock-stage-certs",
                    "label": "Stager les certificats sur l'IPC",
                    "playbook_name": "remote-unlock-stage-certs.yml",
                    "inventory_kind": "remote_unlock",
                    "scope": "ipc",
                    "phase": "deploy",
                },
                {
                    "key": IPC_NETWORK_PERSIST_STEP_KEY,
                    "label": "Persister les IP et routages de l'IPC",
                    "playbook_name": IPC_NETWORK_PERSIST_PLAYBOOK,
                    "inventory_kind": "remote_unlock",
                    "scope": "ipc",
                    "phase": "deploy",
                },
                {
                    "key": "remote-unlock-prepare-broker-wireguard",
                    "label": "Preparer le peer WireGuard sur le broker",
                    "playbook_name": "remote-unlock-prepare-broker-wireguard.yml",
                    "inventory_kind": "remote_unlock_broker",
                    "scope": "broker",
                    "phase": "deploy",
                },
                {
                    "key": "remote-unlock-deploy-broker",
                    "label": "Deployer le broker remote-unlock",
                    "playbook_name": "remote-unlock-deploy-broker.yml",
                    "inventory_kind": "remote_unlock_broker",
                    "scope": "broker",
                    "phase": "deploy",
                },
                {
                    "key": REMOTE_UNLOCK_SEED_VAULT_STEP_KEY,
                    "label": "Seeder le secret remote-unlock dans Vault",
                    "playbook_name": REMOTE_UNLOCK_SEED_VAULT_PLAYBOOK,
                    "inventory_kind": "remote_unlock_broker",
                    "scope": "broker",
                    "phase": "deploy",
                },
                {
                    "key": "remote-unlock-bootstrap",
                    "label": "Bootstrap remote-unlock",
                    "playbook_name": "remote-unlock-bootstrap.yml",
                    "inventory_kind": "remote_unlock",
                    "scope": "ipc",
                    "phase": "deploy",
                },
                {
                    "key": "remote-unlock-preflight",
                    "label": "Preflight remote-unlock",
                    "playbook_name": "remote-unlock-preflight.yml",
                    "inventory_kind": "remote_unlock",
                    "scope": "ipc",
                    "phase": "verify",
                },
                {
                    "key": "remote-unlock-validate",
                    "label": "Valider remote-unlock",
                    "playbook_name": "remote-unlock-validate.yml",
                    "inventory_kind": "remote_unlock",
                    "scope": "ipc",
                    "phase": "verify",
                },
                {
                    "key": WAZUH_AGENT_DEPLOY_STEP_KEY,
                    "label": "Deployer wazuh-agent",
                    "playbook_name": WAZUH_AGENT_DEPLOY_PLAYBOOK,
                    "inventory_kind": "wazuh_agent",
                    "scope": "ipc",
                    "phase": "deploy",
                },
                {
                    "key": WAZUH_AGENT_VALIDATE_STEP_KEY,
                    "label": "Valider wazuh-agent",
                    "playbook_name": WAZUH_AGENT_VALIDATE_PLAYBOOK,
                    "inventory_kind": "wazuh_agent",
                    "scope": "ipc",
                    "phase": "verify",
                },
                {
                    "key": IPC_ALLOY_DEPLOY_STEP_KEY,
                    "label": "Deployer node_exporter + Alloy",
                    "playbook_name": IPC_ALLOY_DEPLOY_PLAYBOOK,
                    "inventory_kind": "ipc_alloy",
                    "scope": "ipc",
                    "phase": "deploy",
                },
                {
                    "key": IPC_ALLOY_VALIDATE_STEP_KEY,
                    "label": "Valider node_exporter + Alloy",
                    "playbook_name": IPC_ALLOY_VALIDATE_PLAYBOOK,
                    "inventory_kind": "ipc_alloy",
                    "scope": "ipc",
                    "phase": "verify",
                },
                {
                    "key": EDGE_AGENT_GENERATE_CERTS_STEP_KEY,
                    "label": "Generer les certificats edge-agent",
                    "playbook_name": EDGE_AGENT_GENERATE_CERTS_PLAYBOOK,
                    "inventory_kind": "edge_agent",
                    "scope": "controller",
                    "phase": "prepare",
                },
                {
                    "key": "edge-agent-deploy",
                    "label": "Deployer edge-agent",
                    "playbook_name": "edge-agent-deploy.yml",
                    "inventory_kind": "edge_agent",
                    "scope": "ipc",
                    "phase": "deploy",
                },
                {
                    "key": "edge-agent-validate",
                    "label": "Valider edge-agent",
                    "playbook_name": "edge-agent-validate.yml",
                    "inventory_kind": "edge_agent",
                    "scope": "ipc",
                    "phase": "verify",
                },
                {
                    "key": EDGE_AGENT_NATS_ROUNDTRIP_STEP_KEY,
                    "label": "Tester le round-trip NATS edge-agent",
                    "playbook_name": EDGE_AGENT_NATS_ROUNDTRIP_PLAYBOOK,
                    "inventory_kind": "edge_agent",
                    "scope": "controller",
                    "phase": "verify",
                },
            ],
        },
        {
            "key": "remote-unlock-wireguard-validation",
            "label": "Remote unlock WireGuard",
            "description": "Workflow dedie a la brique remote-unlock sur un IPC deja onboardingue, avec preparation automatique du peer broker WireGuard.",
            "notes": [
                "Ideal pour valider le dry-run remote-unlock avant un cutover.",
                "Le secret LUKS remote-unlock est seed automatiquement s'il est absent dans Vault.",
                "Si le secret existe deja avec la meme valeur, le seed devient un no-op idempotent.",
                "Si le secret existe deja avec une autre valeur, l'ecrasement requiert une confirmation explicite au lancement du job.",
                "La persistance reseau peut etre relancee seule en mode manuel pour figer l'etat present des interfaces de l'IPC.",
            ],
            "steps": [
                {
                    "key": "remote-unlock-generate-certs",
                    "label": "Generer les certificats remote-unlock",
                    "playbook_name": "remote-unlock-generate-certs.yml",
                    "inventory_kind": "remote_unlock",
                    "scope": "controller",
                    "phase": "prepare",
                },
                {
                    "key": "remote-unlock-generate-broker-certs",
                    "label": "Initialiser le certificat TLS du broker",
                    "playbook_name": "remote-unlock-generate-broker-certs.yml",
                    "inventory_kind": "remote_unlock_broker",
                    "scope": "controller",
                    "phase": "prepare",
                },
                {
                    "key": "remote-unlock-stage-certs",
                    "label": "Stager les certificats sur l'IPC",
                    "playbook_name": "remote-unlock-stage-certs.yml",
                    "inventory_kind": "remote_unlock",
                    "scope": "ipc",
                    "phase": "deploy",
                },
                {
                    "key": IPC_NETWORK_PERSIST_STEP_KEY,
                    "label": "Persister les IP et routages de l'IPC",
                    "playbook_name": IPC_NETWORK_PERSIST_PLAYBOOK,
                    "inventory_kind": "remote_unlock",
                    "scope": "ipc",
                    "phase": "deploy",
                },
                {
                    "key": "remote-unlock-prepare-broker-wireguard",
                    "label": "Preparer le peer WireGuard sur le broker",
                    "playbook_name": "remote-unlock-prepare-broker-wireguard.yml",
                    "inventory_kind": "remote_unlock_broker",
                    "scope": "broker",
                    "phase": "deploy",
                },
                {
                    "key": "remote-unlock-deploy-broker",
                    "label": "Deployer le broker remote-unlock",
                    "playbook_name": "remote-unlock-deploy-broker.yml",
                    "inventory_kind": "remote_unlock_broker",
                    "scope": "broker",
                    "phase": "deploy",
                },
                {
                    "key": REMOTE_UNLOCK_SEED_VAULT_STEP_KEY,
                    "label": "Seeder le secret remote-unlock dans Vault",
                    "playbook_name": REMOTE_UNLOCK_SEED_VAULT_PLAYBOOK,
                    "inventory_kind": "remote_unlock_broker",
                    "scope": "broker",
                    "phase": "deploy",
                },
                {
                    "key": "remote-unlock-bootstrap",
                    "label": "Bootstrap remote-unlock",
                    "playbook_name": "remote-unlock-bootstrap.yml",
                    "inventory_kind": "remote_unlock",
                    "scope": "ipc",
                    "phase": "deploy",
                },
                {
                    "key": "remote-unlock-preflight",
                    "label": "Preflight remote-unlock",
                    "playbook_name": "remote-unlock-preflight.yml",
                    "inventory_kind": "remote_unlock",
                    "scope": "ipc",
                    "phase": "verify",
                },
                {
                    "key": "remote-unlock-validate",
                    "label": "Valider remote-unlock",
                    "playbook_name": "remote-unlock-validate.yml",
                    "inventory_kind": "remote_unlock",
                    "scope": "ipc",
                    "phase": "verify",
                },
            ],
        },
        {
            "key": "wazuh-agent-deploy-validate",
            "label": "Wazuh agent",
            "description": "Deploie puis valide l'agent Wazuh sur un IPC deja onboardingue et joignable.",
            "notes": [
                "Utiliser ce workflow pour tester l'enrollment Wazuh avant de l'inclure dans un onboarding complet.",
                "Le manager Wazuh doit etre reachable depuis l'IPC sur 1514/TCP et 1515/TCP, idealement via une IP privee ou un FQDN stable sur overlay WireGuard.",
                "Si un groupe Wazuh est renseigne, il doit deja exister cote manager avant l'enrollment.",
            ],
            "steps": [
                {
                    "key": WAZUH_AGENT_DEPLOY_STEP_KEY,
                    "label": "Deployer wazuh-agent",
                    "playbook_name": WAZUH_AGENT_DEPLOY_PLAYBOOK,
                    "inventory_kind": "wazuh_agent",
                    "scope": "ipc",
                    "phase": "deploy",
                },
                {
                    "key": WAZUH_AGENT_VALIDATE_STEP_KEY,
                    "label": "Valider wazuh-agent",
                    "playbook_name": WAZUH_AGENT_VALIDATE_PLAYBOOK,
                    "inventory_kind": "wazuh_agent",
                    "scope": "ipc",
                    "phase": "verify",
                },
            ],
        },
        {
            "key": "ipc-alloy-deploy-validate",
            "label": "IPC Alloy metrics",
            "description": "Deploie puis valide node_exporter + Alloy sur un IPC pour pousser les metriques host vers Mimir.",
            "notes": [
                "Workflow dedie a la chaine de metriques infrastructure de l'IPC.",
                "Le endpoint remote_write Mimir doit etre reachable depuis l'IPC, idealement via une IP privee ou un FQDN stable sur l'overlay WireGuard.",
                "Le tenant Mimir cible (`classic`, `lts-1y`, `lts-5y`) est passe via X-Scope-OrgID.",
            ],
            "steps": [
                {
                    "key": IPC_ALLOY_DEPLOY_STEP_KEY,
                    "label": "Deployer node_exporter + Alloy",
                    "playbook_name": IPC_ALLOY_DEPLOY_PLAYBOOK,
                    "inventory_kind": "ipc_alloy",
                    "scope": "ipc",
                    "phase": "deploy",
                },
                {
                    "key": IPC_ALLOY_VALIDATE_STEP_KEY,
                    "label": "Valider node_exporter + Alloy",
                    "playbook_name": IPC_ALLOY_VALIDATE_PLAYBOOK,
                    "inventory_kind": "ipc_alloy",
                    "scope": "ipc",
                    "phase": "verify",
                },
            ],
        },
        {
            "key": "edge-agent-deploy-validate",
            "label": "Edge-agent telemetry",
            "description": "Deploie, valide et teste le round-trip NATS des services de telemetrie edge-agent sur l'IPC.",
            "notes": [
                "Utile si l'IPC est deja prepare cote remote-unlock.",
                "Le bundle TLS client edge-agent est regenere automatiquement depuis Vault avant le deploiement.",
                "Le workflow se termine par un round-trip NATS request/reply pour confirmer le chemin broker -> IPC.",
            ],
            "steps": [
                {
                    "key": EDGE_AGENT_GENERATE_CERTS_STEP_KEY,
                    "label": "Generer les certificats edge-agent",
                    "playbook_name": EDGE_AGENT_GENERATE_CERTS_PLAYBOOK,
                    "inventory_kind": "edge_agent",
                    "scope": "controller",
                    "phase": "prepare",
                },
                {
                    "key": "edge-agent-deploy",
                    "label": "Deployer edge-agent",
                    "playbook_name": "edge-agent-deploy.yml",
                    "inventory_kind": "edge_agent",
                    "scope": "ipc",
                    "phase": "deploy",
                },
                {
                    "key": "edge-agent-validate",
                    "label": "Valider edge-agent",
                    "playbook_name": "edge-agent-validate.yml",
                    "inventory_kind": "edge_agent",
                    "scope": "ipc",
                    "phase": "verify",
                },
                {
                    "key": EDGE_AGENT_NATS_ROUNDTRIP_STEP_KEY,
                    "label": "Tester le round-trip NATS edge-agent",
                    "playbook_name": EDGE_AGENT_NATS_ROUNDTRIP_PLAYBOOK,
                    "inventory_kind": "edge_agent",
                    "scope": "controller",
                    "phase": "verify",
                },
            ],
        },
        {
            "key": "remote-unlock-cutover",
            "label": "Cutover remote unlock",
            "description": "Applique la bascule finalisee de remote-unlock puis retire le token TPM local.",
            "notes": [
                "Ne pas lancer tant que remote-unlock-validate n'est pas vert.",
                "Workflow reserve a la bascule finale, apres validation complete du lab.",
            ],
            "steps": [
                {
                    "key": "remote-unlock-cutover",
                    "label": "Bascule remote-unlock",
                    "playbook_name": "remote-unlock-cutover.yml",
                    "inventory_kind": "remote_unlock",
                    "scope": "ipc",
                    "phase": "cutover",
                },
                {
                    "key": "remote-unlock-remove-local-tpm",
                    "label": "Retirer le TPM local",
                    "playbook_name": "remote-unlock-remove-local-tpm.yml",
                    "inventory_kind": "remote_unlock",
                    "scope": "ipc",
                    "phase": "cutover",
                },
            ],
        },
    ]


def _get_provisioning_workflow(workflow_key: str | None) -> dict[str, Any]:
    selected_key = _clean_optional(workflow_key) or DEFAULT_PROVISIONING_WORKFLOW_KEY
    for workflow in list_provisioning_workflows():
        if workflow["key"] == selected_key:
            return workflow
    raise FleetValidationError(f"Workflow de provisioning inconnu: {selected_key}.")


def _workflow_contains_playbook(steps: list[dict[str, Any]], playbook_name: str) -> bool:
    return any(str(step.get("playbook_name") or "") == playbook_name for step in steps)


def _build_workflow_files(
    asset: InventoryAsset,
    *,
    inventory_group: str,
    settings: Settings,
) -> dict[str, dict[str, Any]]:
    if not asset.inventory_hostname:
        raise FleetValidationError("L'asset doit avoir un inventory_hostname avant de preparer un workflow.")

    edge_inventory_filename = _normalize_generated_filename(asset.inventory_hostname, "edge-agent", "ini")
    edge_vars_filename = _normalize_generated_filename(asset.inventory_hostname, "edge-agent", "vars.json")
    wazuh_inventory_filename = _normalize_generated_filename(asset.inventory_hostname, "wazuh-agent", "ini")
    wazuh_vars_filename = _normalize_generated_filename(asset.inventory_hostname, "wazuh-agent", "vars.json")
    ipc_alloy_inventory_filename = _normalize_generated_filename(asset.inventory_hostname, "ipc-alloy", "ini")
    ipc_alloy_vars_filename = _normalize_generated_filename(asset.inventory_hostname, "ipc-alloy", "vars.json")
    remote_unlock_broker_inventory_filename = _normalize_generated_filename(
        asset.inventory_hostname,
        "remote-unlock-broker",
        "ini",
    )
    remote_unlock_broker_vars_filename = _normalize_generated_filename(
        asset.inventory_hostname,
        "remote-unlock-broker",
        "vars.json",
    )
    remote_unlock_inventory_filename = _normalize_generated_filename(asset.inventory_hostname, "remote-unlock", "ini")
    remote_unlock_vars_filename = _normalize_generated_filename(asset.inventory_hostname, "remote-unlock", "vars.json")

    return {
        "edge_agent": {
            "inventory_path": f"generated/{edge_inventory_filename}",
            "vars_path": f"generated/{edge_vars_filename}",
            "inventory_preview": _build_edge_agent_inventory_preview(asset, inventory_group=inventory_group),
            "vars_preview": _json_preview(_build_edge_agent_vars_preview(asset, settings=settings)),
        },
        "wazuh_agent": {
            "inventory_path": f"generated/{wazuh_inventory_filename}",
            "vars_path": f"generated/{wazuh_vars_filename}",
            "inventory_preview": _build_wazuh_agent_inventory_preview(asset, inventory_group=inventory_group),
            "vars_preview": _json_preview(_build_wazuh_agent_vars_preview(asset, settings=settings)),
        },
        "ipc_alloy": {
            "inventory_path": f"generated/{ipc_alloy_inventory_filename}",
            "vars_path": f"generated/{ipc_alloy_vars_filename}",
            "inventory_preview": _build_ipc_alloy_inventory_preview(asset, inventory_group=inventory_group),
            "vars_preview": _json_preview(_build_ipc_alloy_vars_preview(asset, settings=settings)),
        },
        "remote_unlock_broker": {
            "inventory_path": f"generated/{remote_unlock_broker_inventory_filename}",
            "vars_path": f"generated/{remote_unlock_broker_vars_filename}",
            "inventory_preview": _build_remote_unlock_broker_inventory_preview(asset, settings=settings),
            "vars_preview": _json_preview(_build_remote_unlock_broker_vars_preview(asset, settings=settings)),
        },
        "remote_unlock": {
            "inventory_path": f"generated/{remote_unlock_inventory_filename}",
            "vars_path": f"generated/{remote_unlock_vars_filename}",
            "inventory_preview": _build_remote_unlock_inventory_preview(asset, inventory_group=inventory_group),
            "vars_preview": _json_preview(_build_remote_unlock_vars_preview(asset, settings=settings)),
        },
    }


def _build_workflow_step_command(
    *,
    playbook_path: str,
    inventory_path: str,
    vars_path: str,
    ansible_config_path: str | None = None,
    scope: str,
) -> str:
    rendered_parts: list[str] = []
    if ansible_config_path:
        rendered_parts.append(f"ANSIBLE_CONFIG={shlex.quote(ansible_config_path)}")
    rendered_parts.extend(
        [
            "ansible-playbook",
            "-i",
            shlex.quote(inventory_path),
            shlex.quote(playbook_path),
            "--extra-vars",
            shlex.quote(f"@{vars_path}"),
        ]
    )
    return " ".join(rendered_parts)


def _resolve_ansible_config_path(playbook_root: str | None) -> Path | None:
    cleaned_root = _clean_optional(playbook_root)
    if not cleaned_root:
        return None
    candidate = Path(cleaned_root).expanduser() / "ansible.cfg"
    if candidate.exists():
        return candidate
    return None


def _build_workflow_context(
    asset: InventoryAsset,
    *,
    settings: Settings,
    workflow_key: str,
    inventory_group: str,
    dispatch_mode: str = "auto",
) -> dict[str, Any]:
    workflow = _get_provisioning_workflow(workflow_key)
    workflow_files = _build_workflow_files(asset, inventory_group=inventory_group, settings=settings)
    playbook_root = Path(settings.provisioning_playbook_root).expanduser() if settings.provisioning_playbook_root else None
    ansible_config_path = _resolve_ansible_config_path(str(playbook_root) if playbook_root else None)
    steps: list[dict[str, Any]] = []
    readiness_reasons: list[str] = []
    normalized_dispatch_mode = _normalize_dispatch_mode(dispatch_mode)

    for order, step in enumerate(workflow["steps"], start=1):
        inventory_kind = str(step.get("inventory_kind") or "")
        file_bundle = workflow_files.get(inventory_kind)
        if not isinstance(file_bundle, dict):
            raise FleetValidationError(
                f"Le workflow reference un bundle d'artefacts inconnu: {inventory_kind or 'missing'}."
            )
        playbook_path = (playbook_root / step["playbook_name"]) if playbook_root else None
        playbook_path_str = str(playbook_path) if playbook_path else (Path("<ansible-root>") / step["playbook_name"]).as_posix()
        steps.append(
            {
                **step,
                "order": order,
                "status": "pending",
                "started_at": None,
                "completed_at": None,
                "error_message": None,
                "playbook_path": playbook_path_str,
                "playbook_exists": bool(playbook_path and playbook_path.exists()),
                "inventory_path": file_bundle["inventory_path"],
                "vars_path": file_bundle["vars_path"],
                "command": _build_workflow_step_command(
                    playbook_path=playbook_path_str,
                    inventory_path=file_bundle["inventory_path"],
                    vars_path=file_bundle["vars_path"],
                    ansible_config_path=str(ansible_config_path) if ansible_config_path else None,
                    scope=step["scope"],
                ),
            }
        )

    _apply_dispatch_mode_to_steps(steps, dispatch_mode=normalized_dispatch_mode)

    if not playbook_root:
        readiness_reasons.append("AUTH_PROTO_PROVISIONING_PLAYBOOK_ROOT n'est pas configure.")
    if not all(step["playbook_exists"] for step in steps):
        readiness_reasons.append("Un ou plusieurs playbooks du workflow sont introuvables sur la VM.")
    if shutil.which("ansible-playbook") is None:
        readiness_reasons.append("ansible-playbook n'est pas installe sur la VM control-panel.")
    if any(step.get("scope") == "ipc" for step in steps):
        if settings.provisioning_ssh_key_passphrase:
            readiness_reasons.append("La cle SSH de provisioning est protegee par passphrase et non supportee en mode non interactif.")
        elif not settings.provisioning_ssh_key_path and not settings.provisioning_ssh_password:
            readiness_reasons.append("Aucun secret SSH de provisioning n'est configure pour joindre l'IPC.")
    if any(step.get("scope") == "broker" for step in steps):
        broker_ssh_key_path = (
            settings.provisioning_remote_unlock_broker_ssh_key_path or settings.provisioning_ssh_key_path
        )
        broker_ssh_key_passphrase = settings.provisioning_remote_unlock_broker_ssh_key_passphrase
        if not settings.provisioning_remote_unlock_broker_ssh_key_path:
            broker_ssh_key_passphrase = broker_ssh_key_passphrase or settings.provisioning_ssh_key_passphrase
        broker_ssh_password = settings.provisioning_remote_unlock_broker_ssh_password

        if broker_ssh_key_passphrase:
            readiness_reasons.append(
                "La cle SSH du broker remote-unlock est protegee par passphrase et non supportee en mode non interactif."
            )
        if broker_ssh_key_path:
            broker_ssh_key_file = Path(broker_ssh_key_path).expanduser()
            if not broker_ssh_key_file.exists():
                readiness_reasons.append(
                    f"La cle SSH du broker remote-unlock est configuree mais introuvable sur la VM control-panel: {broker_ssh_key_file}"
                )
        elif not broker_ssh_password:
            readiness_reasons.append("Aucun secret SSH n'est configure pour joindre le broker remote-unlock.")
        if _clean_optional(settings.provisioning_remote_unlock_broker_ansible_host) is None:
            readiness_reasons.append("Le broker remote-unlock n'a pas d'ansible_host configure cote control-panel.")
        broker_vars = _build_remote_unlock_broker_vars_preview(asset, settings=settings)
        if _wireguard_value_is_missing_or_placeholder(broker_vars.get("remote_unlock_broker_wireguard_peer_public_key")):
            readiness_reasons.append("La cle publique WireGuard de l'IPC a publier sur le broker est absente.")
        broker_allowed_ips = broker_vars.get("remote_unlock_broker_wireguard_peer_allowed_ips")
        if not isinstance(broker_allowed_ips, list) or not broker_allowed_ips:
            readiness_reasons.append("L'IP WireGuard de l'IPC a autoriser sur le broker est absente.")
    if any(step.get("playbook_name") == "remote-unlock-generate-broker-certs.yml" for step in steps):
        broker_vars = _build_remote_unlock_broker_vars_preview(asset, settings=settings)
        if not broker_vars.get("remote_unlock_demo_broker_san_dns") and not broker_vars.get(
            "remote_unlock_demo_broker_san_ip"
        ):
            readiness_reasons.append(
                "Impossible de deduire le SAN TLS du broker remote-unlock a partir de remote_unlock_broker_url."
            )
    if any(
        str(step.get("playbook_name") or "")
        in {
            "remote-unlock-deploy-broker.yml",
            REMOTE_UNLOCK_SEED_VAULT_PLAYBOOK,
        }
        for step in steps
    ):
        if _clean_optional(settings.provisioning_remote_unlock_broker_vault_addr) is None:
            readiness_reasons.append("Le broker remote-unlock n'a pas d'adresse Vault configuree cote control-panel.")
        if _clean_optional(settings.provisioning_remote_unlock_broker_vault_token) is None:
            readiness_reasons.append("Le token Vault du broker remote-unlock n'est pas configure cote control-panel.")
    if any(str(step.get("playbook_name") or "") == EDGE_AGENT_GENERATE_CERTS_PLAYBOOK for step in steps):
        edge_agent_vars = _build_edge_agent_vars_preview(asset, settings=settings)
        if _clean_optional(str(edge_agent_vars.get("edge_agent_vault_addr") or "")) is None:
            readiness_reasons.append("L'etape de generation des certificats edge-agent n'a pas d'adresse Vault configuree.")
        if _clean_optional(settings.provisioning_remote_unlock_broker_vault_token) is None:
            readiness_reasons.append(
                "L'etape de generation des certificats edge-agent n'a pas de token Vault configure cote control-panel."
            )
    if any(step.get("inventory_kind") == "wazuh_agent" for step in steps):
        wazuh_agent_vars = _build_wazuh_agent_vars_preview(asset, settings=settings)
        if _clean_optional(str(wazuh_agent_vars.get("wazuh_agent_manager_address") or "")) is None:
            readiness_reasons.append("Le deploiement wazuh-agent n'a pas d'adresse de manager Wazuh configuree.")
        if _clean_optional(str(wazuh_agent_vars.get("wazuh_agent_registration_server") or "")) is None:
            readiness_reasons.append("Le deploiement wazuh-agent n'a pas de serveur d'enrollment Wazuh configure.")
        wazuh_ca_source_path = _clean_optional(
            str(wazuh_agent_vars.get("wazuh_agent_registration_ca_source_path") or "")
        )
        if wazuh_ca_source_path is not None and not Path(wazuh_ca_source_path).expanduser().exists():
            readiness_reasons.append(
                "Le certificat CA Wazuh a copier sur l'IPC est configure mais introuvable sur la VM control-panel."
            )
    if any(step.get("inventory_kind") == "ipc_alloy" for step in steps):
        ipc_alloy_vars = _build_ipc_alloy_vars_preview(asset, settings=settings)
        if _clean_optional(str(ipc_alloy_vars.get("ipc_alloy_mimir_remote_write_url") or "")) is None:
            readiness_reasons.append("Le deploiement IPC Alloy n'a pas d'endpoint remote_write Mimir configure.")
        ipc_alloy_ca_source_path = _clean_optional(
            str(ipc_alloy_vars.get("ipc_alloy_mimir_ca_source_path") or "")
        )
        if ipc_alloy_ca_source_path is not None and not Path(ipc_alloy_ca_source_path).expanduser().exists():
            readiness_reasons.append(
                "La CA Mimir a copier sur l'IPC est configuree mais introuvable sur la VM control-panel."
            )
        if (
            _clean_optional(str(ipc_alloy_vars.get("ipc_alloy_mimir_basic_auth_username") or "")) is not None
            and _clean_optional(settings.provisioning_ipc_alloy_mimir_password) is None
        ):
            readiness_reasons.append(
                "Le username basic_auth Alloy/Mimir est configure mais le mot de passe n'est pas configure cote control-panel."
            )
    if any(step.get("inventory_kind") == "remote_unlock" and step.get("scope") == "ipc" for step in steps):
        remote_unlock_vars = _build_remote_unlock_vars_preview(asset, settings=settings)
        if _wireguard_value_is_missing_or_placeholder(remote_unlock_vars.get("network_wireguard_address")):
            readiness_reasons.append("L'adresse WireGuard de l'IPC n'est pas renseignee.")
        if _wireguard_value_is_missing_or_placeholder(remote_unlock_vars.get("network_wireguard_private_key")):
            readiness_reasons.append("La cle privee WireGuard de l'IPC est absente ou encore sur une valeur REPLACE_*.")
        if _wireguard_value_is_missing_or_placeholder(remote_unlock_vars.get("network_wireguard_peer_public_key")):
            readiness_reasons.append("La cle publique WireGuard du broker est absente ou encore sur une valeur REPLACE_*.")
        if _wireguard_value_is_missing_or_placeholder(remote_unlock_vars.get("network_wireguard_endpoint")):
            readiness_reasons.append("L'endpoint WireGuard du broker est absent ou encore sur une valeur REPLACE_*.")

    return {
        "workflow": {
            "key": workflow["key"],
            "label": workflow["label"],
            "description": workflow["description"],
            "notes": list(workflow.get("notes", [])),
            "steps": steps,
        },
        "artifacts": {
            "edge_agent": workflow_files["edge_agent"],
            "wazuh_agent": workflow_files["wazuh_agent"],
            "ipc_alloy": workflow_files["ipc_alloy"],
            "remote_unlock_broker": workflow_files["remote_unlock_broker"],
            "remote_unlock": workflow_files["remote_unlock"],
        },
        "playbook_root": str(playbook_root) if playbook_root else None,
        "ready_for_real_execution": not readiness_reasons,
        "runner": {
            "ansible_config_path": str(ansible_config_path) if ansible_config_path else None,
            "dispatch_mode": normalized_dispatch_mode,
            "readiness_reasons": readiness_reasons,
        },
    }


def _extract_workflow_steps(job: ProvisioningJob) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    context = copy.deepcopy(job.context_json) if isinstance(job.context_json, dict) else {}
    workflow = context.get("workflow") if isinstance(context.get("workflow"), dict) else {}
    raw_steps = workflow.get("steps") if isinstance(workflow.get("steps"), list) else []
    steps = [step for step in raw_steps if isinstance(step, dict)]
    if not steps:
        raise FleetValidationError("Le job ne contient aucune etape de workflow exploitable.")
    return context, workflow, steps


def _workflow_dispatch_mode(context: dict[str, Any]) -> str:
    runner = context.get("runner") if isinstance(context.get("runner"), dict) else {}
    return _normalize_dispatch_mode(runner.get("dispatch_mode"))


def _apply_dispatch_mode_to_steps(steps: list[dict[str, Any]], *, dispatch_mode: str) -> None:
    if dispatch_mode == "manual":
        for step in steps:
            status = str(step.get("status") or "pending")
            if status in {"succeeded", "running", "failed"}:
                continue
            step["status"] = "ready"
        return

    found_blocker = False
    for step in steps:
        status = str(step.get("status") or "pending")
        if status == "succeeded":
            continue
        if status == "running":
            found_blocker = True
            continue
        if status == "failed":
            found_blocker = True
            continue
        if not found_blocker:
            step["status"] = "ready"
            found_blocker = True
        else:
            step["status"] = "locked"


def _select_runnable_workflow_step(
    steps: list[dict[str, Any]],
    *,
    dispatch_mode: str,
    requested_step_key: str | None,
) -> dict[str, Any] | None:
    running_step = next((step for step in steps if str(step.get("status") or "") == "running"), None)
    if running_step is not None:
        raise FleetValidationError(
            f"L'etape {running_step.get('order', '?')} ({running_step.get('label', running_step.get('key', 'unknown'))}) "
            "est deja en cours. Attends sa fin avant d'en lancer une autre."
        )

    normalized_requested_step_key = _clean_optional(requested_step_key)
    if normalized_requested_step_key is None:
        return next((step for step in steps if step.get("status") in {"ready", "failed"}), None)

    selected_step = next((step for step in steps if str(step.get("key") or "") == normalized_requested_step_key), None)
    if selected_step is None:
        raise FleetValidationError(f"L'etape '{normalized_requested_step_key}' est introuvable dans ce workflow.")

    selected_status = str(selected_step.get("status") or "pending")
    if selected_status == "succeeded":
        raise FleetValidationError(
            f"L'etape '{normalized_requested_step_key}' est deja validee dans ce job. Prepare un nouveau cycle pour la rejouer."
        )
    if selected_status == "running":
        raise FleetValidationError(f"L'etape '{normalized_requested_step_key}' est deja en cours d'execution.")
    if dispatch_mode != "manual" and selected_status not in {"ready", "failed"}:
        raise FleetValidationError(
            f"L'etape '{normalized_requested_step_key}' n'est pas executable dans l'ordre courant (statut {selected_status})."
        )
    return selected_step


def _workflow_progress_snapshot(steps: list[dict[str, Any]]) -> dict[str, Any]:
    completed_steps = sum(1 for step in steps if step.get("status") == "succeeded")
    next_step = next((step for step in steps if step.get("status") in {"ready", "failed"}), None)
    return {
        "completed_steps": completed_steps,
        "total_steps": len(steps),
        "next_step_key": next_step.get("key") if next_step else None,
        "next_step_label": next_step.get("label") if next_step else None,
    }


def _auth_prototype_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _remote_unlock_broker_probe_ca_cert_path(*, settings: Settings) -> Path | None:
    configured_path = _clean_optional(settings.provisioning_remote_unlock_broker_probe_ca_cert_path)
    if configured_path is not None:
        return Path(configured_path).expanduser().resolve()

    default_path = (
        _auth_prototype_root()
        / "provisioning_ansible"
        / ".tmp"
        / "cascadya-remote-unlock"
        / "broker"
        / "ca.crt"
    ).resolve()
    if default_path.exists():
        return default_path
    return None


def _edge_agent_bundle_ca_cert_path(bundle_dir: Path) -> Path:
    nats_server_ca_path = (bundle_dir / "nats-ca.crt").resolve()
    if nats_server_ca_path.exists():
        return nats_server_ca_path
    return (bundle_dir / "ca.crt").resolve()


def build_edge_agent_e2e_probe_context(
    asset: InventoryAsset,
    *,
    settings: Settings,
    site_id: int | None = None,
) -> dict[str, Any]:
    if asset.site is None:
        raise FleetValidationError("Associe d'abord cet IPC a un site avant de lancer un test E2E.")
    if site_id is not None and asset.site_id != site_id:
        raise FleetValidationError("L'IPC selectionne n'appartient pas au site demande pour le test E2E.")
    if asset.asset_type != "industrial_pc":
        raise FleetValidationError("Le test E2E NATS ne supporte actuellement que les assets de type industrial_pc.")

    inventory_hostname = _clean_optional(asset.inventory_hostname) or _clean_optional(asset.hostname)
    if inventory_hostname is None:
        raise FleetValidationError("L'IPC doit avoir un inventory_hostname avant de lancer un test E2E.")

    edge_agent_vars = _build_edge_agent_vars_preview(asset, settings=settings)
    probe_nats_url = _clean_optional(str(edge_agent_vars.get("edge_agent_probe_nats_url") or ""))
    probe_broker_url = _clean_optional(str(edge_agent_vars.get("edge_agent_probe_broker_url") or ""))

    if probe_nats_url is not None:
        bundle_dir = (_auth_prototype_root() / "generated" / "cascadya-edge-agent" / inventory_hostname).resolve()
        ca_cert_path = _edge_agent_bundle_ca_cert_path(bundle_dir)
        cert_paths = {
            "ca_cert_path": ca_cert_path,
            "client_cert_path": bundle_dir / "client.crt",
            "client_key_path": bundle_dir / "client.key",
        }
        missing_files = [path.name for path in cert_paths.values() if not path.exists()]
        if missing_files:
            raise FleetValidationError(
                "Le bundle TLS edge-agent n'est pas complet sur le control plane pour cet IPC. "
                f"Fichiers manquants dans {bundle_dir}: {', '.join(missing_files)}."
            )

        return {
            "probe_mode": "direct_nats",
            "inventory_hostname": inventory_hostname,
            "site": _serialize_site_ref(asset.site),
            "asset": serialize_inventory_asset(asset),
            "nats_url": probe_nats_url,
            "ping_subject": str(edge_agent_vars["edge_agent_nats_ping_subject"]),
            "monitoring_url": _clean_optional(
                str(
                    edge_agent_vars.get("edge_agent_probe_monitoring_url")
                    or ""
                )
            ),
            "ca_cert_path": str(cert_paths["ca_cert_path"]),
            "client_cert_path": str(cert_paths["client_cert_path"]),
            "client_key_path": str(cert_paths["client_key_path"]),
            "bundle_dir": str(bundle_dir),
        }

    if probe_broker_url is not None:
        if settings.provisioning_remote_unlock_broker_probe_token is None:
            raise FleetValidationError(
                "Le broker expose bien un probe URL pour cet IPC, mais aucun token control-plane n'est configure "
                "cote serveur. Renseigne AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_PROBE_TOKEN."
            )
        broker_probe_ca_cert_path = _remote_unlock_broker_probe_ca_cert_path(settings=settings)
        if broker_probe_ca_cert_path is None:
            raise FleetValidationError(
                "Impossible de localiser le certificat CA du probe broker cote control-plane. "
                "Renseigne AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_PROBE_CA_CERT_PATH "
                "ou regenere le bundle broker sur le controller."
            )
        return {
            "probe_mode": "broker_proxy",
            "inventory_hostname": inventory_hostname,
            "site": _serialize_site_ref(asset.site),
            "asset": serialize_inventory_asset(asset),
            "broker_probe_url": probe_broker_url,
            "broker_probe_token": settings.provisioning_remote_unlock_broker_probe_token,
            "broker_probe_ca_cert_path": str(broker_probe_ca_cert_path),
            "ping_subject": str(edge_agent_vars["edge_agent_nats_ping_subject"]),
        }

    raise FleetValidationError(
        "Aucun probe control-plane n'est configure pour cet IPC. "
        "Renseigne edge_agent_probe_nats_url pour un acces direct, "
        "ou configure le broker control-plane probe pour exposer un endpoint HTTPS securise."
    )


def build_ems_light_e2e_probe_context(
    *,
    settings: Settings,
) -> dict[str, Any]:
    broker_probe_url = _clean_optional(settings.provisioning_remote_unlock_broker_probe_url_default)
    if broker_probe_url is None:
        raise FleetValidationError(
            "Aucun endpoint probe broker n'est configure pour le flux ems-light. "
            "Renseigne AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_PROBE_URL_DEFAULT."
        )

    if settings.provisioning_remote_unlock_broker_probe_token is None:
        raise FleetValidationError(
            "Le flux ems-light requiert le token du probe broker cote control-plane. "
            "Renseigne AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_PROBE_TOKEN."
        )

    broker_probe_ca_cert_path = _remote_unlock_broker_probe_ca_cert_path(settings=settings)
    if broker_probe_ca_cert_path is None:
        raise FleetValidationError(
            "Impossible de localiser le certificat CA du probe broker cote control-plane. "
            "Renseigne AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_PROBE_CA_CERT_PATH "
            "ou regenere le bundle broker sur le controller."
        )

    connection_name = _clean_optional(settings.e2e_ems_light_connection_name)
    if connection_name is None:
        raise FleetValidationError(
            "Le nom de connexion broker -> ems-light est vide. "
            "Renseigne AUTH_PROTO_E2E_EMS_LIGHT_CONNECTION_NAME."
        )

    return {
        "flow_key": "ems_light",
        "flow_label": "ems-light",
        "site": None,
        "asset": None,
        "broker_probe_url": broker_probe_url,
        "broker_probe_token": settings.provisioning_remote_unlock_broker_probe_token,
        "broker_probe_ca_cert_path": str(broker_probe_ca_cert_path),
        "connection_name": connection_name,
    }


def build_orders_probe_context(
    *,
    settings: Settings,
) -> dict[str, Any]:
    broker_probe_url = _clean_optional(settings.provisioning_remote_unlock_broker_probe_url_default)
    if broker_probe_url is None:
        raise FleetValidationError(
            "Aucun endpoint probe broker n'est configure pour le flux Orders. "
            "Renseigne AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_PROBE_URL_DEFAULT."
        )

    if settings.provisioning_remote_unlock_broker_probe_token is None:
        raise FleetValidationError(
            "Le flux Orders requiert le token du probe broker cote control-plane. "
            "Renseigne AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_PROBE_TOKEN."
        )

    broker_probe_ca_cert_path = _remote_unlock_broker_probe_ca_cert_path(settings=settings)
    if broker_probe_ca_cert_path is None:
        raise FleetValidationError(
            "Impossible de localiser le certificat CA du probe broker cote control-plane. "
            "Renseigne AUTH_PROTO_PROVISIONING_REMOTE_UNLOCK_BROKER_PROBE_CA_CERT_PATH "
            "ou regenere le bundle broker sur le controller."
        )

    return {
        "flow_key": "orders",
        "flow_label": "Orders broker feed",
        "broker_probe_url": broker_probe_url,
        "broker_probe_token": settings.provisioning_remote_unlock_broker_probe_token,
        "broker_probe_ca_cert_path": str(broker_probe_ca_cert_path),
    }


def _write_generated_artifact(relative_path: str, content: str) -> Path:
    auth_root = _auth_prototype_root().resolve()
    artifact_path = (auth_root / relative_path).resolve()
    if auth_root != artifact_path and auth_root not in artifact_path.parents:
        raise FleetValidationError(f"Generated artifact path escapes auth_prototype root: {relative_path}")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_content = content if content.endswith("\n") else f"{content}\n"
    artifact_path.write_text(normalized_content, encoding="utf-8")
    return artifact_path


def _cleanup_temporary_secret_artifact(path: Path | None, *, logs: list[str]) -> None:
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logs.append(
            f"{_utcnow().isoformat()} WARN impossible de supprimer le fichier temporaire de secrets "
            f"{path}: {exc.__class__.__name__}: {exc}"
        )


def _materialize_workflow_artifacts(context: dict[str, Any]) -> None:
    artifacts = context.get("artifacts")
    if not isinstance(artifacts, dict):
        return

    for bundle_name in ("edge_agent", "wazuh_agent", "ipc_alloy", "remote_unlock_broker", "remote_unlock"):
        bundle = artifacts.get(bundle_name)
        if not isinstance(bundle, dict):
            continue

        inventory_path = bundle.get("inventory_path")
        inventory_preview = bundle.get("inventory_preview")
        vars_path = bundle.get("vars_path")
        vars_preview = bundle.get("vars_preview")
        if not isinstance(inventory_path, str) or not isinstance(inventory_preview, str):
            continue
        if not isinstance(vars_path, str) or not isinstance(vars_preview, str):
            continue

        bundle["inventory_abspath"] = str(_write_generated_artifact(inventory_path, inventory_preview))
        bundle["vars_abspath"] = str(_write_generated_artifact(vars_path, vars_preview))


def _append_command_output(logs: list[str], *, stream: str, output: str | None, max_lines: int = 120) -> None:
    if not output:
        return
    lines = [line.rstrip() for line in output.splitlines() if line.strip()]
    if not lines:
        return
    if len(lines) > max_lines:
        omitted = len(lines) - max_lines
        logs.append(f"{_utcnow().isoformat()} INFO {stream} truncated to last {max_lines} lines ({omitted} line(s) omitted)")
        lines = lines[-max_lines:]
    logs.extend(f"{stream} {line}" for line in lines)


def _append_command_output_line(logs: list[str], *, stream: str, line: str | None) -> bool:
    if line is None:
        return False
    cleaned = line.rstrip()
    if not cleaned.strip():
        return False
    logs.append(f"{stream} {cleaned}")
    return True


def _persist_job_runtime_snapshot(
    session: Session,
    *,
    job: ProvisioningJob,
    context: dict[str, Any],
    workflow: dict[str, Any],
    steps: list[dict[str, Any]],
    logs: list[str],
) -> None:
    _apply_dispatch_mode_to_steps(steps, dispatch_mode=_workflow_dispatch_mode(context))
    workflow["steps"] = steps
    context["workflow"] = workflow
    context["progress"] = _workflow_progress_snapshot(steps)
    job.logs_json = list(logs)
    job.context_json = copy.deepcopy(context)
    session.commit()


def _spawn_command_output_reader(
    pipe: Any,
    *,
    stream: str,
    output_queue: "queue.Queue[tuple[str, str]]",
) -> threading.Thread:
    def _reader() -> None:
        if pipe is None:
            return
        try:
            for raw_line in iter(pipe.readline, ""):
                if raw_line == "":
                    break
                output_queue.put((stream, raw_line))
        finally:
            try:
                pipe.close()
            except Exception:
                pass

    thread = threading.Thread(
        target=_reader,
        name=f"provisioning-{stream.lower()}-reader",
        daemon=True,
    )
    thread.start()
    return thread


def _compact_command_preview(command_preview: str, *, max_length: int = MAX_COMMAND_PREVIEW_LENGTH) -> str:
    if len(command_preview) <= max_length:
        return command_preview
    marker = "\n... [command preview truncated, see workflow steps/context for full command]"
    available = max_length - len(marker)
    if available <= 0:
        return command_preview[:max_length]
    return f"{command_preview[:available]}{marker}"


def _persist_failed_step(
    session: Session,
    *,
    job: ProvisioningJob,
    context: dict[str, Any],
    workflow: dict[str, Any],
    steps: list[dict[str, Any]],
    current_step: dict[str, Any],
    logs: list[str],
    finished_at: datetime,
    error_message: str,
) -> ProvisioningJob:
    current_step["status"] = "failed"
    current_step["completed_at"] = finished_at.isoformat()
    current_step["error_message"] = error_message
    _apply_dispatch_mode_to_steps(steps, dispatch_mode=_workflow_dispatch_mode(context))
    job.status = "failed"
    job.finished_at = finished_at
    job.error_message = error_message
    logs.append(f"{finished_at.isoformat()} ERROR {error_message}")
    job.logs_json = logs
    workflow["steps"] = steps
    context["workflow"] = workflow
    context["progress"] = _workflow_progress_snapshot(steps)
    job.context_json = context
    _refresh_asset_registration_state(job.asset)
    session.commit()
    return get_provisioning_job(session, job.id)


def _build_step_secret_vars(
    step: dict[str, Any], *, settings: Settings, job: ProvisioningJob | None = None
) -> dict[str, Any]:
    scope = str(step.get("scope") or "")
    step_key = str(step.get("key") or "")
    secret_vars: dict[str, Any] = {}

    if step_key == EDGE_AGENT_GENERATE_CERTS_STEP_KEY:
        if not settings.provisioning_remote_unlock_broker_vault_token:
            raise FleetValidationError(
                "Le step de generation des certificats edge-agent requiert un token Vault configure cote control-panel."
            )
        secret_vars["edge_agent_vault_token"] = settings.provisioning_remote_unlock_broker_vault_token

    if step_key == EDGE_AGENT_NATS_ROUNDTRIP_STEP_KEY and settings.provisioning_remote_unlock_broker_probe_token:
        secret_vars["edge_agent_probe_broker_token"] = settings.provisioning_remote_unlock_broker_probe_token

    if step_key == WAZUH_AGENT_DEPLOY_STEP_KEY and settings.provisioning_wazuh_registration_password:
        secret_vars["wazuh_agent_registration_password"] = settings.provisioning_wazuh_registration_password

    if step_key == IPC_ALLOY_DEPLOY_STEP_KEY and settings.provisioning_ipc_alloy_mimir_password:
        secret_vars["ipc_alloy_mimir_basic_auth_password"] = settings.provisioning_ipc_alloy_mimir_password

    if scope not in {"ipc", "broker"}:
        return secret_vars

    if scope == "broker":
        ssh_key_path = settings.provisioning_remote_unlock_broker_ssh_key_path or settings.provisioning_ssh_key_path
        ssh_key_passphrase = settings.provisioning_remote_unlock_broker_ssh_key_passphrase
        if not settings.provisioning_remote_unlock_broker_ssh_key_path:
            ssh_key_passphrase = ssh_key_passphrase or settings.provisioning_ssh_key_passphrase
        ssh_password = settings.provisioning_remote_unlock_broker_ssh_password
        become_password = (
            settings.provisioning_remote_unlock_broker_become_password
            or settings.provisioning_remote_unlock_broker_ssh_password
        )
        missing_auth_is_error = False
        missing_auth_message = ""
        passphrase_message = (
            "Les cles SSH du broker remote-unlock protegees par passphrase ne sont pas encore supportees "
            "par le runner non interactif."
        )
    else:
        ssh_key_path = settings.provisioning_ssh_key_path
        ssh_key_passphrase = settings.provisioning_ssh_key_passphrase
        ssh_password = settings.provisioning_ssh_password
        become_password = settings.provisioning_become_password or settings.provisioning_ssh_password
        missing_auth_is_error = True
        missing_auth_message = (
            "Aucun secret SSH de provisioning n'est configure. Renseigne AUTH_PROTO_PROVISIONING_SSH_KEY_PATH "
            "ou AUTH_PROTO_PROVISIONING_SSH_PASSWORD sur la VM control-panel."
        )
        passphrase_message = (
            "Les cles SSH protegees par passphrase ne sont pas encore supportees par le runner non interactif. "
            "Utilise une cle de deploiement dediee sans passphrase sur la VM, ou configure un mot de passe SSH stocke cote serveur."
        )

    if ssh_key_passphrase:
        raise FleetValidationError(
            passphrase_message
        )

    if ssh_password:
        secret_vars["ansible_password"] = ssh_password
    if become_password:
        secret_vars["ansible_become_password"] = become_password

    if scope == "broker" and settings.provisioning_remote_unlock_broker_vault_token:
        secret_vars["remote_unlock_broker_vault_token"] = settings.provisioning_remote_unlock_broker_vault_token

    if scope == "broker" and settings.provisioning_remote_unlock_broker_probe_token:
        secret_vars["remote_unlock_broker_control_plane_probe_token"] = (
            settings.provisioning_remote_unlock_broker_probe_token
        )

    if step_key == REMOTE_UNLOCK_SEED_VAULT_STEP_KEY:
        job_secret_vars = job.secret_vars_json if job and isinstance(job.secret_vars_json, dict) else {}
        remote_unlock_vault_secret_value = _clean_optional(
            str(job_secret_vars.get("remote_unlock_vault_secret_value"))
        )
        if remote_unlock_vault_secret_value is None:
            raise FleetValidationError(
                "Le step de seeding Vault requiert un secret LUKS fourni par l'operateur. "
                "Prepare un nouveau job avec remote_unlock_vault_secret_value."
            )
        secret_vars["remote_unlock_vault_secret_value"] = remote_unlock_vault_secret_value
        secret_vars["remote_unlock_vault_secret_force"] = bool(job_secret_vars.get("remote_unlock_vault_secret_force"))

    if ssh_key_path:
        secret_vars["ansible_ssh_private_key_file"] = ssh_key_path

    if missing_auth_is_error and not ssh_key_path and "ansible_password" not in secret_vars:
        raise FleetValidationError(missing_auth_message)

    return secret_vars


def _resolve_step_artifact_paths(step: dict[str, Any], context: dict[str, Any]) -> tuple[Path, Path, Path]:
    auth_root = _auth_prototype_root().resolve()
    artifacts = context.get("artifacts") if isinstance(context.get("artifacts"), dict) else {}

    inventory_kind = str(step.get("inventory_kind") or "")
    if inventory_kind not in {"remote_unlock", "remote_unlock_broker", "edge_agent", "wazuh_agent", "ipc_alloy"}:
        raise FleetValidationError(
            f"Le step courant reference un type d'inventory inconnu: {inventory_kind or 'missing'}."
        )
    bundle = artifacts.get(inventory_kind) if isinstance(artifacts, dict) else None
    if not isinstance(bundle, dict):
        raise FleetValidationError(f"Le bundle d'artefacts {inventory_kind} est introuvable dans le job.")

    inventory_raw = bundle.get("inventory_abspath") or bundle.get("inventory_path")
    vars_raw = bundle.get("vars_abspath") or bundle.get("vars_path")
    playbook_raw = step.get("playbook_path")

    if not isinstance(inventory_raw, str) or not isinstance(vars_raw, str) or not isinstance(playbook_raw, str):
        raise FleetValidationError("Le job ne contient pas les chemins d'execution Ansible attendus.")

    inventory_path = Path(inventory_raw).expanduser()
    vars_path = Path(vars_raw).expanduser()
    playbook_path = Path(playbook_raw).expanduser()

    if not inventory_path.is_absolute():
        inventory_path = (auth_root / inventory_path).resolve()
    if not vars_path.is_absolute():
        vars_path = (auth_root / vars_path).resolve()

    return inventory_path, vars_path, playbook_path


def _serialize_job_context(job: ProvisioningJob) -> dict[str, Any]:
    context = copy.deepcopy(job.context_json) if isinstance(job.context_json, dict) else {}
    workflow = context.get("workflow") if isinstance(context.get("workflow"), dict) else None
    raw_steps = workflow.get("steps") if workflow and isinstance(workflow.get("steps"), list) else []
    steps = [step for step in raw_steps if isinstance(step, dict)]

    if not workflow or not steps:
        return context

    if job.status == "succeeded":
        completed_at = job.finished_at.isoformat() if job.finished_at else None
        for step in steps:
            step["status"] = "succeeded"
            step["error_message"] = None
            if completed_at and step.get("started_at") is None:
                step["started_at"] = completed_at
            if completed_at and step.get("completed_at") is None:
                step["completed_at"] = completed_at
    elif job.status in {"prepared", "running", "failed"}:
        _apply_dispatch_mode_to_steps(steps, dispatch_mode=_workflow_dispatch_mode(context))

    context["progress"] = _workflow_progress_snapshot(steps)
    return context


def _supersede_active_jobs(asset: InventoryAsset, *, settings: Settings) -> list[ProvisioningJob]:
    active_jobs = [job for job in asset.provisioning_jobs if job.status in {"prepared", "running"}]
    if not active_jobs:
        return []

    if settings.provisioning_execution_mode != "mock":
        running_job = next((job for job in active_jobs if job.status == "running"), None)
        if running_job is not None:
            raise FleetValidationError(
                f"Un job de provisioning reel est deja en cours pour cet IPC (job #{running_job.id}). "
                "Attends sa fin avant de relancer un cycle complet."
            )

    closed_at = _utcnow()
    for job in active_jobs:
        logs = list(job.logs_json or [])
        logs.append(f"{closed_at.isoformat()} INFO superseded by a new provisioning cycle request")
        job.logs_json = logs
        job.status = "superseded"
        job.finished_at = closed_at
        job.error_message = None

        context = copy.deepcopy(job.context_json) if isinstance(job.context_json, dict) else {}
        workflow = context.get("workflow") if isinstance(context.get("workflow"), dict) else None
        raw_steps = workflow.get("steps") if workflow and isinstance(workflow.get("steps"), list) else []
        steps = [step for step in raw_steps if isinstance(step, dict)]
        if not steps:
            continue

        for step in steps:
            status = str(step.get("status") or "")
            if status == "running":
                step["completed_at"] = step.get("completed_at") or closed_at.isoformat()
            if status != "succeeded":
                step["status"] = "locked"
                step["error_message"] = None

        context["progress"] = {
            "completed_steps": sum(1 for step in steps if step.get("status") == "succeeded"),
            "total_steps": len(steps),
            "next_step_key": None,
            "next_step_label": None,
        }
        job.context_json = context

    return active_jobs


def _serialize_site_ref(site: Site | None) -> dict[str, Any] | None:
    if site is None:
        return None
    return {"id": site.id, "code": site.code, "name": site.name}


def _serialize_scan_ref(scan: InventoryScan | None) -> dict[str, Any] | None:
    if scan is None:
        return None
    return {
        "id": scan.id,
        "status": scan.status,
        "target_ip": scan.target_ip,
        "created_at": scan.created_at.isoformat(),
        "finished_at": scan.finished_at.isoformat() if scan.finished_at else None,
    }


def _serialize_job_ref(job: ProvisioningJob | None) -> dict[str, Any] | None:
    if job is None:
        return None
    return {
        "id": job.id,
        "status": job.status,
        "playbook_name": job.playbook_name,
        "created_at": job.created_at.isoformat(),
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


def serialize_site(site: Site) -> dict[str, Any]:
    last_scan = max(site.scans, key=lambda item: item.created_at, default=None)
    last_job = max(site.provisioning_jobs, key=lambda item: item.created_at, default=None)
    active_assets = sum(1 for asset in site.assets if asset.registration_status == "active")
    status = "inactive"
    if site.is_active:
        status = "active"
    if any(job.status in {"prepared", "running"} for job in site.provisioning_jobs):
        status = "provisioning"

    return {
        "id": site.id,
        "code": site.code,
        "name": site.name,
        "customer_name": site.customer_name,
        "country": site.country,
        "city": site.city,
        "timezone": site.timezone,
        "address_line1": site.address_line1,
        "notes": site.notes,
        "is_active": site.is_active,
        "status": status,
        "asset_count": len(site.assets),
        "active_asset_count": active_assets,
        "last_scan": _serialize_scan_ref(last_scan),
        "last_job": _serialize_job_ref(last_job),
        "created_at": site.created_at.isoformat(),
        "updated_at": site.updated_at.isoformat(),
    }


def serialize_inventory_asset(asset: InventoryAsset) -> dict[str, Any]:
    provisioning_vars = _clean_provisioning_vars(
        asset.provisioning_vars if isinstance(asset.provisioning_vars, dict) else {}
    )
    latest_job = max(asset.provisioning_jobs, key=lambda item: item.created_at, default=None)
    return {
        "id": asset.id,
        "site": _serialize_site_ref(asset.site),
        "discovered_by_scan_id": asset.discovered_by_scan_id,
        "asset_type": asset.asset_type,
        "registration_status": asset.registration_status,
        "hostname": asset.hostname,
        "inventory_hostname": asset.inventory_hostname,
        "naming_slug": asset.naming_slug,
        "ip_address": asset.ip_address,
        "management_ip": asset.management_ip,
        "teltonika_router_ip": asset.teltonika_router_ip,
        "mac_address": asset.mac_address,
        "serial_number": asset.serial_number,
        "vendor": asset.vendor,
        "model": asset.model,
        "firmware_version": asset.firmware_version,
        "status": asset.status,
        "source": asset.source,
        "management_interface": asset.management_interface,
        "uplink_interface": asset.uplink_interface,
        "gateway_ip": asset.gateway_ip,
        "wireguard_address": asset.wireguard_address,
        "notes": asset.notes,
        "provisioning_vars": provisioning_vars,
        "first_seen_at": asset.first_seen_at.isoformat() if asset.first_seen_at else None,
        "last_seen_at": asset.last_seen_at.isoformat() if asset.last_seen_at else None,
        "latest_job": _serialize_job_ref(latest_job),
        "created_at": asset.created_at.isoformat(),
        "updated_at": asset.updated_at.isoformat(),
    }


def serialize_inventory_scan(scan: InventoryScan) -> dict[str, Any]:
    return {
        "id": scan.id,
        "site": _serialize_site_ref(scan.site),
        "requested_by_user_id": scan.requested_by_user_id,
        "status": scan.status,
        "trigger_type": scan.trigger_type,
        "source": scan.source,
        "target_label": scan.target_label,
        "target_ip": scan.target_ip,
        "teltonika_router_ip": scan.teltonika_router_ip,
        "started_at": scan.started_at.isoformat() if scan.started_at else None,
        "finished_at": scan.finished_at.isoformat() if scan.finished_at else None,
        "summary": scan.summary_json or {},
        "error_message": scan.error_message,
        "discovered_assets": [
            {
                "id": asset.id,
                "hostname": asset.hostname,
                "inventory_hostname": asset.inventory_hostname,
                "management_ip": asset.management_ip,
                "mac_address": asset.mac_address,
                "registration_status": asset.registration_status,
            }
            for asset in scan.discovered_assets
        ],
        "created_at": scan.created_at.isoformat(),
        "updated_at": scan.updated_at.isoformat(),
    }


def serialize_provisioning_job(job: ProvisioningJob) -> dict[str, Any]:
    dispatch_mode = _workflow_dispatch_mode(job.context_json if isinstance(job.context_json, dict) else {})
    return {
        "id": job.id,
        "site": _serialize_site_ref(job.site),
        "asset_id": job.asset_id,
        "requested_by_user_id": job.requested_by_user_id,
        "status": job.status,
        "execution_mode": job.execution_mode,
        "dispatch_mode": dispatch_mode,
        "playbook_name": job.playbook_name,
        "inventory_group": job.inventory_group,
        "command_preview": job.command_preview,
        "context": _serialize_job_context(job),
        "logs": list(job.logs_json or []),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }


def cancel_provisioning_job(session: Session, job_id: int) -> ProvisioningJob:
    job = get_provisioning_job(session, job_id)
    if job.status in {"succeeded", "superseded", "cancelled"}:
        raise FleetValidationError(
            f"Le job #{job.id} est deja termine avec le statut '{job.status}' et ne peut plus etre abandonne."
        )

    cancelled_at = _utcnow()
    logs = list(job.logs_json or [])
    context = copy.deepcopy(job.context_json) if isinstance(job.context_json, dict) else {}
    workflow = context.get("workflow") if isinstance(context.get("workflow"), dict) else {}
    raw_steps = workflow.get("steps") if isinstance(workflow.get("steps"), list) else []
    steps = [step for step in raw_steps if isinstance(step, dict)]

    first_pending_step_marked = False
    for step in steps:
        status = str(step.get("status") or "locked")
        if status == "succeeded":
            continue
        if not first_pending_step_marked:
            step["status"] = "failed"
            step["completed_at"] = cancelled_at.isoformat()
            step["error_message"] = "Annule par l'operateur."
            first_pending_step_marked = True
            continue
        step["status"] = "locked"
        step["error_message"] = None

    _apply_dispatch_mode_to_steps(steps, dispatch_mode=_workflow_dispatch_mode(context))
    workflow["steps"] = steps
    context["workflow"] = workflow
    context["progress"] = _workflow_progress_snapshot(steps)

    job.status = "cancelled"
    job.finished_at = cancelled_at
    job.error_message = "Cycle abandonne par l'operateur."
    job.logs_json = [
        *logs,
        f"{cancelled_at.isoformat()} CANCEL job cancelled by operator",
        (
            f"{cancelled_at.isoformat()} INFO annulation logique uniquement: si un ansible-playbook tourne encore "
            "sur la VM, un redemarrage du service peut rester necessaire pour couper le process."
            if job.execution_mode == "real"
            else f"{cancelled_at.isoformat()} INFO job mock annule et retire de la file active"
        ),
    ]
    job.context_json = context

    _refresh_asset_registration_state(job.asset)
    session.commit()
    return get_provisioning_job(session, job.id)


def delete_provisioning_job(session: Session, job_id: int) -> dict[str, Any]:
    job = get_provisioning_job(session, job_id)
    if job.status == "running":
        raise FleetValidationError(
            f"Le job #{job.id} est encore marque 'running'. Abandonne-le d'abord avant de le supprimer de l'historique."
        )

    deleted_job_label = job.playbook_name
    deleted_job_status = job.status
    deleted_site_id = job.site_id
    deleted_asset_id = job.asset_id
    asset = job.asset
    should_refresh_asset_state = deleted_job_status != "succeeded"

    session.delete(job)
    session.flush()
    if should_refresh_asset_state:
        _refresh_asset_registration_state(asset)
    session.commit()
    return {
        "status": "ok",
        "deleted_job_id": job_id,
        "deleted_job_label": deleted_job_label,
        "deleted_job_status": deleted_job_status,
        "site_id": deleted_site_id,
        "asset_id": deleted_asset_id,
    }


def create_site(
    session: Session,
    *,
    code: str,
    name: str,
    customer_name: str | None,
    country: str | None,
    city: str | None,
    timezone_name: str | None,
    address_line1: str | None,
    notes: str | None,
    is_active: bool = True,
) -> Site:
    normalized_code = _normalize_site_code(code)
    if session.scalar(select(Site).where(Site.code == normalized_code)) is not None:
        raise FleetValidationError(f"Le code site {normalized_code} existe deja.")

    site = Site(
        code=normalized_code,
        name=_clean_required(name, "site_name"),
        customer_name=_clean_optional(customer_name) or "",
        country=_clean_optional(country) or "FR",
        city=_clean_optional(city) or "",
        timezone=_clean_optional(timezone_name) or "Europe/Paris",
        address_line1=_clean_optional(address_line1) or "",
        notes=_clean_optional(notes) or "",
        is_active=is_active,
    )
    session.add(site)
    session.commit()
    return get_site(session, site.id)


def update_site(
    session: Session,
    site_id: int,
    *,
    code: str,
    name: str,
    customer_name: str | None,
    country: str | None,
    city: str | None,
    timezone_name: str | None,
    address_line1: str | None,
    notes: str | None,
    is_active: bool,
) -> Site:
    site = get_site(session, site_id)
    normalized_code = _normalize_site_code(code)
    existing = session.scalar(select(Site).where(Site.code == normalized_code))
    if existing is not None and existing.id != site.id:
        raise FleetValidationError(f"Le code site {normalized_code} existe deja.")

    site.code = normalized_code
    site.name = _clean_required(name, "site_name")
    site.customer_name = _clean_optional(customer_name) or ""
    site.country = _clean_optional(country) or "FR"
    site.city = _clean_optional(city) or ""
    site.timezone = _clean_optional(timezone_name) or "Europe/Paris"
    site.address_line1 = _clean_optional(address_line1) or ""
    site.notes = _clean_optional(notes) or ""
    site.is_active = is_active
    session.commit()
    return get_site(session, site.id)


def set_site_active(session: Session, site_id: int, *, is_active: bool) -> Site:
    site = get_site(session, site_id)
    site.is_active = is_active
    session.commit()
    return get_site(session, site.id)


def request_inventory_scan(
    session: Session,
    *,
    settings: Settings,
    requested_by_user_id: int | None,
    site_id: int | None,
    target_ip: str,
    teltonika_router_ip: str | None,
    target_label: str | None,
    ssh_username: str | None = None,
    ssh_port: int | None = None,
    downstream_probe_ip: str | None = None,
    asset_type: str = "industrial_pc",
) -> tuple[InventoryScan, InventoryAsset]:
    normalized_target_ip = _normalize_ip(target_ip, field_name="target_ip")
    assert normalized_target_ip is not None
    normalized_router_ip = _normalize_ip(teltonika_router_ip, field_name="teltonika_router_ip")
    site = get_site(session, site_id) if site_id is not None else None
    started_at = _utcnow()
    scan = InventoryScan(
        site=site,
        requested_by_user_id=requested_by_user_id,
        status="running",
        trigger_type="manual",
        source="scan",
        target_label=_clean_optional(target_label) or f"Scan {normalized_target_ip}",
        target_ip=normalized_target_ip,
        teltonika_router_ip=normalized_router_ip,
        started_at=started_at,
    )

    try:
        discovery = _probe_inventory_target(
            settings=settings,
            target_ip=normalized_target_ip,
            teltonika_router_ip=normalized_router_ip,
            ssh_username=ssh_username,
            ssh_port=ssh_port,
            downstream_probe_ip=downstream_probe_ip,
        )
    except FleetValidationError as exc:
        now = _utcnow()
        scan.status = "failed"
        scan.finished_at = now
        scan.error_message = str(exc)
        scan.summary_json = {
            "probe_mode": "failed",
            "entrypoint_ip": normalized_target_ip,
            "teltonika_router_ip": normalized_router_ip,
            "requested_at": started_at.isoformat(),
        }
        session.add(scan)
        session.commit()
        raise

    session.add(scan)
    session.flush()

    mac_address = _clean_optional(discovery.get("mac_address"))
    if mac_address:
        existing_asset = session.scalar(
            _asset_query().where(
                (InventoryAsset.management_ip == normalized_target_ip)
                | (InventoryAsset.mac_address == mac_address)
            )
        )
    else:
        existing_asset = session.scalar(_asset_query().where(InventoryAsset.management_ip == normalized_target_ip))

    now = _utcnow()
    asset = existing_asset or InventoryAsset(
        asset_type=asset_type,
        source="scan",
        registration_status="discovered",
        first_seen_at=now,
    )
    if existing_asset is None:
        session.add(asset)

    default_vars = discovery["provisioning_vars"] if isinstance(discovery.get("provisioning_vars"), dict) else {}
    asset.site = site or asset.site
    asset.discovered_by_scan = scan
    asset.asset_type = asset_type
    asset.hostname = asset.hostname or _clean_optional(discovery.get("hostname"))
    asset.inventory_hostname = asset.inventory_hostname or _clean_optional(discovery.get("inventory_hostname"))
    asset.naming_slug = asset.naming_slug or _slugify(asset.hostname or asset.inventory_hostname or normalized_target_ip)
    asset.ip_address = normalized_target_ip
    asset.management_ip = normalized_target_ip
    asset.teltonika_router_ip = normalized_router_ip
    asset.mac_address = asset.mac_address or mac_address
    asset.serial_number = asset.serial_number or _clean_optional(discovery.get("serial_number"))
    asset.vendor = asset.vendor or _clean_optional(discovery.get("vendor"))
    asset.model = asset.model or _clean_optional(discovery.get("model"))
    asset.status = _clean_optional(discovery.get("status")) or "warning"
    asset.source = "scan"
    asset.management_interface = asset.management_interface or _clean_optional(discovery.get("management_interface"))
    asset.uplink_interface = asset.uplink_interface or _clean_optional(discovery.get("uplink_interface"))
    asset.gateway_ip = asset.gateway_ip or _clean_optional(discovery.get("gateway_ip")) or (
        normalized_router_ip or _default_gateway_for_ip(normalized_target_ip)
    )
    asset.wireguard_address = asset.wireguard_address or _clean_optional(discovery.get("wireguard_address"))
    asset.provisioning_vars = {**default_vars, **(asset.provisioning_vars or {})}
    asset.last_seen_at = now
    if existing_asset is None:
        session.flush()

    scan.status = "succeeded"
    scan.source = _clean_optional(discovery.get("probe_mode")) or "scan"
    scan.finished_at = now
    scan.summary_json = {
        **(discovery.get("summary") or {}),
        "candidate_count": 1,
        "candidate_ids": [asset.id],
    }
    session.commit()
    return get_inventory_scan(session, scan.id), get_inventory_asset(session, asset.id)


def _resolve_site_for_registration(
    session: Session,
    *,
    site_id: int | None,
    site_code: str | None,
    site_name: str | None,
    customer_name: str | None,
    country: str | None,
    city: str | None,
    timezone_name: str | None,
    address_line1: str | None,
    site_notes: str | None,
) -> Site:
    if site_id is not None:
        return get_site(session, site_id)

    normalized_code = _normalize_site_code(site_code or _slugify(_clean_required(site_name, "site_name")))
    existing = session.scalar(_site_query().where(Site.code == normalized_code))
    if existing is not None:
        existing.name = _clean_required(site_name or existing.name, "site_name")
        existing.customer_name = _clean_optional(customer_name) or existing.customer_name
        existing.country = _clean_optional(country) or existing.country
        existing.city = _clean_optional(city) or existing.city
        existing.timezone = _clean_optional(timezone_name) or existing.timezone
        existing.address_line1 = _clean_optional(address_line1) or existing.address_line1
        existing.notes = _clean_optional(site_notes) or existing.notes
        session.flush()
        return existing

    site = Site(
        code=normalized_code,
        name=_clean_required(site_name, "site_name"),
        customer_name=_clean_optional(customer_name) or "",
        country=_clean_optional(country) or "FR",
        city=_clean_optional(city) or "",
        timezone=_clean_optional(timezone_name) or "Europe/Paris",
        address_line1=_clean_optional(address_line1) or "",
        notes=_clean_optional(site_notes) or "",
        is_active=True,
    )
    session.add(site)
    session.flush()
    return site


def register_inventory_asset(
    session: Session,
    *,
    settings: Settings,
    asset_id: int,
    site_id: int | None,
    site_code: str | None,
    site_name: str | None,
    customer_name: str | None,
    country: str | None,
    city: str | None,
    timezone_name: str | None,
    address_line1: str | None,
    site_notes: str | None,
    hostname: str,
    inventory_hostname: str,
    naming_slug: str | None,
    management_ip: str | None,
    teltonika_router_ip: str | None,
    management_interface: str | None,
    uplink_interface: str | None,
    gateway_ip: str | None,
    wireguard_address: str | None,
    notes: str | None,
    provisioning_vars: dict[str, str] | None,
) -> InventoryAsset:
    asset = get_inventory_asset(session, asset_id)
    site = _resolve_site_for_registration(
        session,
        site_id=site_id,
        site_code=site_code,
        site_name=site_name,
        customer_name=customer_name,
        country=country,
        city=city,
        timezone_name=timezone_name,
        address_line1=address_line1,
        site_notes=site_notes,
    )

    normalized_hostname = _normalize_hostname(hostname, field_name="hostname")
    normalized_inventory_hostname = _normalize_hostname(inventory_hostname, field_name="inventory_hostname")
    normalized_management_ip = _normalize_ip(management_ip or asset.management_ip, field_name="management_ip")
    normalized_router_ip = _normalize_ip(
        teltonika_router_ip or asset.teltonika_router_ip,
        field_name="teltonika_router_ip",
    )
    normalized_gateway_ip = _normalize_ip(
        gateway_ip or asset.gateway_ip or (normalized_management_ip and _default_gateway_for_ip(normalized_management_ip)),
        field_name="gateway_ip",
    )
    normalized_wg_address = _clean_optional(wireguard_address) or asset.wireguard_address
    normalized_slug = _slugify(naming_slug or normalized_hostname)
    cleaned_provisioning_vars = _clean_provisioning_vars(provisioning_vars)
    merged_vars = {
        **_default_provisioning_vars(
            management_interface=_clean_optional(management_interface) or asset.management_interface,
            uplink_interface=_clean_optional(uplink_interface) or asset.uplink_interface,
        ),
        **(asset.provisioning_vars or {}),
        **cleaned_provisioning_vars,
    }

    asset.site = site
    asset.hostname = normalized_hostname
    asset.inventory_hostname = normalized_inventory_hostname
    asset.naming_slug = normalized_slug
    asset.ip_address = normalized_management_ip
    asset.management_ip = normalized_management_ip
    asset.teltonika_router_ip = normalized_router_ip
    asset.management_interface = _clean_optional(management_interface) or asset.management_interface
    asset.uplink_interface = _clean_optional(uplink_interface) or asset.uplink_interface
    asset.gateway_ip = normalized_gateway_ip
    asset.wireguard_address = normalized_wg_address
    asset.notes = _clean_optional(notes) or asset.notes
    asset.provisioning_vars = merged_vars
    _ensure_asset_runtime_provisioning_vars(asset, settings=settings)
    asset.registration_status = "registered"
    asset.status = "warning" if asset.status == "unknown" else asset.status
    asset.last_seen_at = _utcnow()
    if asset.first_seen_at is None:
        asset.first_seen_at = asset.last_seen_at

    session.commit()
    return get_inventory_asset(session, asset.id)


def prepare_provisioning_job(
    session: Session,
    *,
    settings: Settings,
    requested_by_user_id: int | None,
    asset_id: int,
    playbook_name: str,
    inventory_group: str,
    workflow_key: str | None = None,
    dispatch_mode: str = "auto",
    remote_unlock_vault_secret_value: str | None = None,
    remote_unlock_vault_secret_confirm_overwrite: bool = False,
) -> ProvisioningJob:
    asset = get_inventory_asset(session, asset_id)
    if asset.site is None:
        raise FleetValidationError("Associe d'abord cet IPC a un site avant de preparer un job.")
    _ensure_asset_runtime_provisioning_vars(asset, settings=settings)
    superseded_jobs = _supersede_active_jobs(asset, settings=settings)
    effective_workflow_key = _clean_optional(workflow_key) or _clean_optional(playbook_name) or DEFAULT_PROVISIONING_WORKFLOW_KEY
    normalized_dispatch_mode = _normalize_dispatch_mode(dispatch_mode)
    workflow_context = _build_workflow_context(
        asset,
        settings=settings,
        workflow_key=effective_workflow_key,
        inventory_group=inventory_group,
        dispatch_mode=normalized_dispatch_mode,
    )
    if settings.provisioning_execution_mode == "real" and not workflow_context["ready_for_real_execution"]:
        reasons = [
            reason
            for reason in (workflow_context.get("runner", {}) or {}).get("readiness_reasons", [])
            if isinstance(reason, str) and reason
        ]
        raise FleetValidationError(
            "Provisioning reel non pret pour cet IPC. "
            + (" ".join(reasons) if reasons else "Complete d'abord la configuration requise.")
        )
    workflow_steps = workflow_context["workflow"]["steps"]
    job_secret_vars: dict[str, Any] | None = None
    if _workflow_contains_playbook(workflow_steps, REMOTE_UNLOCK_SEED_VAULT_PLAYBOOK):
        vault_secret_value = _clean_optional(remote_unlock_vault_secret_value)
        if vault_secret_value is None:
            raise FleetValidationError(
                "Ce workflow requiert le secret LUKS a publier dans Vault. "
                "Renseigne remote_unlock_vault_secret_value avant de lancer le provisioning."
            )
        job_secret_vars = {
            "remote_unlock_vault_secret_value": vault_secret_value,
            "remote_unlock_vault_secret_force": bool(remote_unlock_vault_secret_confirm_overwrite),
        }
    command_preview = _compact_command_preview("\n".join(step["command"] for step in workflow_steps))
    workflow_context["progress"] = _workflow_progress_snapshot(workflow_steps)
    context_json = {
        "site": _serialize_site_ref(asset.site),
        "asset": serialize_inventory_asset(asset),
        **workflow_context,
    }
    _materialize_workflow_artifacts(context_json)
    artifact_log_lines = _workflow_artifact_log_lines(context_json)
    job = ProvisioningJob(
        site=asset.site,
        asset=asset,
        requested_by_user_id=requested_by_user_id,
        status="prepared",
        execution_mode=settings.provisioning_execution_mode,
        playbook_name=effective_workflow_key,
        inventory_group=inventory_group,
        command_preview=command_preview,
        context_json=context_json,
        secret_vars_json=job_secret_vars,
        logs_json=[
            "Job prepared from discovered IPC candidate.",
            f"Inventory hostname: {asset.inventory_hostname}",
            f"Workflow: {workflow_context['workflow']['label']}",
            f"Steps: {len(workflow_steps)}",
            f"Execution mode: {settings.provisioning_execution_mode}",
            f"Dispatch mode: {normalized_dispatch_mode}",
            *(
                [
                    "Vault seed mode: "
                    + (
                        "overwrite-confirmed"
                        if job_secret_vars and job_secret_vars.get("remote_unlock_vault_secret_force")
                        else "create-if-absent"
                    )
                ]
                if job_secret_vars
                else []
            ),
            f"Ready for real execution: {workflow_context['ready_for_real_execution']}",
            *[
                f"Readiness: {reason}"
                for reason in (workflow_context.get("runner", {}) or {}).get("readiness_reasons", [])
                if isinstance(reason, str) and reason
            ],
            *(
                [f"Previous active jobs superseded: {', '.join(str(job.id) for job in superseded_jobs)}"]
                if superseded_jobs
                else []
            ),
            *artifact_log_lines,
        ],
    )
    asset.registration_status = "provisioning"
    session.add(job)
    session.commit()
    return get_provisioning_job(session, job.id)


def run_provisioning_job(
    session: Session,
    *,
    job_id: int,
    settings: Settings,
    requested_step_key: str | None = None,
) -> ProvisioningJob:
    job = get_provisioning_job(session, job_id)
    if job.status not in {"prepared", "running", "failed"}:
        raise FleetValidationError("Seuls les jobs prepares, en cours ou en echec peuvent etre relances.")

    logs = list(job.logs_json or [])
    context, workflow, steps = _extract_workflow_steps(job)
    _materialize_workflow_artifacts(context)
    for artifact_line in _workflow_artifact_log_lines(context):
        if artifact_line not in logs:
            logs.append(artifact_line)
    dispatch_mode = _workflow_dispatch_mode(context)
    _apply_dispatch_mode_to_steps(steps, dispatch_mode=dispatch_mode)
    current_step = _select_runnable_workflow_step(
        steps,
        dispatch_mode=dispatch_mode,
        requested_step_key=requested_step_key,
    )
    if current_step is None:
        if all(step.get("status") == "succeeded" for step in steps):
            raise FleetValidationError("Ce workflow est deja termine.")
        raise FleetValidationError("Aucune etape executable n'est disponible pour ce workflow.")

    step_started_at = _utcnow()
    if job.started_at is None:
        job.started_at = step_started_at
        logs.append(
            f"{step_started_at.isoformat()} START provisioning workflow "
            f"({settings.provisioning_execution_mode}/{dispatch_mode})"
        )

    current_step["status"] = "running"
    current_step["started_at"] = step_started_at.isoformat()
    current_step["error_message"] = None
    current_step["completed_at"] = None
    job.status = "running"
    job.finished_at = None
    job.error_message = None
    logs.append(
        f"{step_started_at.isoformat()} START step {current_step.get('order', '?')}: "
        f"{current_step.get('playbook_name', 'unknown')} [{current_step.get('phase', 'n/a')}]"
    )
    _persist_job_runtime_snapshot(
        session,
        job=job,
        context=context,
        workflow=workflow,
        steps=steps,
        logs=logs,
    )

    finished_at: datetime
    if settings.provisioning_execution_mode == "mock":
        finished_at = _utcnow()
        current_step["status"] = "succeeded"
        current_step["completed_at"] = finished_at.isoformat()
        logs.append(
            f"{finished_at.isoformat()} OK step {current_step.get('order', '?')}: "
            f"{current_step.get('playbook_name', 'unknown')} [{current_step.get('phase', 'n/a')}] simulated"
        )
    else:
        if not settings.provisioning_playbook_root:
            raise FleetValidationError(
                "AUTH_PROTO_PROVISIONING_PLAYBOOK_ROOT n'est pas configure sur la VM control-panel. "
                "Impossible d'executer les playbooks reels."
            )

        ansible_playbook_bin = shutil.which("ansible-playbook")
        if not ansible_playbook_bin:
            raise FleetValidationError(
                "ansible-playbook est introuvable sur la VM control-panel. Installe ansible-core avant de relancer le cycle."
            )

        inventory_path, vars_path, playbook_path = _resolve_step_artifact_paths(current_step, context)
        if not inventory_path.exists():
            raise FleetValidationError(f"Inventory introuvable pour le step courant: {inventory_path}")
        if not vars_path.exists():
            raise FleetValidationError(f"Vars file introuvable pour le step courant: {vars_path}")
        if not playbook_path.exists():
            raise FleetValidationError(f"Playbook introuvable pour le step courant: {playbook_path}")

        secret_vars = _build_step_secret_vars(current_step, settings=settings, job=job)
        secret_vars_path: Path | None = None
        try:
            if secret_vars:
                secret_filename = _normalize_generated_filename(
                    job.asset.inventory_hostname if job.asset and job.asset.inventory_hostname else f"job-{job.id}",
                    f"job-{job.id}-{current_step.get('key', 'step')}-secrets",
                    "json",
                )
                secret_vars_path = _write_generated_artifact(
                    f"generated/{secret_filename}",
                    json.dumps(secret_vars, indent=2, ensure_ascii=True),
                )

            command = [ansible_playbook_bin, "-i", str(inventory_path), str(playbook_path), "--extra-vars", f"@{vars_path}"]
            if secret_vars_path is not None:
                command.extend(["--extra-vars", f"@{secret_vars_path}"])

            env = os.environ.copy()
            env["ANSIBLE_HOST_KEY_CHECKING"] = "False"
            ansible_config_path = _resolve_ansible_config_path(settings.provisioning_playbook_root)
            if ansible_config_path is not None:
                env["ANSIBLE_CONFIG"] = str(ansible_config_path)
                logs.append(f"{step_started_at.isoformat()} INFO ANSIBLE_CONFIG {ansible_config_path}")
            logged_command = _build_workflow_step_command(
                playbook_path=str(playbook_path),
                inventory_path=str(inventory_path),
                vars_path=str(vars_path),
                ansible_config_path=str(ansible_config_path) if ansible_config_path else None,
                scope=str(current_step.get("scope") or ""),
            )
            if secret_vars_path is not None:
                logged_command += f" --extra-vars {shlex.quote(f'@{secret_vars_path}')}"
            logs.append(f"{step_started_at.isoformat()} CMD {logged_command}")
            _persist_job_runtime_snapshot(
                session,
                job=job,
                context=context,
                workflow=workflow,
                steps=steps,
                logs=logs,
            )

            try:
                process = subprocess.Popen(
                    command,
                    cwd=settings.provisioning_playbook_root,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                )
            except OSError as exc:
                finished_at = _utcnow()
                error_message = (
                    f"Echec de lancement Ansible sur {current_step.get('playbook_name', 'unknown')}: "
                    f"{exc.__class__.__name__}: {exc}"
                )
                return _persist_failed_step(
                    session,
                    job=job,
                    context=context,
                    workflow=workflow,
                    steps=steps,
                    current_step=current_step,
                    logs=logs,
                    finished_at=finished_at,
                    error_message=error_message,
                )

            output_queue: "queue.Queue[tuple[str, str]]" = queue.Queue()
            stdout_reader = _spawn_command_output_reader(process.stdout, stream="STDOUT", output_queue=output_queue)
            stderr_reader = _spawn_command_output_reader(process.stderr, stream="STDERR", output_queue=output_queue)
            stream_deadline = time.monotonic() + float(settings.provisioning_step_timeout_seconds)
            last_flush_at = time.monotonic()
            pending_live_lines = 0
            timed_out = False

            while True:
                now = time.monotonic()
                if now >= stream_deadline and process.poll() is None:
                    timed_out = True
                    process.kill()

                try:
                    stream_name, raw_line = output_queue.get(timeout=0.25)
                    if _append_command_output_line(logs, stream=stream_name, line=raw_line):
                        pending_live_lines += 1
                except queue.Empty:
                    pass

                now = time.monotonic()
                if pending_live_lines > 0 and (pending_live_lines >= 10 or (now - last_flush_at) >= 1.0):
                    _persist_job_runtime_snapshot(
                        session,
                        job=job,
                        context=context,
                        workflow=workflow,
                        steps=steps,
                        logs=logs,
                    )
                    pending_live_lines = 0
                    last_flush_at = now

                process_finished = process.poll() is not None
                readers_alive = stdout_reader.is_alive() or stderr_reader.is_alive()
                if process_finished and not readers_alive and output_queue.empty():
                    break

            stdout_reader.join(timeout=1.0)
            stderr_reader.join(timeout=1.0)

            while not output_queue.empty():
                stream_name, raw_line = output_queue.get_nowait()
                if _append_command_output_line(logs, stream=stream_name, line=raw_line):
                    pending_live_lines += 1

            if pending_live_lines > 0:
                _persist_job_runtime_snapshot(
                    session,
                    job=job,
                    context=context,
                    workflow=workflow,
                    steps=steps,
                    logs=logs,
                )

            finished_at = _utcnow()

            if timed_out:
                error_message = (
                    f"Timeout apres {settings.provisioning_step_timeout_seconds}s sur {current_step.get('playbook_name', 'unknown')}."
                )
                return _persist_failed_step(
                    session,
                    job=job,
                    context=context,
                    workflow=workflow,
                    steps=steps,
                    current_step=current_step,
                    logs=logs,
                    finished_at=finished_at,
                    error_message=error_message,
                )

            if process.returncode != 0:
                error_message = (
                    f"Echec Ansible (code {process.returncode}) sur {current_step.get('playbook_name', 'unknown')}."
                )
                return _persist_failed_step(
                    session,
                    job=job,
                    context=context,
                    workflow=workflow,
                    steps=steps,
                    current_step=current_step,
                    logs=logs,
                    finished_at=finished_at,
                    error_message=error_message,
                )

            current_step["status"] = "succeeded"
            current_step["completed_at"] = finished_at.isoformat()
            current_step["error_message"] = None
            if str(current_step.get("key") or "") == REMOTE_UNLOCK_SEED_VAULT_STEP_KEY:
                job.secret_vars_json = None
            logs.append(
                f"{finished_at.isoformat()} OK step {current_step.get('order', '?')}: "
                f"{current_step.get('playbook_name', 'unknown')} [{current_step.get('phase', 'n/a')}] real"
            )
        finally:
            _cleanup_temporary_secret_artifact(secret_vars_path, logs=logs)

    _apply_dispatch_mode_to_steps(steps, dispatch_mode=dispatch_mode)
    progress = _workflow_progress_snapshot(steps)
    workflow["steps"] = steps
    context["workflow"] = workflow
    context["progress"] = progress
    logs.append(
        f"{finished_at.isoformat()} PROGRESS {progress['completed_steps']}/{progress['total_steps']} "
        f"next={progress['next_step_label'] or progress['next_step_key'] or 'done'}"
    )

    if progress["completed_steps"] == progress["total_steps"]:
        job.status = "succeeded"
        job.finished_at = finished_at
        job.error_message = None
        job.secret_vars_json = None
        logs.append(f"{finished_at.isoformat()} DONE provisioning finished ({settings.provisioning_execution_mode})")
        if job.asset is not None:
            job.asset.registration_status = "active"
            job.asset.status = "online"
            job.asset.last_seen_at = finished_at
    else:
        job.status = "running"
        job.finished_at = None
        job.error_message = None
        logs.append(
            f"{finished_at.isoformat()} INFO next step ready: {progress['next_step_label'] or progress['next_step_key']}"
        )

    job.logs_json = logs
    job.context_json = context
    _refresh_asset_registration_state(job.asset)
    session.commit()
    return get_provisioning_job(session, job.id)
