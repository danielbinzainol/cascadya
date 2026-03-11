import os
from pathlib import Path

# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent


def _first_existing_path(candidates):
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    return None


def _resolve_cert_path(filename, explicit_env_var):
    """Find certificate/key files from env vars or known project locations."""
    env_file = os.getenv(explicit_env_var, "").strip()
    if env_file:
        path = Path(env_file).expanduser()
        if path.exists():
            return str(path)

    env_dir = os.getenv("STEAMSWITCH_CERTS_DIR", "").strip()
    env_dir_path = Path(env_dir).expanduser() if env_dir else None

    search_paths = [
        BASE_DIR / "config" / "certs" / filename,
        BASE_DIR.parent / "config" / "certs" / filename,
        BASE_DIR.parent / filename,
        BASE_DIR.parent.parent / filename,
        BASE_DIR.parent.parent / "config" / "certs" / filename,
    ]

    if env_dir_path:
        search_paths.insert(0, env_dir_path / filename)

    found = _first_existing_path(search_paths)
    if found:
        return str(found)

    # Keep default location for clear error reporting if file is still missing.
    return str(BASE_DIR / "config" / "certs" / filename)


# TLS certificates (auto-resolved)
CA_CERT = _resolve_cert_path("ca.crt", "STEAMSWITCH_CA_CERT")
CLIENT_CERT = _resolve_cert_path("client.crt", "STEAMSWITCH_CLIENT_CERT")
CLIENT_KEY = _resolve_cert_path("client.key", "STEAMSWITCH_CLIENT_KEY")

# NATS
NATS_URL = "tls://10.42.1.6:4222"
TOPIC_PING = "cascadya.routing.ping"
TOPIC_TELEMETRY = "cascadya.routing.telemetry"
TOPIC_COMMAND = "cascadya.routing.command"
COMMAND_TIMEOUT_SEC = 8.0

# Modbus-related constants (for display/use in UI)
REG_WATCHDOG = 620

# UI configuration
APP_TITLE = "SteamSwitch - Edge Control Center"
APP_GEOMETRY = "1050x760"
THEME_COLOR = "blue"
APPEARANCE_MODE = "dark"
REFRESH_RATE_MS = 100
