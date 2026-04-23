from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import CostReport


def render_summary(report: CostReport) -> str:
    lines = [
        "Scaleway monthly estimate",
        "=========================",
        f"Generated at: {report.generated_at}",
        "",
        f"Grand total: {report.totals['grand_total_monthly_eur']:.4f} EUR/month",
        f"Instances: {report.totals['instances_monthly_eur']:.4f} EUR/month",
        f"Volumes: {report.totals['volumes_monthly_eur']:.4f} EUR/month",
        f"Flexible IPs: {report.totals['flexible_ips_monthly_eur']:.4f} EUR/month",
        f"Object Storage: {report.totals['object_storage_monthly_eur']:.4f} EUR/month",
        "",
        f"Instances scanned: {len(report.instances)}",
        f"Volumes scanned: {len(report.volumes)}",
        f"Flexible IPs scanned: {len(report.flexible_ips)}",
        f"Buckets scanned: {len(report.buckets)}",
        f"Security groups scanned: {len(report.security_groups)}",
    ]

    if report.warnings:
        lines.extend(["", "Warnings:"])
        for warning in report.warnings:
            lines.append(f"- {warning}")

    return "\n".join(lines)


def _markdown_report(report: CostReport) -> str:
    lines = [
        "# Scaleway monthly estimate",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Grand total: `{report.totals['grand_total_monthly_eur']:.4f} EUR/month`",
        "",
        "## Totals",
        "",
        "| Category | EUR/month |",
        "| --- | ---: |",
        f"| Instances | {report.totals['instances_monthly_eur']:.4f} |",
        f"| Volumes | {report.totals['volumes_monthly_eur']:.4f} |",
        f"| Flexible IPs | {report.totals['flexible_ips_monthly_eur']:.4f} |",
        f"| Object Storage | {report.totals['object_storage_monthly_eur']:.4f} |",
        f"| Grand total | {report.totals['grand_total_monthly_eur']:.4f} |",
        "",
        "## Inventory",
        "",
        f"- Instances: `{len(report.instances)}`",
        f"- Volumes: `{len(report.volumes)}`",
        f"- Flexible IPs: `{len(report.flexible_ips)}`",
        f"- Buckets: `{len(report.buckets)}`",
        f"- Security groups: `{len(report.security_groups)}`",
    ]

    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in report.warnings:
            lines.append(f"- {warning}")

    return "\n".join(lines) + "\n"


def _csv_rows(report: CostReport) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for item in report.instances:
        rows.append(
            {
                "kind": "instance",
                "name": item.name,
                "resource_id": item.id,
                "zone": item.zone,
                "details": f"{item.commercial_type or ''} / RAM={item.ram_gib or ''} GiB / vCPU={item.vcpus or ''}",
                "size_gb": "",
                "monthly_eur": "" if item.monthly_eur is None else f"{item.monthly_eur:.4f}",
                "note": " | ".join(item.notes),
            }
        )

    for item in report.volumes:
        rows.append(
            {
                "kind": f"volume_{item.role}",
                "name": item.name,
                "resource_id": item.id,
                "zone": item.zone,
                "details": f"{item.source_api} / {item.volume_type or ''} / attached_to={item.attached_server_name or ''}",
                "size_gb": "" if item.size_gb is None else f"{item.size_gb:.3f}",
                "monthly_eur": "" if item.monthly_eur is None else f"{item.monthly_eur:.4f}",
                "note": item.pricing_note or "",
            }
        )

    for item in report.flexible_ips:
        rows.append(
            {
                "kind": "flexible_ip",
                "name": item.address or item.id,
                "resource_id": item.id,
                "zone": item.zone,
                "details": f"attached_to={item.attached_server_id or ''}",
                "size_gb": "",
                "monthly_eur": f"{item.monthly_eur:.4f}",
                "note": "",
            }
        )

    for item in report.buckets:
        rows.append(
            {
                "kind": "bucket",
                "name": item.name,
                "resource_id": item.name,
                "zone": item.region or "",
                "details": f"objects={item.object_count} / classes={item.storage_classes_gb}",
                "size_gb": f"{item.total_size_gb:.3f}",
                "monthly_eur": "" if item.monthly_eur is None else f"{item.monthly_eur:.4f}",
                "note": " | ".join(item.notes),
            }
        )

    for item in report.security_groups:
        rows.append(
            {
                "kind": "security_group",
                "name": item.name,
                "resource_id": item.id,
                "zone": item.zone,
                "details": (
                    f"servers={item.server_count} / rules={item.rule_count} / "
                    f"inbound={item.inbound_default_policy or ''} / outbound={item.outbound_default_policy or ''}"
                ),
                "size_gb": "",
                "monthly_eur": "",
                "note": item.description or "",
            }
        )

    return rows


def write_report_files(output_dir: Path, report: CostReport) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "latest_report.json"
    csv_path = output_dir / "latest_report.csv"
    markdown_path = output_dir / "latest_report.md"

    json_path.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "kind",
                "name",
                "resource_id",
                "zone",
                "details",
                "size_gb",
                "monthly_eur",
                "note",
            ],
        )
        writer.writeheader()
        writer.writerows(_csv_rows(report))

    markdown_path.write_text(_markdown_report(report), encoding="utf-8")
    return json_path, csv_path, markdown_path
