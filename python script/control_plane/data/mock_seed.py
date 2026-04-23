from __future__ import annotations

from data.mock_data import AppState, AssetSnapshot, E2ERow, RouteSnapshot, ServiceSnapshot, SiteSummary


def seed_state(state: AppState) -> None:
    state.sites = {
        "ouest-consigne": SiteSummary(
            site_id="ouest-consigne",
            name="Ouest Consigne",
            city="Carquefou",
            code="44",
            sector="Lavage bouteilles",
            capacity_mw=2.5,
            status="active",
            ems_site_status="healthy",
            routes_ok=6,
            routes_total=6,
            last_hb="12s ago",
            last_job_summary="12/12 steps completed - 2026-03-15 14:30 UTC",
        ),
        "usine-nord": SiteSummary(
            site_id="usine-nord",
            name="Usine Nord",
            city="Dunkerque",
            code="59",
            sector="Fours industriels",
            capacity_mw=6.0,
            status="active",
            ems_site_status="degraded",
            routes_ok=4,
            routes_total=6,
            last_hb="3m ago",
        ),
        "verrerie-est": SiteSummary(
            site_id="verrerie-est",
            name="Verrerie Est",
            city="Troyes",
            code="10",
            sector="Fusion verre",
            capacity_mw=4.0,
            status="active",
            ems_site_status="healthy",
            routes_ok=6,
            routes_total=6,
            last_hb="18s ago",
        ),
        "papeterie-vosges": SiteSummary(
            site_id="papeterie-vosges",
            name="Papeterie Vosges",
            city="Epinal",
            code="88",
            sector="Papier recycle",
            capacity_mw=8.0,
            status="active",
            ems_site_status="healthy",
            routes_ok=6,
            routes_total=6,
            last_hb="5s ago",
        ),
        "laiterie-bretagne": SiteSummary(
            site_id="laiterie-bretagne",
            name="Laiterie Bretagne",
            city="Rennes",
            code="35",
            sector="Process laitier",
            capacity_mw=3.0,
            status="provisioning",
            ems_site_status="waiting",
            routes_ok=0,
            routes_total=6,
            last_hb="---",
            last_job_summary="Provisioning prepared - awaiting operator run",
        ),
    }

    state.site_services["ouest-consigne"] = (
        ServiceSnapshot("ems-site", "healthy", ("Config v3 synced", "Modbus connected", "Buffer 0 msg pending", "HB 12s ago")),
        ServiceSnapshot("ems-core", "healthy", ("Config v43 synced", "Site dans config oui", "Optimizer active", "Last telemetry 2s ago")),
        ServiceSnapshot("ems-light", "healthy", ("Config v18 synced", "Site dans config oui", "IEC 104 addr CA=1", "Last signal 28s ago")),
    )
    state.site_alerts["ouest-consigne"] = ("Config drift ems-site : applied v2, desired v3 (drift 35 min)",)
    state.site_routes["ouest-consigne"] = (
        RouteSnapshot("telemetry_power", "cascadya/ouest-consigne/telemetry/power", "ems-site", "ems-core", "60/min", "healthy"),
        RouteSnapshot("setpoint_command", "cascadya/ouest-consigne/command/setpoint", "ems-core", "ems-site", "12/min", "healthy"),
        RouteSnapshot("capacity_update", "cascadya/ouest-consigne/command/capacity-update", "control-plane", "ems-site", "0/min", "healthy"),
        RouteSnapshot("rte_signal", "cascadya/ouest-consigne/telemetry/rte-signal", "ems-light", "ems-core", "2/min", "healthy"),
        RouteSnapshot("heartbeat", "cascadya/ouest-consigne/heartbeat/ems-site", "ems-site", "control-plane", "2/min", "healthy"),
    )
    state.site_assets["ouest-consigne"] = (
        AssetSnapshot("Chaudiere electrique", "PARAT Halvorsen", "IEH 6MW", "6 000 kW", "192.168.1.100:502"),
        AssetSnapshot("Capteur pression", "Endress+Hauser", "PMC51", "---", "192.168.1.100:502 reg 30010"),
    )
    state.site_e2e_history["ouest-consigne"] = (
        E2ERow("18/03 10:06", 847, 57, 180, 95, 210, 305, (4, 5, 5, 6, 5, 5, 4), "pass"),
        E2ERow("17/03 22:00", 912, 62, 195, 88, 245, 322, (5, 5, 6, 5, 4, 5, 5), "pass"),
        E2ERow("17/03 14:00", 780, 48, 165, 92, 198, 277, (4, 4, 5, 4, 4, 4, 4), "pass"),
        E2ERow("16/03 22:00", 1420, 55, 380, 102, 410, 473, (5, 6, 7, 5, 6, 7, 6), "slow"),
        E2ERow("16/03 14:00", 820, 50, 172, 90, 205, 303, (4, 4, 4, 5, 4, 4, 5), "pass"),
    )
