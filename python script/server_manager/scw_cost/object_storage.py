from __future__ import annotations

from collections import defaultdict
from typing import Any

from .config import AppConfig
from .models import BucketRecord
from .pricing import bytes_to_decimal_gb, estimate_bucket_monthly

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # pragma: no cover
    boto3 = None

    class BotoCoreError(Exception):
        pass

    class ClientError(Exception):
        pass


def _effective_access_key(config: AppConfig) -> str | None:
    if not config.access_key:
        return None
    if config.project_id and "@" not in config.access_key:
        # Scaleway supports access_key@project_id to target Object Storage calls.
        return f"{config.access_key}@{config.project_id}"
    return config.access_key


def _client_for_region(config: AppConfig, region: str) -> Any:
    assert boto3 is not None
    session = boto3.session.Session()
    return session.client(
        "s3",
        region_name=region,
        endpoint_url=f"https://s3.{region}.scw.cloud",
        aws_access_key_id=_effective_access_key(config),
        aws_secret_access_key=config.secret_key,
    )


def _discover_buckets(config: AppConfig) -> tuple[dict[str, str | None], list[str]]:
    warnings: list[str] = []
    discovered: dict[str, str | None] = {}
    clients: dict[str, Any] = {}

    for region in config.object_regions:
        clients[region] = _client_for_region(config, region)

    for region, client in clients.items():
        try:
            response = client.list_buckets()
        except (BotoCoreError, ClientError) as exc:
            warnings.append(f"Object Storage discovery failed on {region}: {exc}")
            continue
        for bucket in response.get("Buckets", []):
            name = bucket.get("Name")
            if name:
                discovered.setdefault(name, region)

    for bucket_name in list(discovered):
        for region, client in clients.items():
            try:
                response = client.get_bucket_location(Bucket=bucket_name)
            except (BotoCoreError, ClientError):
                continue
            location = response.get("LocationConstraint") or region
            discovered[bucket_name] = location
            break
        if discovered[bucket_name] is None:
            warnings.append(
                f"Could not determine region for bucket {bucket_name}; using discovery endpoint."
            )
    return discovered, warnings


def _scan_bucket_contents(client: Any, bucket_name: str) -> tuple[dict[str, int], int, list[str]]:
    class_sizes: dict[str, int] = defaultdict(int)
    object_count = 0
    notes: list[str] = []

    try:
        versioning = client.get_bucket_versioning(Bucket=bucket_name)
        versioning_status = (versioning or {}).get("Status")
    except (BotoCoreError, ClientError) as exc:
        versioning_status = None
        notes.append(f"Bucket versioning lookup failed: {exc}")

    if versioning_status in {"Enabled", "Suspended"}:
        paginator = client.get_paginator("list_object_versions")
        for page in paginator.paginate(Bucket=bucket_name):
            for version in page.get("Versions", []):
                storage_class = version.get("StorageClass") or "STANDARD"
                size_bytes = int(version.get("Size", 0) or 0)
                class_sizes[storage_class] += size_bytes
                object_count += 1
        notes.append("Versioned bucket scan includes all object versions.")
    else:
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket_name):
            for content in page.get("Contents", []):
                storage_class = content.get("StorageClass") or "STANDARD"
                size_bytes = int(content.get("Size", 0) or 0)
                class_sizes[storage_class] += size_bytes
                object_count += 1

    return dict(class_sizes), object_count, notes


def scan_buckets(config: AppConfig, catalog) -> tuple[list[BucketRecord], list[str]]:
    if boto3 is None:
        return [], ["boto3 is not installed, so Object Storage scanning is disabled."]
    if not config.access_key:
        return [], ["SCW_ACCESS_KEY is missing, so Object Storage scanning is disabled."]

    warnings: list[str] = []
    buckets: list[BucketRecord] = []

    discovered, discovery_warnings = _discover_buckets(config)
    warnings.extend(discovery_warnings)

    for bucket_name, region in sorted(discovered.items()):
        if not region:
            warnings.append(f"Skipping bucket {bucket_name}: missing region.")
            continue
        client = _client_for_region(config, region)
        try:
            class_sizes, object_count, notes = _scan_bucket_contents(client, bucket_name)
        except (BotoCoreError, ClientError) as exc:
            warnings.append(f"Bucket scan failed for {bucket_name}: {exc}")
            continue

        monthly_eur, class_warnings = estimate_bucket_monthly(class_sizes, catalog)
        notes.extend(class_warnings)
        total_size_gb = round(
            sum(size_bytes for size_bytes in class_sizes.values()) / 1_000_000_000, 3
        )
        buckets.append(
            BucketRecord(
                name=bucket_name,
                region=region,
                total_size_gb=total_size_gb,
                object_count=object_count,
                storage_classes_gb={
                    storage_class: bytes_to_decimal_gb(size_bytes) or 0.0
                    for storage_class, size_bytes in sorted(class_sizes.items())
                },
                monthly_eur=monthly_eur,
                notes=notes,
            )
        )

    return buckets, warnings
