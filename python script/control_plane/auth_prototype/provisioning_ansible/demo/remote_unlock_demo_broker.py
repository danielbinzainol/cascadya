#!/usr/bin/env python3
"""Demo broker for Cascadya remote unlock.

This is a lab helper for demonstrations. It proves the IPC-side flow:
- mTLS client connection
- challenge / response structure
- TPM quote material transport
- Vault-backed secret release

It does not cryptographically verify the TPM quote yet.

It can also expose a dedicated control-plane probe HTTPS listener that lets the
dashboard trigger a broker-local NATS request/reply test without exposing raw
NATS or monitoring ports publicly.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
from collections import deque
from datetime import datetime, timezone
import http.server
import json
import os
import secrets
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from typing import Any
from urllib.parse import parse_qs, urlsplit

from nats_e2e import (
    NatsE2EProbeError,
    run_monitoring_connection_probe,
    run_nats_command_request,
    run_nats_request_reply_probe,
)


CHALLENGES: dict[str, dict[str, Any]] = {}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_optional(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _extract_first_non_empty(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        cleaned = _clean_optional(payload.get(key))
        if cleaned is not None:
            return cleaned
    return None


def _summarize_order_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "action": None,
            "order_id": None,
            "direction": None,
            "execute_at": None,
            "target": None,
        }

    return {
        "action": _extract_first_non_empty(payload, ("action", "type", "operation", "command")),
        "order_id": _safe_int(payload.get("order_id") if "order_id" in payload else payload.get("id")),
        "direction": _extract_first_non_empty(
            payload,
            ("side", "direction", "order_side", "market_side", "kind"),
        ),
        "execute_at": _extract_first_non_empty(payload, ("execute_at", "scheduled_at", "timestamp")),
        "target": _extract_first_non_empty(
            payload,
            ("asset_name", "inventory_hostname", "edge_instance_id", "site_code", "site_name", "target"),
        ),
    }


class BrokerOrderTap:
    def __init__(
        self,
        *,
        nats_url: str,
        ca_cert_path: str,
        client_cert_path: str,
        client_key_path: str,
        subject: str,
        max_items: int,
        timeout_seconds: float,
    ) -> None:
        self.nats_url = nats_url
        self.ca_cert_path = ca_cert_path
        self.client_cert_path = client_cert_path
        self.client_key_path = client_key_path
        self.subject = subject
        self.max_items = max(1, int(max_items))
        self.timeout_seconds = max(float(timeout_seconds), 1.0)

        self._entries: deque[dict[str, Any]] = deque(maxlen=self.max_items)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._connected = False
        self._last_error: str | None = None
        self._started_at = _utcnow_iso()
        self._last_message_at: str | None = None
        self._total_seen = 0

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._thread_main, name="broker-order-tap", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def join(self, timeout: float = 2.0) -> None:
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def snapshot(self, *, limit: int | None = None) -> dict[str, Any]:
        with self._lock:
            retained_entries = list(self._entries)
            if limit is not None:
                retained_entries = retained_entries[: max(1, int(limit))]
            warnings = []
            if self._last_error:
                warnings.append(self._last_error)
            return {
                "status": "ok",
                "subject": self.subject,
                "connected": self._connected,
                "started_at": self._started_at,
                "last_message_at": self._last_message_at,
                "total_seen": self._total_seen,
                "retained": len(self._entries),
                "max_items": self.max_items,
                "warnings": warnings,
                "orders": retained_entries,
            }

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._run())
        except Exception as exc:  # pragma: no cover - defensive thread error path
            with self._lock:
                self._connected = False
                self._last_error = f"broker_order_tap_crashed:{exc.__class__.__name__}:{exc}"

    async def _run(self) -> None:
        try:
            import nats
        except ModuleNotFoundError as exc:
            with self._lock:
                self._connected = False
                self._last_error = f"nats_dependency_missing:{exc}"
            return

        while not self._stop_event.is_set():
            nc = None
            try:
                tls_ctx = ssl.create_default_context(cafile=self.ca_cert_path)
                tls_ctx.load_cert_chain(self.client_cert_path, self.client_key_path)
                tls_ctx.check_hostname = False

                nc = await nats.connect(
                    self.nats_url,
                    tls=tls_ctx,
                    connect_timeout=self.timeout_seconds,
                    name=f"broker_order_tap:{uuid.uuid4().hex[:8]}",
                )

                with self._lock:
                    self._connected = True
                    self._last_error = None

                async def handle_message(msg: Any) -> None:
                    observed_at = _utcnow_iso()
                    payload_text = msg.data.decode("utf-8", errors="replace")
                    payload: Any
                    payload_is_json = False
                    try:
                        payload = json.loads(payload_text)
                        payload_is_json = True
                    except json.JSONDecodeError:
                        payload = payload_text

                    with self._lock:
                        self._total_seen += 1
                        entry = {
                            "sequence": self._total_seen,
                            "observed_at": observed_at,
                            "subject": msg.subject,
                            "reply_subject": _clean_optional(msg.reply),
                            "size_bytes": len(msg.data),
                            "payload": payload,
                            "payload_is_json": payload_is_json,
                            "summary": _summarize_order_payload(payload),
                        }
                        self._entries.appendleft(entry)
                        self._last_message_at = observed_at

                await nc.subscribe(self.subject, cb=handle_message)

                while not self._stop_event.is_set() and nc.is_connected:
                    await asyncio.sleep(1.0)
            except Exception as exc:
                with self._lock:
                    self._connected = False
                    self._last_error = f"broker_order_tap_error:{exc.__class__.__name__}:{exc}"
                if not self._stop_event.is_set():
                    await asyncio.sleep(2.0)
            finally:
                if nc is not None:
                    try:
                        await nc.close()
                    except Exception:
                        pass
                with self._lock:
                    if not self._stop_event.is_set():
                        self._connected = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a demo broker backed by Vault KV v2.")
    parser.add_argument("--listen-host", default="0.0.0.0")
    parser.add_argument("--listen-port", type=int, default=8443)
    parser.add_argument("--server-cert", required=True)
    parser.add_argument("--server-key", required=True)
    parser.add_argument("--client-ca", required=True)
    parser.add_argument("--vault-addr", required=True)
    parser.add_argument("--vault-token", default=os.environ.get("VAULT_TOKEN", ""))
    parser.add_argument("--vault-kv-mount", default="secret")
    parser.add_argument("--vault-kv-prefix", default="remote-unlock")
    parser.add_argument("--challenge-ttl-seconds", type=int, default=300)
    parser.add_argument("--control-plane-listen-host")
    parser.add_argument("--control-plane-listen-port", type=int)
    parser.add_argument("--control-plane-probe-token", default=os.environ.get("CONTROL_PLANE_PROBE_TOKEN", ""))
    parser.add_argument("--control-plane-probe-client-cert")
    parser.add_argument("--control-plane-probe-client-key")
    parser.add_argument("--control-plane-probe-ca-cert")
    parser.add_argument("--control-plane-probe-nats-url", default="tls://host.docker.internal:4222")
    parser.add_argument("--control-plane-probe-monitoring-url", default="http://host.docker.internal:8222")
    parser.add_argument("--control-plane-order-subject", default="cascadya.routing.command")
    parser.add_argument("--control-plane-order-max-items", type=int, default=200)
    parser.add_argument("--control-plane-probe-timeout-seconds", type=float, default=10.0)
    return parser.parse_args()


def vault_read_secret(args: argparse.Namespace, device_id: str) -> bytes:
    path = f"{args.vault_addr.rstrip('/')}/v1/{args.vault_kv_mount}/data/{args.vault_kv_prefix.strip('/')}/{device_id}"
    request = urllib.request.Request(path, headers={"X-Vault-Token": args.vault_token})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Vault returned HTTP {exc.code} for device_id={device_id}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Vault request failed: {exc}") from exc

    data = payload.get("data", {}).get("data", {})
    if "secret_b64" in data:
        return base64.b64decode(data["secret_b64"])
    if "secret" in data:
        return data["secret"].encode("utf-8")
    if "luks_passphrase" in data:
        return data["luks_passphrase"].encode("utf-8")
    raise RuntimeError(
        f"Vault secret for device_id={device_id} is missing one of: secret_b64, secret, luks_passphrase"
    )


def extract_peer_common_name(handler: http.server.BaseHTTPRequestHandler) -> str:
    peer = handler.connection.getpeercert()
    if not peer:
        return ""
    subject = peer.get("subject", [])
    for part in subject:
        for key, value in part:
            if key == "commonName":
                return value
    return ""


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class DemoBrokerHandler(http.server.BaseHTTPRequestHandler):
    server_version = "CascadyaDemoBroker/1.1"

    def _read_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length)
        return json.loads(raw.decode("utf-8"))

    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _log(self, message: str) -> None:
        sys.stdout.write(f"[demo-broker] {message}\n")
        sys.stdout.flush()

    def _is_control_plane_probe_server(self) -> bool:
        return bool(getattr(self.server, "control_plane_probe_server", False))

    def _require_probe_token(self) -> bool:
        expected_token = str(getattr(self.server, "control_plane_probe_token", "") or "")
        if not expected_token:
            self._write_json(503, {"error": "probe_not_configured"})
            return False

        authorization = str(self.headers.get("Authorization", "") or "")
        if authorization == f"Bearer {expected_token}":
            return True

        self._write_json(401, {"error": "invalid_probe_token"})
        return False

    def do_GET(self) -> None:  # noqa: N802
        try:
            parsed_path = urlsplit(self.path)
            if self._is_control_plane_probe_server() and parsed_path.path == "/healthz":
                self.handle_probe_healthz()
                return
            if self._is_control_plane_probe_server() and parsed_path.path == "/orders/live":
                self.handle_orders_live(parsed_path.query)
                return
            self._write_json(404, {"error": "unknown_path"})
        except Exception as exc:  # pragma: no cover - demo error path
            self._log(f"request failure on {self.path}: {exc}")
            self._write_json(500, {"error": "internal_error", "detail": str(exc)})

    def do_POST(self) -> None:  # noqa: N802
        try:
            payload = self._read_json()
            if self._is_control_plane_probe_server():
                if self.path == "/nats/e2e-probe":
                    self.handle_nats_e2e_probe(payload)
                    return
                if self.path == "/orders/dispatch":
                    self.handle_orders_dispatch(payload)
                    return
                self._write_json(404, {"error": "unknown_path"})
                return

            if self.path == "/challenge":
                self.handle_challenge(payload)
                return
            if self.path == "/unlock":
                self.handle_unlock(payload)
                return
            self._write_json(404, {"error": "unknown_path"})
        except Exception as exc:  # pragma: no cover - demo error path
            self._log(f"request failure on {self.path}: {exc}")
            self._write_json(500, {"error": "internal_error", "detail": str(exc)})

    def handle_probe_healthz(self) -> None:
        self._write_json(
            200,
            {
                "status": "ok",
                "service": "control_plane_probe",
                "nats_url": getattr(self.server, "control_plane_probe_nats_url", None),
                "monitoring_url": getattr(self.server, "control_plane_probe_monitoring_url", None),
            },
        )

    def handle_orders_live(self, query_string: str) -> None:
        if not self._require_probe_token():
            return

        order_tap = getattr(self.server, "control_plane_order_tap", None)
        if order_tap is None:
            self._write_json(503, {"error": "orders_probe_not_configured"})
            return

        params = parse_qs(query_string or "")
        limit = _safe_int((params.get("limit") or [None])[0])
        if limit is not None and limit <= 0:
            self._write_json(400, {"error": "invalid_limit"})
            return

        self._write_json(200, order_tap.snapshot(limit=limit))

    def handle_orders_dispatch(self, payload: dict[str, Any]) -> None:
        if not self._require_probe_token():
            return

        command_subject = str(payload.get("subject", "")).strip()
        command_payload = payload.get("command_payload")
        timeout_seconds = float(
            payload.get("timeout_seconds") or getattr(self.server, "control_plane_probe_timeout_seconds", 10.0)
        )

        if not command_subject:
            self._write_json(400, {"error": "missing_command_subject"})
            return
        if not isinstance(command_payload, dict):
            self._write_json(400, {"error": "invalid_command_payload"})
            return

        try:
            result = run_nats_command_request(
                nats_url=str(getattr(self.server, "control_plane_probe_nats_url")),
                command_subject=command_subject,
                command_payload=command_payload,
                ca_cert_path=str(getattr(self.server, "control_plane_probe_ca_cert_path")),
                client_cert_path=str(getattr(self.server, "control_plane_probe_client_cert_path")),
                client_key_path=str(getattr(self.server, "control_plane_probe_client_key_path")),
                timeout_seconds=timeout_seconds,
            )
        except NatsE2EProbeError as exc:
            self._log(f"control-plane command dispatch failed subject={command_subject}: {exc}")
            self._write_json(502, {"error": "dispatch_failed", "detail": str(exc)})
            return

        self._log(f"control-plane command dispatch succeeded subject={command_subject}")
        self._write_json(200, result)

    def handle_nats_e2e_probe(self, payload: dict[str, Any]) -> None:
        if not self._require_probe_token():
            return

        probe_kind = str(payload.get("probe_kind", "request_reply")).strip().lower()
        timeout_seconds = float(
            payload.get("timeout_seconds") or getattr(self.server, "control_plane_probe_timeout_seconds", 10.0)
        )

        if probe_kind == "monitoring_connection":
            connection_name = str(payload.get("connection_name", "")).strip()
            connection_label = str(payload.get("connection_label", "")).strip() or connection_name
            if not connection_name:
                self._write_json(400, {"error": "missing_connection_name"})
                return

            broker_proxy_received_at = _utcnow_iso()
            broker_proxy_started = time.perf_counter()
            try:
                result = run_monitoring_connection_probe(
                    connection_name=connection_name,
                    connection_label=connection_label,
                    monitoring_url=str(getattr(self.server, "control_plane_probe_monitoring_url")),
                    timeout_seconds=timeout_seconds,
                )
            except NatsE2EProbeError as exc:
                self._log(f"control-plane monitoring probe failed connection_name={connection_name}: {exc}")
                self._write_json(502, {"error": "probe_failed", "detail": str(exc)})
                return

            broker_proxy_handler_ms = round((time.perf_counter() - broker_proxy_started) * 1000.0, 3)
            broker_proxy_response_ready_at = _utcnow_iso()
            summary = result.get("summary")
            if isinstance(summary, dict):
                summary["broker_proxy_handler_ms"] = broker_proxy_handler_ms
                summary["broker_proxy_received_at"] = broker_proxy_received_at
                summary["broker_proxy_response_ready_at"] = broker_proxy_response_ready_at

            self._log(f"control-plane monitoring probe succeeded connection_name={connection_name}")
            self._write_json(200, result)
            return

        asset_name = str(payload.get("asset_name", "")).strip()
        ping_subject = str(payload.get("ping_subject", "")).strip()
        if not asset_name:
            self._write_json(400, {"error": "missing_asset_name"})
            return
        if not ping_subject:
            self._write_json(400, {"error": "missing_ping_subject"})
            return

        probe_value = _safe_int(payload.get("probe_value"))
        broker_proxy_received_at = _utcnow_iso()
        broker_proxy_started = time.perf_counter()

        try:
            result = run_nats_request_reply_probe(
                asset_name=asset_name,
                nats_url=str(getattr(self.server, "control_plane_probe_nats_url")),
                ping_subject=ping_subject,
                ca_cert_path=str(getattr(self.server, "control_plane_probe_ca_cert_path")),
                client_cert_path=str(getattr(self.server, "control_plane_probe_client_cert_path")),
                client_key_path=str(getattr(self.server, "control_plane_probe_client_key_path")),
                monitoring_url=str(getattr(self.server, "control_plane_probe_monitoring_url", "") or "") or None,
                timeout_seconds=timeout_seconds,
                probe_value=probe_value,
            )
        except NatsE2EProbeError as exc:
            self._log(f"control-plane probe failed asset_name={asset_name}: {exc}")
            self._write_json(502, {"error": "probe_failed", "detail": str(exc)})
            return

        broker_proxy_handler_ms = round((time.perf_counter() - broker_proxy_started) * 1000.0, 3)
        broker_proxy_response_ready_at = _utcnow_iso()
        summary = result.get("summary")
        if isinstance(summary, dict):
            summary["broker_proxy_handler_ms"] = broker_proxy_handler_ms
            summary["broker_proxy_received_at"] = broker_proxy_received_at
            summary["broker_proxy_response_ready_at"] = broker_proxy_response_ready_at

        self._log(f"control-plane probe succeeded asset_name={asset_name} subject={ping_subject}")
        self._write_json(200, result)

    def handle_challenge(self, payload: dict[str, Any]) -> None:
        device_id = str(payload.get("device_id", "")).strip()
        if not device_id:
            self._write_json(400, {"error": "missing_device_id"})
            return

        challenge_id = str(uuid.uuid4())
        nonce = secrets.token_urlsafe(32)
        CHALLENGES[challenge_id] = {
            "device_id": device_id,
            "nonce": nonce,
            "created_at": time.time(),
        }

        self._log(
            "challenge issued "
            f"device_id={device_id} cert_cn={extract_peer_common_name(self)!r} "
            f"gateway_mac={payload.get('gateway_mac', '')!r}"
        )
        self._write_json(200, {"challenge_id": challenge_id, "nonce": nonce})

    def handle_unlock(self, payload: dict[str, Any]) -> None:
        device_id = str(payload.get("device_id", "")).strip()
        challenge_id = str(payload.get("challenge_id", "")).strip()
        nonce = str(payload.get("nonce", "")).strip()

        required_fields = [
            "quote_b64",
            "signature_b64",
            "pcr_b64",
            "ak_pub_b64",
        ]
        missing = [field for field in required_fields if not str(payload.get(field, "")).strip()]
        if missing:
            self._write_json(400, {"error": "missing_fields", "fields": missing})
            return

        challenge = CHALLENGES.get(challenge_id)
        if not challenge:
            self._write_json(403, {"error": "unknown_challenge"})
            return

        if time.time() - float(challenge["created_at"]) > float(self.server.challenge_ttl_seconds):
            del CHALLENGES[challenge_id]
            self._write_json(403, {"error": "expired_challenge"})
            return

        if challenge["device_id"] != device_id or challenge["nonce"] != nonce:
            self._write_json(403, {"error": "challenge_mismatch"})
            return

        cert_cn = extract_peer_common_name(self)
        if cert_cn and cert_cn != device_id:
            self._write_json(403, {"error": "client_cert_cn_mismatch", "cert_cn": cert_cn})
            return

        secret = vault_read_secret(self.server.demo_args, device_id)
        del CHALLENGES[challenge_id]

        self._log(
            "unlock approved "
            f"device_id={device_id} cert_cn={cert_cn!r} "
            f"gateway_mac={payload.get('gateway_mac', '')!r}"
        )
        self._write_json(200, {"secret_b64": base64.b64encode(secret).decode("ascii")})

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


def build_unlock_server(args: argparse.Namespace) -> http.server.ThreadingHTTPServer:
    server = http.server.ThreadingHTTPServer((args.listen_host, args.listen_port), DemoBrokerHandler)
    server.demo_args = args  # type: ignore[attr-defined]
    server.challenge_ttl_seconds = args.challenge_ttl_seconds  # type: ignore[attr-defined]
    server.control_plane_probe_server = False  # type: ignore[attr-defined]

    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile=args.server_cert, keyfile=args.server_key)
    context.load_verify_locations(cafile=args.client_ca)
    context.verify_mode = ssl.CERT_REQUIRED
    server.socket = context.wrap_socket(server.socket, server_side=True)
    return server


def build_control_plane_probe_server(args: argparse.Namespace) -> http.server.ThreadingHTTPServer | None:
    if args.control_plane_listen_port is None:
        return None

    required_fields = {
        "--control-plane-listen-host": args.control_plane_listen_host,
        "--control-plane-probe-token": args.control_plane_probe_token,
        "--control-plane-probe-client-cert": args.control_plane_probe_client_cert,
        "--control-plane-probe-client-key": args.control_plane_probe_client_key,
        "--control-plane-probe-ca-cert": args.control_plane_probe_ca_cert,
    }
    missing = [option for option, value in required_fields.items() if not str(value or "").strip()]
    if missing:
        raise SystemExit(
            "The control-plane probe listener requires the following arguments: " + ", ".join(missing)
        )

    server = http.server.ThreadingHTTPServer(
        (str(args.control_plane_listen_host), int(args.control_plane_listen_port)),
        DemoBrokerHandler,
    )
    server.control_plane_probe_server = True  # type: ignore[attr-defined]
    server.control_plane_probe_token = args.control_plane_probe_token  # type: ignore[attr-defined]
    server.control_plane_probe_nats_url = args.control_plane_probe_nats_url  # type: ignore[attr-defined]
    server.control_plane_probe_monitoring_url = args.control_plane_probe_monitoring_url  # type: ignore[attr-defined]
    server.control_plane_probe_client_cert_path = args.control_plane_probe_client_cert  # type: ignore[attr-defined]
    server.control_plane_probe_client_key_path = args.control_plane_probe_client_key  # type: ignore[attr-defined]
    server.control_plane_probe_ca_cert_path = args.control_plane_probe_ca_cert  # type: ignore[attr-defined]
    server.control_plane_probe_timeout_seconds = args.control_plane_probe_timeout_seconds  # type: ignore[attr-defined]
    server.control_plane_order_tap = BrokerOrderTap(  # type: ignore[attr-defined]
        nats_url=str(args.control_plane_probe_nats_url),
        ca_cert_path=str(args.control_plane_probe_ca_cert),
        client_cert_path=str(args.control_plane_probe_client_cert),
        client_key_path=str(args.control_plane_probe_client_key),
        subject=str(args.control_plane_order_subject),
        max_items=int(args.control_plane_order_max_items),
        timeout_seconds=float(args.control_plane_probe_timeout_seconds),
    )
    server.control_plane_order_tap.start()  # type: ignore[attr-defined]

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=args.server_cert, keyfile=args.server_key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    return server


def _serve_in_background(server: http.server.ThreadingHTTPServer, *, label: str) -> threading.Thread:
    thread = threading.Thread(target=server.serve_forever, name=label, daemon=True)
    thread.start()
    return thread


def main() -> int:
    args = parse_args()
    if not args.vault_token:
        raise SystemExit("Set --vault-token or VAULT_TOKEN before starting the demo broker.")

    unlock_server = build_unlock_server(args)
    control_plane_probe_server = build_control_plane_probe_server(args)
    control_plane_probe_thread: threading.Thread | None = None

    print(
        "[demo-broker] listening "
        f"https://{args.listen_host}:{args.listen_port} "
        f"vault={args.vault_addr} mount={args.vault_kv_mount}/{args.vault_kv_prefix}"
    )
    if control_plane_probe_server is not None:
        control_plane_probe_thread = _serve_in_background(
            control_plane_probe_server,
            label="control-plane-probe-server",
        )
        print(
            "[demo-broker] control-plane probe listening "
            f"https://{args.control_plane_listen_host}:{args.control_plane_listen_port}"
        )
        print(
            "[demo-broker] orders tap enabled "
            f"subject={args.control_plane_order_subject} max_items={args.control_plane_order_max_items}"
        )

    try:
        unlock_server.serve_forever()
    except KeyboardInterrupt:
        print("[demo-broker] stopping")
    finally:
        unlock_server.shutdown()
        unlock_server.server_close()
        if control_plane_probe_server is not None:
            order_tap = getattr(control_plane_probe_server, "control_plane_order_tap", None)
            if order_tap is not None:
                order_tap.stop()
            control_plane_probe_server.shutdown()
            control_plane_probe_server.server_close()
            if order_tap is not None:
                order_tap.join(timeout=2)
        if control_plane_probe_thread is not None:
            control_plane_probe_thread.join(timeout=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
