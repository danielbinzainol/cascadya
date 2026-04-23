#!/usr/bin/env python3
"""Demo broker for Cascadya remote unlock.

This is a lab helper for demonstrations. It proves the IPC-side flow:
- mTLS client connection
- challenge / response structure
- TPM quote material transport
- Vault-backed secret release

It does not cryptographically verify the TPM quote yet.
"""

from __future__ import annotations

import argparse
import base64
import http.server
import json
import os
import secrets
import ssl
import sys
import time
import urllib.error
import urllib.request
import uuid
from typing import Any


CHALLENGES: dict[str, dict[str, Any]] = {}


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


class DemoBrokerHandler(http.server.BaseHTTPRequestHandler):
    server_version = "CascadyaDemoBroker/1.0"

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

    def do_POST(self) -> None:  # noqa: N802
        try:
            payload = self._read_json()
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


def build_server(args: argparse.Namespace) -> http.server.ThreadingHTTPServer:
    server = http.server.ThreadingHTTPServer((args.listen_host, args.listen_port), DemoBrokerHandler)
    server.demo_args = args  # type: ignore[attr-defined]
    server.challenge_ttl_seconds = args.challenge_ttl_seconds  # type: ignore[attr-defined]

    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile=args.server_cert, keyfile=args.server_key)
    context.load_verify_locations(cafile=args.client_ca)
    context.verify_mode = ssl.CERT_REQUIRED
    server.socket = context.wrap_socket(server.socket, server_side=True)
    return server


def main() -> int:
    args = parse_args()
    if not args.vault_token:
        raise SystemExit("Set --vault-token or VAULT_TOKEN before starting the demo broker.")

    server = build_server(args)
    print(
        "[demo-broker] listening "
        f"https://{args.listen_host}:{args.listen_port} "
        f"vault={args.vault_addr} mount={args.vault_kv_mount}/{args.vault_kv_prefix}"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[demo-broker] stopping")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
