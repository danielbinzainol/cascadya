from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, request, send_file, send_from_directory
from waitress import serve

from .config import AppConfig
from .evaluator import evaluate_spec
from .keys_provider import load_keys_js


def _status_payload(config: AppConfig) -> dict[str, object]:
    keys_payload = load_keys_js(config)
    return {
        "app_name": config.app_name,
        "host": config.host,
        "port": config.port,
        "web_dir": str(config.web_dir),
        "dotenv_path": str(config.loaded_dotenv_path),
        "keys_source": keys_payload.source,
        "keys_detail": keys_payload.detail,
        "database_configured": bool(config.keys_database_url),
        "keys_file_configured": bool(config.keys_file_path),
        "configured_api_key_names": list(config.configured_api_key_names),
        "configured_api_key_count": len(config.configured_api_key_names),
    }


def create_app() -> Flask:
    config = AppConfig.from_env()
    config.web_dir.mkdir(parents=True, exist_ok=True)

    app = Flask(
        __name__,
        static_folder=str(config.web_dir),
        static_url_path="",
    )
    app.config["CASCADYA_FEATURES"] = config

    @app.after_request
    def _set_cache_headers(response):  # type: ignore[no-untyped-def]
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.get("/api/healthz")
    def healthz():
        runtime = app.config["CASCADYA_FEATURES"]
        return jsonify({"ok": True, "status": _status_payload(runtime)})

    @app.get("/api/status")
    def status():
        runtime = app.config["CASCADYA_FEATURES"]
        return jsonify({"status": _status_payload(runtime)})

    @app.post("/api/evaluate")
    def evaluate():
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({"error": "Invalid JSON payload"}), 400
        spec = str(payload.get("spec", ""))
        result = evaluate_spec(spec)
        return jsonify({"result": result.to_dict()})

    @app.get("/keys.js")
    def keys_js():
        runtime = app.config["CASCADYA_FEATURES"]
        payload = load_keys_js(runtime)
        return app.response_class(payload.content, mimetype="application/javascript")

    @app.route("/api/<path:subpath>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def unknown_api(subpath: str):
        return jsonify({"error": f"Unknown endpoint: /api/{subpath}"}), 404

    @app.get("/")
    def index():
        return send_from_directory(runtime_web_dir(app), "index.html")

    @app.get("/<path:asset_path>")
    def assets(asset_path: str):
        web_dir = runtime_web_dir(app)
        candidate = (web_dir / asset_path).resolve()
        try:
            candidate.relative_to(web_dir.resolve())
        except ValueError:
            return jsonify({"error": "Forbidden path"}), 403
        if candidate.is_file():
            return send_file(candidate)
        return send_from_directory(web_dir, "index.html")

    return app


def runtime_web_dir(app: Flask) -> Path:
    runtime = app.config["CASCADYA_FEATURES"]
    return runtime.web_dir


def launch_server(app: Flask | None = None) -> None:
    app = app or create_app()
    config = app.config["CASCADYA_FEATURES"]
    print(f"{config.app_name} running on http://{config.host}:{config.port}")
    print("Press Ctrl+C to stop the server.")
    serve(app, host=config.host, port=config.port)
