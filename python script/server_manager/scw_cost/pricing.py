from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable


DECIMAL_GB = 1_000_000_000
GIB = 1024**3


@dataclass(slots=True)
class PriceCatalog:
    hours_per_month: int
    flexible_ipv4_hourly_eur: float
    volume_hourly_eur_per_gb: dict[str, float | None]
    object_storage_hourly_eur_per_gb: dict[str, float]
    metadata: dict[str, Any]


def load_price_catalog(raw_catalog: dict[str, Any]) -> PriceCatalog:
    return PriceCatalog(
        hours_per_month=int(raw_catalog.get("hours_per_month", 730)),
        flexible_ipv4_hourly_eur=float(
            raw_catalog.get("flexible_ipv4_hourly_eur", 0.004)
        ),
        volume_hourly_eur_per_gb={
            str(key).lower(): None if value is None else float(value)
            for key, value in raw_catalog.get("volume_hourly_eur_per_gb", {}).items()
        },
        object_storage_hourly_eur_per_gb={
            str(key).upper(): float(value)
            for key, value in raw_catalog.get(
                "object_storage_hourly_eur_per_gb", {}
            ).items()
        },
        metadata=dict(raw_catalog.get("metadata", {})),
    )


def bytes_to_decimal_gb(raw_bytes: int | float | None) -> float | None:
    if raw_bytes is None:
        return None
    return round(float(raw_bytes) / DECIMAL_GB, 3)


def bytes_to_gib(raw_bytes: int | float | None) -> float | None:
    if raw_bytes is None:
        return None
    return round(float(raw_bytes) / GIB, 2)


def money_to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^0-9,.\-]", "", value).replace(",", ".")
        if not cleaned or cleaned in {"-", ".", "-."}:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    if isinstance(value, dict):
        if "units" in value or "nanos" in value:
            try:
                units = float(value.get("units", 0) or 0)
                nanos = float(value.get("nanos", 0) or 0) / 1_000_000_000
                return units + nanos
            except (TypeError, ValueError):
                return None
        for nested_key in ("value", "amount", "price"):
            nested_value = money_to_float(value.get(nested_key))
            if nested_value is not None:
                return nested_value
    return None


def _walk_named_values(payload: Any, names: Iterable[str]) -> list[Any]:
    wanted = {name.lower() for name in names}
    found: list[Any] = []

    def _visit(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key.lower() in wanted:
                    found.append(value)
                _visit(value)
        elif isinstance(node, list):
            for item in node:
                _visit(item)

    _visit(payload)
    return found


def _first_float(values: list[Any]) -> float | None:
    for value in values:
        parsed = money_to_float(value)
        if parsed is not None and parsed >= 0:
            return parsed
    return None


def _parse_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        digits = re.sub(r"[^0-9]", "", value)
        if not digits:
            return None
        return int(digits)
    if isinstance(value, dict):
        for key in ("value", "size", "ram", "memory", "ncpus", "cpus", "vcpus"):
            parsed = _parse_int(value.get(key))
            if parsed is not None:
                return parsed
    return None


def _guess_bytes(value: Any) -> int | None:
    parsed = _parse_int(value)
    if parsed is None:
        return None
    if parsed > 1024 * 1024:
        return parsed
    return parsed * GIB


def extract_instance_pricing(product: dict[str, Any]) -> tuple[float | None, float | None]:
    hourly = _first_float(
        _walk_named_values(
            product,
            ("hourly_price", "price_per_hour", "hourly", "hourly_cost", "price_hourly"),
        )
    )
    monthly = _first_float(
        _walk_named_values(
            product,
            (
                "monthly_price",
                "price_per_month",
                "monthly",
                "monthly_cost",
                "price_monthly",
            ),
        )
    )
    return hourly, monthly


def extract_instance_specs(
    product: dict[str, Any], server: dict[str, Any]
) -> tuple[int | None, float | None]:
    vcpu_candidates = _walk_named_values(product, ("ncpus", "cpus", "vcpus"))
    vcpu_candidates.extend(_walk_named_values(server, ("ncpus", "cpus", "vcpus")))
    vcpus = None
    for value in vcpu_candidates:
        parsed = _parse_int(value)
        if parsed is not None and parsed > 0:
            vcpus = parsed
            break

    ram_candidates = _walk_named_values(product, ("ram", "memory"))
    ram_candidates.extend(_walk_named_values(server, ("ram", "memory")))
    ram_gib = None
    for value in ram_candidates:
        parsed = _guess_bytes(value)
        if parsed is not None and parsed > 0:
            ram_gib = bytes_to_gib(parsed)
            break

    return vcpus, ram_gib


def compute_instance_monthly(
    hourly_eur: float | None, monthly_eur: float | None, catalog: PriceCatalog
) -> float | None:
    if monthly_eur is not None:
        return round(monthly_eur, 4)
    if hourly_eur is not None:
        return round(hourly_eur * catalog.hours_per_month, 4)
    return None


def estimate_volume_monthly(
    volume_type: str | None,
    size_bytes: int | float | None,
    catalog: PriceCatalog,
) -> tuple[float | None, str | None]:
    if size_bytes is None:
        return None, "Volume size missing."
    size_gb = float(size_bytes) / DECIMAL_GB
    normalized_type = (volume_type or "").lower()
    hourly_rate = catalog.volume_hourly_eur_per_gb.get(normalized_type)
    if hourly_rate is None:
        if normalized_type == "l_ssd":
            return None, "No l_ssd rate configured in price_catalog.json."
        return None, f"No configured rate for volume type {volume_type!r}."

    monthly = round(size_gb * hourly_rate * catalog.hours_per_month, 4)
    if normalized_type == "b_ssd":
        return monthly, "b_ssd mapped to the 5K block rate as a best-effort default."
    if normalized_type == "sbs_volume":
        return monthly, "sbs_volume priced with the default 5K block rate."
    return monthly, None


def estimate_flexible_ip_monthly(catalog: PriceCatalog) -> float:
    return round(catalog.flexible_ipv4_hourly_eur * catalog.hours_per_month, 4)


def map_storage_class(raw_class: str | None) -> str:
    if not raw_class:
        return "STANDARD"
    normalized = raw_class.upper()
    aliases = {
        "STANDARD": "STANDARD",
        "STANDARD_MULTI_AZ": "STANDARD",
        "ONEZONE_IA": "ONEZONE_IA",
        "STANDARD_IA": "ONEZONE_IA",
        "STANDARD_ONE_ZONE": "ONEZONE_IA",
        "GLACIER": "GLACIER",
    }
    return aliases.get(normalized, normalized)


def estimate_bucket_monthly(
    class_sizes_bytes: dict[str, int],
    catalog: PriceCatalog,
) -> tuple[float | None, list[str]]:
    warnings: list[str] = []
    total = 0.0
    for raw_class, size_bytes in class_sizes_bytes.items():
        normalized_class = map_storage_class(raw_class)
        rate = catalog.object_storage_hourly_eur_per_gb.get(normalized_class)
        if rate is None:
            warnings.append(
                f"No object storage rate configured for class {raw_class!r}."
            )
            continue
        total += (size_bytes / DECIMAL_GB) * rate * catalog.hours_per_month
    if total == 0 and warnings:
        return None, warnings
    return round(total, 4), warnings
