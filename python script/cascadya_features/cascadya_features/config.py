from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


def _read_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def _discover_api_key_names() -> tuple[str, ...]:
    names = []
    for key, value in os.environ.items():
        if key.endswith("_API_KEY") and value.strip():
            names.append(key)
    return tuple(sorted(names))


@dataclass(frozen=True)
class AppConfig:
    app_name: str
    host: str
    port: int
    workspace_dir: Path
    web_dir: Path
    keys_database_url: str | None
    keys_sql: str
    keys_file_path: Path | None
    loaded_dotenv_path: Path
    configured_api_key_names: tuple[str, ...]

    @classmethod
    def from_env(cls) -> "AppConfig":
        workspace_dir = Path(__file__).resolve().parent.parent
        dotenv_path = workspace_dir / ".env"
        load_dotenv(dotenv_path=dotenv_path, override=False)
        keys_file_raw = os.environ.get("FEATURES_KEYS_FILE_PATH", "").strip()
        keys_file_path = Path(keys_file_raw).expanduser() if keys_file_raw else None
        return cls(
            app_name=os.environ.get("APP_NAME", "Cascadya Features").strip() or "Cascadya Features",
            host=os.environ.get("APP_HOST", "127.0.0.1").strip() or "127.0.0.1",
            port=_read_int("APP_PORT", 8766),
            workspace_dir=workspace_dir,
            web_dir=workspace_dir / "web",
            keys_database_url=os.environ.get("FEATURES_KEYS_DATABASE_URL", "").strip() or None,
            keys_sql=(
                os.environ.get(
                    "FEATURES_KEYS_SQL",
                    "select content from web_assets where name = 'keys.js' order by updated_at desc limit 1",
                ).strip()
                or "select content from web_assets where name = 'keys.js' order by updated_at desc limit 1"
            ),
            keys_file_path=keys_file_path,
            loaded_dotenv_path=dotenv_path,
            configured_api_key_names=_discover_api_key_names(),
        )
