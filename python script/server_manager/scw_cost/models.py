from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(slots=True)
class InstanceRecord:
    id: str
    name: str
    zone: str
    project_id: str | None
    state: str | None
    commercial_type: str | None
    vcpus: int | None
    ram_gib: float | None
    hourly_eur: float | None
    monthly_eur: float | None
    public_ip: str | None
    tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class VolumeRecord:
    id: str
    name: str
    zone: str
    project_id: str | None
    source_api: str
    volume_type: str | None
    size_gb: float | None
    attached_server_id: str | None
    attached_server_name: str | None
    role: str
    monthly_eur: float | None
    pricing_note: str | None = None


@dataclass(slots=True)
class FlexibleIPRecord:
    id: str
    zone: str
    address: str | None
    project_id: str | None
    attached_server_id: str | None
    monthly_eur: float


@dataclass(slots=True)
class BucketRecord:
    name: str
    region: str | None
    total_size_gb: float
    object_count: int
    storage_classes_gb: dict[str, float]
    monthly_eur: float | None
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SecurityGroupRuleRecord:
    id: str
    direction: str | None
    action: str | None
    protocol: str | None
    ip_range: str | None
    dest_ip_range: str | None
    dest_port_from: int | None
    dest_port_to: int | None
    position: int | None


@dataclass(slots=True)
class SecurityGroupServerRecord:
    id: str
    name: str
    zone: str
    state: str | None
    commercial_type: str | None
    public_ip: str | None


@dataclass(slots=True)
class SecurityGroupRecord:
    id: str
    name: str
    zone: str
    project_id: str | None
    description: str | None
    state: str | None
    stateful: bool
    project_default: bool
    inbound_default_policy: str | None
    outbound_default_policy: str | None
    enable_default_security: bool
    server_count: int
    rule_count: int
    servers: list[SecurityGroupServerRecord] = field(default_factory=list)
    rules: list[SecurityGroupRuleRecord] = field(default_factory=list)


@dataclass(slots=True)
class CostReport:
    generated_at: str
    catalog_metadata: dict[str, Any]
    zones_scanned: list[str]
    totals: dict[str, float]
    instances: list[InstanceRecord]
    volumes: list[VolumeRecord]
    flexible_ips: list[FlexibleIPRecord]
    buckets: list[BucketRecord]
    security_groups: list[SecurityGroupRecord]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "catalog_metadata": self.catalog_metadata,
            "zones_scanned": self.zones_scanned,
            "totals": self.totals,
            "instances": [asdict(item) for item in self.instances],
            "volumes": [asdict(item) for item in self.volumes],
            "flexible_ips": [asdict(item) for item in self.flexible_ips],
            "buckets": [asdict(item) for item in self.buckets],
            "security_groups": [asdict(item) for item in self.security_groups],
            "warnings": list(self.warnings),
        }


@dataclass(slots=True)
class RefreshResult:
    report: CostReport
    json_path: str
    csv_path: str
    markdown_path: str
