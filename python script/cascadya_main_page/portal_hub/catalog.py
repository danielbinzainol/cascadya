from __future__ import annotations

from dataclasses import dataclass

from .config import Settings


@dataclass(frozen=True)
class SectionDef:
    key: str
    title: str
    strapline: str
    description: str


@dataclass(frozen=True)
class AppCard:
    key: str
    title: str
    section: str
    href: str
    badge: str
    accent: str
    description: str
    audience: str
    required_tags: tuple[str, ...]
    preview_when_locked: bool = False


SECTION_DEFS: tuple[SectionDef, ...] = (
    SectionDef(
        key="operations",
        title="Operations",
        strapline="Pilotage and day-2 tasks",
        description="Control surfaces for platform operations, rollout follow-up and delivery flow.",
    ),
    SectionDef(
        key="monitoring",
        title="Monitoring",
        strapline="Observability and signal triage",
        description="Dashboards, metrics routing and the fast path to investigate health and telemetry.",
    ),
    SectionDef(
        key="security",
        title="Security",
        strapline="Detection and security posture",
        description="Security-focused tools, detection workflows and sensitive operations kept on native UIs.",
    ),
    SectionDef(
        key="platform",
        title="Platform",
        strapline="Identity and internal references",
        description="Platform administration entry points that stay decoupled from the portal itself.",
    ),
)


def build_cards(settings: Settings) -> tuple[AppCard, ...]:
    cards = [
        AppCard(
            key="control-panel",
            title="Control Panel",
            section="operations",
            href=settings.control_panel_url,
            badge="Native UI",
            accent="teal",
            description="Fleet operations, workflows and day-to-day control surfaces on the native DNS.",
            audience="Operators and platform owners",
            required_tags=("control-panel-user", "portal-admin"),
            preview_when_locked=True,
        ),
        AppCard(
            key="features",
            title="Features",
            section="operations",
            href=settings.features_url,
            badge="Spec review",
            accent="amber",
            description="Quick feature challenge workspace for reviewing scope, risks and acceptance before delivery.",
            audience="Product, ops and engineering",
            required_tags=("control-panel-user", "portal-admin"),
            preview_when_locked=True,
        ),
        AppCard(
            key="grafana",
            title="Grafana",
            section="monitoring",
            href=settings.grafana_url,
            badge="Dashboards",
            accent="blue",
            description="Dashboards, drill-downs and shared observability views backed by the existing monitoring stack.",
            audience="Monitoring and support teams",
            required_tags=("grafana-user", "monitoring-user", "portal-admin"),
            preview_when_locked=True,
        ),
        AppCard(
            key="mimir",
            title="Mimir",
            section="monitoring",
            href=settings.mimir_url,
            badge="Grafana-backed",
            accent="cyan",
            description="Mimir is the metrics backend, but the human-facing dashboards live in Grafana. This card opens the Grafana-backed Mimir entry point configured for the portal.",
            audience="Observability maintainers and platform operators",
            required_tags=("monitoring-user", "portal-admin"),
            preview_when_locked=True,
        ),
        AppCard(
            key="wazuh",
            title="Wazuh",
            section="security",
            href=settings.wazuh_url,
            badge="Security",
            accent="rose",
            description="Threat detection, agent state and security investigation on the native security stack.",
            audience="Security operators",
            required_tags=("wazuh-user", "security-user", "portal-admin"),
            preview_when_locked=False,
        ),
        AppCard(
            key="keycloak-admin",
            title="Keycloak Admin",
            section="platform",
            href=settings.keycloak_admin_url,
            badge="Identity",
            accent="violet",
            description="Administrative identity console kept separate from the portal navigation experience.",
            audience="Portal and IAM admins",
            required_tags=("portal-admin",),
            preview_when_locked=False,
        ),
    ]

    if settings.docs_url:
        cards.append(
            AppCard(
                key="docs",
                title="Platform Docs",
                section="platform",
                href=settings.docs_url,
                badge="Runbooks",
                accent="slate",
                description="Runbooks, rollout notes and internal references that help operators navigate the platform.",
                audience="Authenticated platform users",
                required_tags=("portal-access", "portal-admin"),
                preview_when_locked=True,
            )
        )

    return tuple(cards)


def get_section(section_key: str) -> SectionDef | None:
    for section in SECTION_DEFS:
        if section.key == section_key:
            return section
    return None
