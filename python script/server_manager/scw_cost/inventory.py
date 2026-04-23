from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from .api import ApiError, ScalewayApiClient
from .config import AppConfig
from .models import (
    CostReport,
    FlexibleIPRecord,
    InstanceRecord,
    RefreshResult,
    SecurityGroupRecord,
    SecurityGroupRuleRecord,
    SecurityGroupServerRecord,
    VolumeRecord,
)
from .object_storage import scan_buckets
from .pricing import (
    bytes_to_decimal_gb,
    compute_instance_monthly,
    estimate_flexible_ip_monthly,
    estimate_volume_monthly,
    extract_instance_pricing,
    extract_instance_specs,
    load_price_catalog,
)
from .reporter import write_report_files


def _project_matches(config: AppConfig, project_id: str | None) -> bool:
    if not config.project_id:
        return True
    if not project_id:
        return False
    return project_id == config.project_id


def _normalize_products(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_servers = payload.get("servers", payload)
    normalized: dict[str, dict[str, Any]] = {}
    if isinstance(raw_servers, dict):
        for key, value in raw_servers.items():
            if not isinstance(value, dict):
                continue
            commercial_type = (
                value.get("commercial_type")
                or value.get("name")
                or value.get("commercial_name")
                or key
            )
            normalized[str(commercial_type)] = value
    elif isinstance(raw_servers, list):
        for entry in raw_servers:
            if not isinstance(entry, dict):
                continue
            commercial_type = (
                entry.get("commercial_type")
                or entry.get("name")
                or entry.get("commercial_name")
            )
            if commercial_type:
                normalized[str(commercial_type)] = entry
    return normalized


def _build_server_volume_lookup(
    servers_by_zone: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, dict[str, Any]], dict[str, set[str]], dict[str, tuple[str | None, str | None]]]:
    volume_lookup: dict[str, dict[str, Any]] = {}
    root_ids_by_server: dict[str, set[str]] = defaultdict(set)
    attachment_map: dict[str, tuple[str | None, str | None]] = {}

    for servers in servers_by_zone.values():
        for server in servers:
            server_id = server.get("id")
            server_name = server.get("name")
            raw_volumes = server.get("volumes", {})
            entries = list(raw_volumes.values()) if isinstance(raw_volumes, dict) else raw_volumes
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                volume_id = entry.get("id")
                if not volume_id:
                    continue
                volume_lookup[volume_id] = entry
                attachment_map[volume_id] = (server_id, server_name)
                if entry.get("boot") and server_id:
                    root_ids_by_server[server_id].add(volume_id)

    return volume_lookup, root_ids_by_server, attachment_map


def _preflight_auth_check(client: ScalewayApiClient, zones: list[str]) -> None:
    if not zones:
        return
    try:
        client.get_server_products(zones[0])
    except ApiError as exc:
        message = str(exc)
        if "authentication is denied" in message:
            raise ValueError(
                "Scaleway authentication failed. Check SCW_SECRET_KEY in .env: "
                "use the secret part of a Scaleway API key for the same Organization, "
                "not the access key, and verify the key is still active."
            ) from exc
        raise


