from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import importlib.util
import json
from urllib.parse import urlparse

from .config import AppConfig
from .inventory import refresh_report


WORKSPACE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = WORKSPACE_DIR / "web"


def _read_env_values() -> dict[str, str]:
    env_path = WORKSPACE_DIR / ".env"
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _runtime_status() -> dict[str, object]:
    env_values = _read_env_values()
    status: dict[str, object] = {
        "env_present": (WORKSPACE_DIR / ".env").exists(),
        "access_key_present": bool(env_values.get("SCW_ACCESS_KEY")),
        "secret_key_present": bool(env_values.get("SCW_SECRET_KEY")),
        "organization_id": env_values.get("SCW_ORGANIZATION_ID") or None,
        "project_id": env_values.get("SCW_PROJECT_ID") or None,
        "boto3_installed": importlib.util.find_spec("boto3") is not None,
        "workspace_dir": str(WORKSPACE_DIR),
        "web_dir": str(WEB_DIR),
    }
    try:
        config = AppConfig.from_env()
    except Exception as exc:
        status["config_ready"] = False
        status["config_error"] = str(exc)
        status["output_dir"] = str(WORKSPACE_DIR / "output")
        return status

    status["config_ready"] = True
    status["zones"] = config.zones
    status["object_regions"] = config.object_regions
    status["output_dir"] = str(config.output_dir)
    status["price_catalog_path"] = str(config.price_catalog_path)
    return status


def _latest_report_path() -> Path:
    try:
        config = AppConfig.from_env()
        return config.output_dir / "latest_report.json"
    except Exception:
        return WORKSPACE_DIR / "output" / "latest_report.json"


def _latest_report_payload() -> dict[str, object]:
    report_path = _latest_report_path()
    payload: dict[str, object] = {
        "report": None,
        "status": _runtime_status(),
        "files": {
            "json": str(report_path),
            "csv": str(report_path.with_suffix(".csv")),
            "markdown": str(report_path.with_suffix(".md")),
        },
    }
    if report_path.exists():
        payload["report"] = json.loads(report_path.read_text(encoding="utf-8"))
    return payload


class CostWebHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/report":
            self._send_json(_latest_report_payload())
            return
        if parsed.path == "/api/status":
            self._send_json({"status": _runtime_status()})
            return
        if parsed.path.startswith("/api/"):
            self._send_json({"error": f"Unknown endpoint: {parsed.path}"}, status=404)
            return

        requested_path = (WEB_DIR / parsed.path.lstrip("/")).resolve()
        if parsed.path == "/" or not requested_path.exists():
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/refresh":
            self._send_json({"error": f"Unknown endpoint: {parsed.path}"}, status=404)
            return

        try:
            config = AppConfig.from_env()
            result = refresh_report(config)
            self._send_json(
                {
                    "report": result.report.to_dict(),
                    "status": _runtime_status(),
                    "files": {
                        "json": result.json_path,
                        "csv": result.csv_path,
                        "markdown": result.markdown_path,
                    },
                }
            )
        except Exception as exc:
            self._send_json(
                {
                    "error": str(exc),
                    "status": _runtime_status(),
                },
                status=500,
            )

    def log_message(self, format: str, *args) -> None:
        print(f"[web] {self.address_string()} - {format % args}")

    def _send_json(self, payload: dict[str, object], status: int = 200) -> None:
        body = json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def launch_web_app(host: str = "127.0.0.1", port: int = 8765) -> None:
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((host, port), CostWebHandler)
    print(f"Scaleway web app running on http://{host}:{port}")
    print("Press Ctrl+C to stop the server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping web server...")
    finally:
        server.server_close()
