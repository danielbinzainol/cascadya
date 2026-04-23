from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os


DEFAULT_ZONES = [
    "fr-par-1",
    "fr-par-2",
    "fr-par-3",
    "nl-ams-1",
    "nl-ams-2",
    "nl-ams-3",
    "pl-waw-1",
    "pl-waw-2",
    "pl-waw-3",
]

DEFAULT_OBJECT_REGIONS = [
    "fr-par",
    "nl-ams",
    "pl-waw",
    "it-mil",
]


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _split_csv(raw_value: str | None, default: list[str]) -> list[str]:
    if not raw_value:
        return list(default)
    values = [item.strip() for item in raw_value.split(",")]
    return [item for item in values if item]


@dataclass(slots=True)
class AppConfig:
    workspace_dir: Path
    access_key: str | None
    secret_key: str
    organization_id: str | None
    project_id: str | None
    zones: list[str]
    object_regions: list[str]
    timeout_seconds: int
    price_catalog_path: Path
    output_dir: Path

    @classmethod
    def from_env(cls) -> "AppConfig":
        workspace_dir = Path(__file__).resolve().parent.parent
        load_env_file(workspace_dir / ".env")

        secret_key = os.getenv("SCW_SECRET_KEY", "").strip()
        if not secret_key:
            raise ValueError(
                "SCW_SECRET_KEY is required. Fill it in .env or in your environment."
            )

        price_catalog_path = Path(
            os.getenv("SCW_PRICE_CATALOG", "price_catalog.json").strip()
        )
        if not price_catalog_path.is_absolute():
            price_catalog_path = workspace_dir / price_catalog_path

        output_dir = Path(os.getenv("SCW_OUTPUT_DIR", "output").strip())
        if not output_dir.is_absolute():
            output_dir = workspace_dir / output_dir

        timeout_seconds = int(os.getenv("SCW_TIMEOUT_SECONDS", "30").strip())

        return cls(
            workspace_dir=workspace_dir,
            access_key=os.getenv("SCW_ACCESS_KEY", "").strip() or None,
            secret_key=secret_key,
            organization_id=os.getenv("SCW_ORGANIZATION_ID", "").strip() or None,
            project_id=os.getenv("SCW_PROJECT_ID", "").strip() or None,
            zones=_split_csv(os.getenv("SCW_ZONES"), DEFAULT_ZONES),
            object_regions=_split_csv(
                os.getenv("SCW_OBJECT_REGIONS"), DEFAULT_OBJECT_REGIONS
            ),
            timeout_seconds=timeout_seconds,
            price_catalog_path=price_catalog_path,
            output_dir=output_dir,
        )

    def load_catalog(self) -> dict:
        if not self.price_catalog_path.exists():
            raise FileNotFoundError(
                f"Pricing catalog not found: {self.price_catalog_path}"
            )
        return json.loads(self.price_catalog_path.read_text(encoding="utf-8"))