def refresh_report(config: AppConfig) -> RefreshResult:
    catalog = load_price_catalog(config.load_catalog())
    client = ScalewayApiClient(config.secret_key, config.timeout_seconds)
    warnings: list[str] = []
    _preflight_auth_check(client, config.zones)

    products_by_zone: dict[str, dict[str, dict[str, Any]]] = {}
    servers_by_zone: dict[str, list[dict[str, Any]]] = {}
    instance_volumes_by_zone: dict[str, list[dict[str, Any]]] = {}
    block_volumes_by_zone: dict[str, list[dict[str, Any]]] = {}
    ips_by_zone: dict[str, list[dict[str, Any]]] = {}
    security_groups_by_zone: dict[str, list[dict[str, Any]]] = {}

    for zone in config.zones:
        try:
            products_by_zone[zone] = _normalize_products(client.get_server_products(zone))
        except ApiError as exc:
            products_by_zone[zone] = {}
            warnings.append(f"Could not fetch server products for {zone}: {exc}")

        try:
            servers_by_zone[zone] = client.list_servers(zone)
        except ApiError as exc:
            servers_by_zone[zone] = []
            warnings.append(f"Could not fetch servers for {zone}: {exc}")

        try:
            instance_volumes_by_zone[zone] = client.list_instance_volumes(zone)
        except ApiError as exc:
            instance_volumes_by_zone[zone] = []
            warnings.append(f"Could not fetch instance volumes for {zone}: {exc}")

        try:
            block_volumes_by_zone[zone] = client.list_block_volumes(zone)
        except ApiError as exc:
            block_volumes_by_zone[zone] = []
            warnings.append(f"Could not fetch block volumes for {zone}: {exc}")

        try:
            ips_by_zone[zone] = client.list_ips(zone)
        except ApiError as exc:
            ips_by_zone[zone] = []
            warnings.append(f"Could not fetch flexible IPs for {zone}: {exc}")

        try:
            security_groups_by_zone[zone] = client.list_security_groups(zone)
        except ApiError as exc:
            security_groups_by_zone[zone] = []
            warnings.append(f"Could not fetch security groups for {zone}: {exc}")

    volume_entries, root_ids_by_server, attachment_map = _build_server_volume_lookup(servers_by_zone)

    instances: list[InstanceRecord] = []
    volumes: list[VolumeRecord] = []
    flexible_ips: list[FlexibleIPRecord] = []
    security_groups: list[SecurityGroupRecord] = []
    seen_volume_ids: set[str] = set()

    for zone, servers in servers_by_zone.items():
        for server in servers:
            project_id = server.get("project")
            if not _project_matches(config, project_id):
                continue

            commercial_type = server.get("commercial_type")
            product = products_by_zone.get(zone, {}).get(str(commercial_type), {})
            hourly_eur, monthly_direct = extract_instance_pricing(product)
            vcpus, ram_gib = extract_instance_specs(product, server)
            monthly_eur = compute_instance_monthly(hourly_eur, monthly_direct, catalog)

            notes: list[str] = []
            if monthly_eur is None:
                notes.append("Instance price not resolved from the product catalog.")

            public_ip = None
            if isinstance(server.get("public_ip"), dict):
                public_ip = server["public_ip"].get("address")

            instances.append(
                InstanceRecord(
                    id=str(server.get("id", "")),
                    name=str(server.get("name", "")),
                    zone=zone,
                    project_id=project_id,
                    state=server.get("state"),
                    commercial_type=commercial_type,
                    vcpus=vcpus,
                    ram_gib=ram_gib,
                    hourly_eur=hourly_eur,
                    monthly_eur=monthly_eur,
                    public_ip=public_ip,
                    tags=list(server.get("tags", []) or []),
                    notes=notes,
                )
            )

    for zone, zone_volumes in instance_volumes_by_zone.items():
        for volume in zone_volumes:
            project_id = volume.get("project")
            if not _project_matches(config, project_id):
                continue
            volume_id = str(volume.get("id", ""))
            if not volume_id or volume_id in seen_volume_ids:
                continue
            seen_volume_ids.add(volume_id)

            server_info = volume.get("server") or {}
            attached_server_id = server_info.get("id")
            attached_server_name = server_info.get("name")
            if volume_id in attachment_map:
                attached_server_id, attached_server_name = attachment_map[volume_id]
            role = "root" if volume_id in root_ids_by_server.get(attached_server_id or "", set()) else "data"
            monthly_eur, pricing_note = estimate_volume_monthly(
                volume.get("volume_type"),
                volume.get("size"),
                catalog,
            )

            volumes.append(
                VolumeRecord(
                    id=volume_id,
                    name=str(volume.get("name", "")),
                    zone=zone,
                    project_id=project_id,
                    source_api="instance",
                    volume_type=volume.get("volume_type"),
                    size_gb=bytes_to_decimal_gb(volume.get("size")),
                    attached_server_id=attached_server_id,
                    attached_server_name=attached_server_name,
                    role=role,
                    monthly_eur=monthly_eur,
                    pricing_note=pricing_note,
                )
            )

    for zone, zone_volumes in block_volumes_by_zone.items():
        for volume in zone_volumes:
            project_id = volume.get("project_id") or volume.get("project")
            if not _project_matches(config, project_id):
                continue
            volume_id = str(volume.get("id", ""))
            if not volume_id or volume_id in seen_volume_ids:
                continue
            seen_volume_ids.add(volume_id)

            attached_server_id, attached_server_name = attachment_map.get(volume_id, (None, None))
            role = "root" if volume_id in root_ids_by_server.get(attached_server_id or "", set()) else "data"
            volume_type = volume.get("type") or volume_entries.get(volume_id, {}).get("volume_type")
            monthly_eur, pricing_note = estimate_volume_monthly(volume_type, volume.get("size"), catalog)
            volumes.append(
                VolumeRecord(
                    id=volume_id,
                    name=str(volume.get("name", "")),
                    zone=zone,
                    project_id=project_id,
                    source_api="block",
                    volume_type=volume_type,
                    size_gb=bytes_to_decimal_gb(volume.get("size")),
                    attached_server_id=attached_server_id,
                    attached_server_name=attached_server_name,
                    role=role,
                    monthly_eur=monthly_eur,
                    pricing_note=pricing_note,
                )
            )

    flexible_ip_monthly = estimate_flexible_ip_monthly(catalog)
    for zone, zone_ips in ips_by_zone.items():
        for ip in zone_ips:
            project_id = ip.get("project") or ip.get("project_id")
            if not _project_matches(config, project_id):
                continue
            attached_server = ip.get("server") or {}
            flexible_ips.append(
                FlexibleIPRecord(
                    id=str(ip.get("id", ip.get("address", ""))),
                    zone=zone,
                    address=ip.get("address"),
                    project_id=project_id,
                    attached_server_id=attached_server.get("id"),
                    monthly_eur=flexible_ip_monthly,
                )
            )

    instance_lookup = {item.id: item for item in instances}
    for zone, zone_security_groups in security_groups_by_zone.items():
        for security_group in zone_security_groups:
            project_id = security_group.get("project")
            if not _project_matches(config, project_id):
                continue

            security_group_id = str(security_group.get("id", ""))
            rules_raw: list[dict[str, Any]] = []
            try:
                rules_raw = client.list_security_group_rules(zone, security_group_id)
            except ApiError as exc:
                warnings.append(
                    f"Could not fetch security group rules for {security_group.get('name', security_group_id)} in {zone}: {exc}"
                )

            servers: list[SecurityGroupServerRecord] = []
            for server_ref in security_group.get("servers", []) or []:
                server_id = str(server_ref.get("id", ""))
                instance = instance_lookup.get(server_id)
                servers.append(
                    SecurityGroupServerRecord(
                        id=server_id,
                        name=str(server_ref.get("name", "")),
                        zone=instance.zone if instance else zone,
                        state=instance.state if instance else None,
                        commercial_type=instance.commercial_type if instance else None,
                        public_ip=instance.public_ip if instance else None,
                    )
                )

            rules = [
                SecurityGroupRuleRecord(
                    id=str(rule.get("id", "")),
                    direction=rule.get("direction"),
                    action=rule.get("action"),
                    protocol=rule.get("protocol"),
                    ip_range=rule.get("ip_range"),
                    dest_ip_range=rule.get("dest_ip_range"),
                    dest_port_from=rule.get("dest_port_from"),
                    dest_port_to=rule.get("dest_port_to"),
                    position=rule.get("position"),
                )
                for rule in rules_raw
            ]
            rules.sort(key=lambda item: (item.position or 0, item.id))
            servers.sort(key=lambda item: item.name.lower())

            security_groups.append(
                SecurityGroupRecord(
                    id=security_group_id,
                    name=str(security_group.get("name", "")),
                    zone=zone,
                    project_id=project_id,
                    description=security_group.get("description"),
                    state=security_group.get("state"),
                    stateful=bool(security_group.get("stateful", False)),
                    project_default=bool(security_group.get("project_default", False)),
                    inbound_default_policy=security_group.get("inbound_default_policy"),
                    outbound_default_policy=security_group.get("outbound_default_policy"),
                    enable_default_security=bool(
                        security_group.get("enable_default_security", False)
                    ),
                    server_count=len(servers),
                    rule_count=len(rules),
                    servers=servers,
                    rules=rules,
                )
            )

    security_groups.sort(key=lambda item: (item.zone, item.name.lower()))

    buckets, bucket_warnings = scan_buckets(config, catalog)
    warnings.extend(bucket_warnings)
    if config.project_id:
        warnings.append(
            "Object Storage scan is scoped to SCW_PROJECT_ID for S3-compatible calls."
        )
    else:
        warnings.append(
            "Object Storage scan uses the API key preferred project if SCW_PROJECT_ID is not set."
        )

    totals = {
        "instances_monthly_eur": round(sum(item.monthly_eur or 0 for item in instances), 4),
        "volumes_monthly_eur": round(sum(item.monthly_eur or 0 for item in volumes), 4),
        "flexible_ips_monthly_eur": round(sum(item.monthly_eur for item in flexible_ips), 4),
        "object_storage_monthly_eur": round(sum(item.monthly_eur or 0 for item in buckets), 4),
    }
    totals["grand_total_monthly_eur"] = round(sum(totals.values()), 4)

    report = CostReport(
        generated_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
        catalog_metadata=catalog.metadata,
        zones_scanned=list(config.zones),
        totals=totals,
        instances=instances,
        volumes=volumes,
        flexible_ips=flexible_ips,
        buckets=buckets,
        security_groups=security_groups,
        warnings=warnings,
    )

    json_path, csv_path, markdown_path = write_report_files(config.output_dir, report)
    return RefreshResult(
        report=report,
        json_path=str(json_path),
        csv_path=str(csv_path),
        markdown_path=str(markdown_path),
    )
