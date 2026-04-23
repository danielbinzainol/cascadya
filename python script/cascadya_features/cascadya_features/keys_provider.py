from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import AppConfig

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None


DEFAULT_KEYS_JS = "window.CASCADYA_KEYS = Object.freeze({});\n"


@dataclass(frozen=True)
class KeysPayload:
    source: str
    content: str
    detail: str


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8").rstrip() + "\n"


def load_keys_js(config: AppConfig) -> KeysPayload:
    if config.keys_database_url and psycopg is not None:
        try:
            with psycopg.connect(config.keys_database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(config.keys_sql)
                    row = cursor.fetchone()
            if row and row[0]:
                return KeysPayload(
                    source="database",
                    content=str(row[0]).rstrip() + "\n",
                    detail="keys.js charge depuis la base",
                )
            return KeysPayload(
                source="database-empty",
                content=DEFAULT_KEYS_JS,
                detail="Aucune ligne retournee par la requete SQL configuree",
            )
        except Exception as exc:  # pragma: no cover
            return KeysPayload(
                source="database-error",
                content=DEFAULT_KEYS_JS,
                detail=f"Echec de lecture DB: {exc}",
            )

    if config.keys_database_url and psycopg is None:
        return KeysPayload(
            source="database-driver-missing",
            content=DEFAULT_KEYS_JS,
            detail="psycopg indisponible, fallback sur une valeur vide",
        )

    if config.keys_file_path and config.keys_file_path.exists():
        return KeysPayload(
            source="file",
            content=_read_file(config.keys_file_path),
            detail=f"keys.js charge depuis {config.keys_file_path}",
        )

    return KeysPayload(
        source="default",
        content=DEFAULT_KEYS_JS,
        detail="Aucune source keys.js configuree",
    )

