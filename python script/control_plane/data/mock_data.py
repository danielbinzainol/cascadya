from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SiteSummary:
    site_id: str
    name: str
    city: str
    code: str
    sector: str
    capacity_mw: float
    status: str
    ems_site_status: str
    routes_ok: int
    routes_total: int
    last_hb: str
    last_job_summary: str = "No provisioning run yet"


@dataclass(frozen=True)
class ServiceSnapshot:
    name: str
    status: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class RouteSnapshot:
    route: str
    subject: str
    publisher: str
    subscriber: str
    rate: str
    status: str


@dataclass(frozen=True)
class AssetSnapshot:
    asset_type: str
    fabricant: str
    modele: str
    puissance: str
    modbus: str


@dataclass(frozen=True)
class E2ERow:
    date_label: str
    total_ms: int
    cp_core: int
    core_site: int
    modbus: int
    site_light: int
    light_rte: int
    sparkline: tuple[int, ...]
    status: str


@dataclass
class AppState:
    sites: dict[str, SiteSummary] = field(default_factory=dict)
    site_services: dict[str, tuple[ServiceSnapshot, ...]] = field(default_factory=dict)
    site_routes: dict[str, tuple[RouteSnapshot, ...]] = field(default_factory=dict)
    site_assets: dict[str, tuple[AssetSnapshot, ...]] = field(default_factory=dict)
    site_alerts: dict[str, tuple[str, ...]] = field(default_factory=dict)
    site_e2e_history: dict[str, tuple[E2ERow, ...]] = field(default_factory=dict)


def build_mock_state() -> AppState:
    from data.mock_seed import seed_state

    state = AppState()
    seed_state(state)
    return state
