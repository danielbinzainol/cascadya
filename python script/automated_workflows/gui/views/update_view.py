from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass
from typing import Callable

import tkinter as tk
from tkinter import filedialog, ttk

from gui.components import LogConsole, ScrollableFrame
from gui.views.remote_unlock_dashboard import DashboardActionConfig, RemoteUnlockDashboard
from utils.config import DIAGNOSTIC_VM_TARGETS, GIT_PUSH_TARGETS, WORKFLOW_POLL_INTERVAL_MS
from workflows.ansible import (
    BrokerVmServerCertificatesWorkflow,
    EdgeComputerClientCertificatesWorkflow,
    IndustrialComputerSetupProvisioner,
    RemoteUnlockBaselineWorkflow,
    RemoteUnlockBootstrapWorkflow,
    RemoteUnlockBrokerPingWorkflow,
    RemoteUnlockCutoverWorkflow,
    RemoteUnlockFullFlowWorkflow,
    RemoteUnlockGenerateCertificatesWorkflow,
    RemoteUnlockPostRebootProofWorkflow,
    RemoteUnlockPreflightWorkflow,
    RemoteUnlockSeedVaultSecretWorkflow,
    RemoteUnlockValidateWorkflow,
    TerraformApplyWorkflow,
    TerraformPlanWorkflow,
    UserClientCertificatesWorkflow,
)
from workflows.base_workflow import BaseWorkflow
from workflows.diagnostic import AllVmDockerStatusWorkflow, VmDockerStatusWorkflow
from workflows.modules import SimulationPatternsWorkflow
from workflows.updater import (
    BrokerUpdater,
    GitPushWorkflow,
    GatewayModbusSbcUpdater,
    ModbusSimUpdater,
    TelemetryPublisherUpdater,
)


@dataclass(frozen=True)
class WorkflowButtonConfig:
    label: str
    description: str
    factory: Callable[[], BaseWorkflow] | None = None
    action: Callable[[], None] | None = None
    enabled: bool = True


@dataclass(frozen=True)
class WorkflowPanelConfig:
    name: str
    description: str
    sections: tuple["WorkflowSectionConfig", ...]


@dataclass(frozen=True)
class WorkflowSectionConfig:
    name: str
    description: str
    workflows: tuple[WorkflowButtonConfig, ...]


class UpdateView(ttk.Frame):
    """Main page hosting deployment and sync workflows."""

    def __init__(self, master: tk.Misc, log_console: LogConsole | None = None, **kwargs) -> None:
        super().__init__(master, padding=20, **kwargs)
        self.log_console = log_console or LogConsole(self)
        self.active_workflow: BaseWorkflow | None = None
        self._buttons: list[tuple[ttk.Button, bool]] = []
        self._controls: list[tuple[tk.Widget, bool]] = []
        self._status_var = tk.StringVar(value="Ready")
        self._panel_var = tk.StringVar()
        self._panel_description_var = tk.StringVar()
        self._git_target_var = tk.StringVar(value=GIT_PUSH_TARGETS[0].label)
        self._panel_configs = self._build_panel_configs()
        self._panel_lookup = {panel.name: panel for panel in self._panel_configs}
        self._git_target_lookup = {target.label: target for target in GIT_PUSH_TARGETS}
        self._remote_unlock_dashboard: RemoteUnlockDashboard | None = None
        self._active_remote_unlock_dashboard: RemoteUnlockDashboard | None = None

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)
        self._build_layout()

    def _build_layout(self) -> None:
        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        title = ttk.Label(
            header,
            text="Workflow Panels",
            style="ViewTitle.TLabel",
        )
        title.grid(row=0, column=0, sticky="w")

        subtitle = ttk.Label(
            header,
            text=(
                "Use the selector to switch the visible panel. The selector stays pinned while "
                "the workflow catalog below scrolls."
            ),
            style="Muted.TLabel",
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(4, 18))

        selector_row = ttk.Frame(header)
        selector_row.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        selector_row.columnconfigure(1, weight=1)

        selector_label = ttk.Label(selector_row, text="Current panel", style="CardTitle.TLabel")
        selector_label.grid(row=0, column=0, sticky="w", padx=(0, 12))

        self._panel_selector = ttk.Combobox(
            selector_row,
            textvariable=self._panel_var,
            values=[panel.name for panel in self._panel_configs],
            state="readonly",
        )
        self._panel_selector.grid(row=0, column=1, sticky="ew")
        self._panel_selector.bind("<<ComboboxSelected>>", self._on_panel_selected)

        self._panel_header = ttk.Label(header, style="CardTitle.TLabel")
        self._panel_header.grid(row=3, column=0, sticky="w")

        panel_description = ttk.Label(
            header,
            textvariable=self._panel_description_var,
            style="Muted.TLabel",
            wraplength=760,
            justify="left",
        )
        panel_description.grid(row=4, column=0, sticky="w", pady=(4, 10))

        body = ScrollableFrame(self)
        body.grid(row=1, column=0, sticky="nsew")
        body.content.columnconfigure(0, weight=1)

        self._panel_content = ttk.Frame(body.content)
        self._panel_content.grid(row=0, column=0, sticky="nsew")
        self._panel_content.columnconfigure(0, weight=1)

        if self._panel_configs:
            self._panel_var.set(self._panel_configs[0].name)
            self._render_panel(self._panel_var.get())

        self.log_console.grid(row=2, column=0, sticky="nsew", pady=(12, 10))

        footer = ttk.Frame(self)
        footer.grid(row=3, column=0, sticky="ew", pady=(0, 0))
        footer.columnconfigure(0, weight=1)

        status_label = ttk.Label(footer, textvariable=self._status_var, style="Muted.TLabel")
        status_label.grid(row=0, column=0, sticky="w")

        clear_button = ttk.Button(footer, text="Clear Console", command=self.log_console.clear)
        clear_button.grid(row=0, column=1, sticky="e")

    def _build_panel_configs(self) -> tuple[WorkflowPanelConfig, ...]:
        return (
            WorkflowPanelConfig(
                name="Update",
                description=(
                    "Deployment and synchronization workflows for the Modbus Simulator, "
                    "Industrial PC services and future broker updates."
                ),
                sections=(
                    WorkflowSectionConfig(
                        name="Deployment & Sync",
                        description=(
                            "Operational update workflows for field targets. Each action runs the "
                            "required sync sequence and service restart for the selected target."
                        ),
                        workflows=(
                            WorkflowButtonConfig(
                                label="Update Modbus Simulator",
                                description=(
                                    "Runs local sync, remote rsync through the jump host, then restarts "
                                    "the remote SystemD service."
                                ),
                                factory=ModbusSimUpdater,
                            ),
                            WorkflowButtonConfig(
                                label="Update IPC Gateway Modbus SBC",
                                description=(
                                    "Syncs the Industrial PC scripts, then restarts the "
                                    "cascadya-gateway.service unit."
                                ),
                                factory=GatewayModbusSbcUpdater,
                                enabled=True,
                            ),
                            WorkflowButtonConfig(
                                label="Update IPC Telemetry Publisher",
                                description=(
                                    "Syncs the Industrial PC scripts, then restarts the "
                                    "cascadya-telemetry.service unit."
                                ),
                                factory=TelemetryPublisherUpdater,
                                enabled=True,
                            ),
                            WorkflowButtonConfig(
                                label="Update Broker",
                                description=(
                                    "Runs the local sync, then pushes the VM Broker files to "
                                    "~/nats_bridge/ on the remote broker VM."
                                ),
                                factory=BrokerUpdater,
                                enabled=True,
                            ),
                        ),
                    ),
                ),
            ),
            WorkflowPanelConfig(
                name="Modules",
                description=(
                    "Reusable simulation modules and scenario variants. Add a new workflow "
                    "here when a simulation pattern has a defined command sequence."
                ),
                sections=(
                    WorkflowSectionConfig(
                        name="Simulation Patterns",
                        description=(
                            "Module-oriented scenario runners. Add a workflow here when a simulation "
                            "pattern has a stable command sequence."
                        ),
                        workflows=(
                            WorkflowButtonConfig(
                                label="Run Simulation Pattern",
                                description="Placeholder for the future simulation pattern variations/styles.",
                                factory=SimulationPatternsWorkflow,
                                enabled=False,
                            ),
                        ),
                    ),
                ),
            ),
            WorkflowPanelConfig(
                name="Ansible-Terraform",
                description=(
                    "Ordered Ansible and Terraform workflows for provisioning, certificate generation, "
                    "and infrastructure operations."
                ),
                sections=(
                    WorkflowSectionConfig(
                        name="Industrial Computer Setup",
                        description=(
                            "Provisioning workflows for a fresh Debian Industrial PC using ordered "
                            "Ansible playbooks from multiple repositories."
                        ),
                        workflows=(
                            WorkflowButtonConfig(
                                label="Provision Fresh Industrial PC",
                                description=(
                                    "Placeholder for the ordered Ansible playbook chain that prepares "
                                    "and configures a clean Debian Industrial PC."
                                ),
                                factory=IndustrialComputerSetupProvisioner,
                                enabled=False,
                            ),
                        ),
                    ),
                    WorkflowSectionConfig(
                        name="mTLS Certificates Generation",
                        description=(
                            "Regenerates the broker, edge, and user-side certificates from the "
                            "ansible-mosquitto-certificats repository."
                        ),
                        workflows=(
                            WorkflowButtonConfig(
                                label="Broker VM Server",
                                description=(
                                    "Runs the broker server certificate regeneration playbook from WSL."
                                ),
                                factory=BrokerVmServerCertificatesWorkflow,
                            ),
                            WorkflowButtonConfig(
                                label="Edge Computer Client",
                                description=(
                                    "Removes the current edge client certificate, then regenerates it "
                                    "with the edge-local inventory limit."
                                ),
                                factory=EdgeComputerClientCertificatesWorkflow,
                            ),
                            WorkflowButtonConfig(
                                label="User Client",
                                description=(
                                    "Runs the application client certificate regeneration playbook."
                                ),
                                factory=UserClientCertificatesWorkflow,
                            ),
                        ),
                    ),
                    WorkflowSectionConfig(
                        name="Terraform",
                        description=(
                            "Infrastructure workflows for the dev environment. Each action makes the "
                            "wrapper scripts executable, then runs the selected Terraform script."
                        ),
                        workflows=(
                            WorkflowButtonConfig(
                                label="Terraform Plan",
                                description="Runs ./plan_terraform.sh from the dev infrastructure environment.",
                                factory=TerraformPlanWorkflow,
                            ),
                            WorkflowButtonConfig(
                                label="Terraform Apply",
                                description="Runs ./apply_terraform.sh from the dev infrastructure environment.",
                                factory=TerraformApplyWorkflow,
                            ),
                        ),
                    ),
                ),
            ),
            WorkflowPanelConfig(
                name="Diagnostic",
                description=(
                    "Operational checks for cloud VMs and quick export of collected diagnostic output."
                ),
                sections=(
                    WorkflowSectionConfig(
                        name="VM Docker Status",
                        description=(
                            "Connects to the listed VMs with the personal SSH key and runs docker ps -a "
                            "to inspect container state."
                        ),
                        workflows=(
                            WorkflowButtonConfig(
                                label="Check All VMs",
                                description="Runs docker ps -a on all configured VMs in sequence.",
                                factory=AllVmDockerStatusWorkflow,
                            ),
                            *tuple(
                                WorkflowButtonConfig(
                                    label=f"Check {target.label}",
                                    description=(
                                        f"Connects to {target.username}@{target.host} and runs docker ps -a."
                                    ),
                                    factory=lambda current=target: VmDockerStatusWorkflow(current),
                                )
                                for target in DIAGNOSTIC_VM_TARGETS
                            ),
                        ),
                    ),
                    WorkflowSectionConfig(
                        name="Exports",
                        description=(
                            "Stores the current console content in a text file for traceability or sharing."
                        ),
                        workflows=(
                            WorkflowButtonConfig(
                                label="Save Console to TXT",
                                description="Exports the current console content to a .txt file.",
                                action=self._save_console_report,
                            ),
                        ),
                    ),
                ),
            ),
            WorkflowPanelConfig(
                name="Remote Unlock",
                description=(
                    "Phased WireGuard and Vault remote-unlock workflows for a fresh Cascadya IPC. "
                    "Use the full flow for a new session, or run individual phases when you need to "
                    "resume from a known checkpoint."
                ),
                sections=(
                    WorkflowSectionConfig(
                        name="Fresh IPC Flow",
                        description=(
                            "Runs the validated sequence up to cutover. The operator still performs the "
                            "final reboot, then uses the proof checks to confirm unattended unlock."
                        ),
                        workflows=(
                            WorkflowButtonConfig(
                                label="Run Full Remote Unlock Flow",
                                description=(
                                    "Executes sync, baseline, certificate generation, broker check, "
                                    "Vault secret seed, bootstrap, preflight, validation, and cutover."
                                ),
                                factory=RemoteUnlockFullFlowWorkflow,
                            ),
                            WorkflowButtonConfig(
                                label="Post-Reboot Proof Checks",
                                description=(
                                    "Collects the route, WireGuard, mount, and service status checks after "
                                    "the IPC has been rebooted."
                                ),
                                factory=RemoteUnlockPostRebootProofWorkflow,
                            ),
                        ),
                    ),
                    WorkflowSectionConfig(
                        name="Individual Phases",
                        description=(
                            "Manual phase controls for debugging or resuming an interrupted run. "
                            "Broker steps expect REMOTE_UNLOCK_BROKER_VAULT_TOKEN and either ssh-agent "
                            "or CASCADYA_BROKER_SSH_KEY_PASSPHRASE."
                        ),
                        workflows=(
                            WorkflowButtonConfig(
                                label="Baseline Report",
                                description="Captures the fresh IPC disk, crypttab, and WireGuard baseline.",
                                factory=RemoteUnlockBaselineWorkflow,
                            ),
                            WorkflowButtonConfig(
                                label="Generate Certificates",
                                description="Builds the local CA and per-device client certificate bundle.",
                                factory=RemoteUnlockGenerateCertificatesWorkflow,
                            ),
                            WorkflowButtonConfig(
                                label="Broker Ping",
                                description="Checks that the broker inventory is reachable with the current SSH setup.",
                                factory=RemoteUnlockBrokerPingWorkflow,
                            ),
                            WorkflowButtonConfig(
                                label="Seed Vault Secret",
                                description="Stores the current device passphrase in Vault for the selected device id.",
                                factory=RemoteUnlockSeedVaultSecretWorkflow,
                            ),
                            WorkflowButtonConfig(
                                label="Bootstrap IPC",
                                description="Installs WireGuard, stages mTLS assets, and deploys the unlock service.",
                                factory=RemoteUnlockBootstrapWorkflow,
                            ),
                            WorkflowButtonConfig(
                                label="Preflight",
                                description="Runs the preflight checks before validation and cutover.",
                                factory=RemoteUnlockPreflightWorkflow,
                            ),
                            WorkflowButtonConfig(
                                label="Validate",
                                description="Exercises the broker challenge and unlock path before cutover.",
                                factory=RemoteUnlockValidateWorkflow,
                            ),
                            WorkflowButtonConfig(
                                label="Cutover",
                                description="Applies the remote-unlock crypttab and fstab configuration.",
                                factory=RemoteUnlockCutoverWorkflow,
                            ),
                        ),
                    ),
                ),
            ),
        )

    def _on_panel_selected(self, _event: tk.Event) -> None:
        self._render_panel(self._panel_var.get())

    def _render_panel(self, panel_name: str) -> None:
        panel = self._panel_lookup[panel_name]
        self._panel_header.configure(text=panel.name)
        self._panel_description_var.set(panel.description)
        self._remote_unlock_dashboard = None

        for child in self._panel_content.winfo_children():
            child.destroy()

        self._buttons = []
        self._controls = []
        cards = ttk.Frame(self._panel_content, style="Card.TFrame")
        cards.grid(row=0, column=0, sticky="ew")
        cards.columnconfigure(0, weight=1)

        if panel.name == "Remote Unlock":
            self._render_remote_unlock_dashboard(cards, panel)
            self._set_buttons_enabled(enabled=self.active_workflow is None or not self.active_workflow.is_running)
            return

        for index, section in enumerate(panel.sections):
            self._render_section(cards, index, section)

        if panel.name == "Update":
            self._render_git_push_section(cards, len(panel.sections))

        self._set_buttons_enabled(enabled=self.active_workflow is None or not self.active_workflow.is_running)

    def _render_remote_unlock_dashboard(
        self,
        parent: ttk.Frame,
        panel: WorkflowPanelConfig,
    ) -> None:
        primary_actions = tuple(
            DashboardActionConfig(
                label=config.label,
                trigger=lambda current=config: self._activate_button(current),
                enabled=config.enabled,
                primary=True,
            )
            for config in panel.sections[0].workflows
        )
        phase_actions = tuple(
            DashboardActionConfig(
                label=config.label,
                trigger=lambda current=config: self._activate_button(current),
                enabled=config.enabled,
                primary=False,
            )
            for config in panel.sections[1].workflows
        )
        self._remote_unlock_dashboard = RemoteUnlockDashboard(
            parent,
            primary_actions=primary_actions,
            phase_actions=phase_actions,
        )
        self._remote_unlock_dashboard.grid(row=0, column=0, sticky="ew")

    def _render_section(
        self,
        parent: ttk.Frame,
        row_index: int,
        section: WorkflowSectionConfig,
    ) -> None:
        section_frame = ttk.Frame(parent)
        section_frame.grid(row=row_index, column=0, sticky="ew", pady=(0, 18))
        section_frame.columnconfigure(0, weight=1)

        title = ttk.Label(section_frame, text=section.name, style="CardTitle.TLabel")
        title.grid(row=0, column=0, sticky="w")

        description = ttk.Label(
            section_frame,
            text=section.description,
            style="Muted.TLabel",
            wraplength=760,
            justify="left",
        )
        description.grid(row=1, column=0, sticky="w", pady=(4, 10))

        for workflow_index, config in enumerate(section.workflows):
            self._render_workflow_card(section_frame, workflow_index + 2, config)

    def _render_workflow_card(
        self,
        parent: ttk.Frame,
        row_index: int,
        config: WorkflowButtonConfig,
    ) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=16)
        card.grid(row=row_index, column=0, sticky="ew", pady=(0, 12))
        card.columnconfigure(0, weight=1)

        label = ttk.Label(card, text=config.label, style="CardTitle.TLabel")
        label.grid(row=0, column=0, sticky="w")

        description = ttk.Label(
            card,
            text=config.description,
            style="CardBody.TLabel",
            wraplength=700,
            justify="left",
        )
        description.grid(row=1, column=0, sticky="w", pady=(6, 12))

        button = ttk.Button(
            card,
            text=config.label,
            command=lambda current=config: self._activate_button(current),
        )
        if not config.enabled:
            button.state(["disabled"])
        button.grid(row=0, column=1, rowspan=2, sticky="e")
        self._buttons.append((button, config.enabled))

    def _render_git_push_section(self, parent: ttk.Frame, row_index: int) -> None:
        section_frame = ttk.Frame(parent)
        section_frame.grid(row=row_index, column=0, sticky="ew", pady=(0, 18))
        section_frame.columnconfigure(0, weight=1)

        title = ttk.Label(section_frame, text="Git Push", style="CardTitle.TLabel")
        title.grid(row=0, column=0, sticky="w")

        description = ttk.Label(
            section_frame,
            text=(
                "Push du depot local vers la cible Git selectionnee. Le remote origin, "
                "l'identite Git locale et le push final sont ajustes automatiquement."
            ),
            style="Muted.TLabel",
            wraplength=760,
            justify="left",
        )
        description.grid(row=1, column=0, sticky="w", pady=(4, 10))

        self._render_git_push_card(section_frame, 2)

    def _render_git_push_card(self, parent: ttk.Frame, row_index: int) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=16)
        card.grid(row=row_index, column=0, sticky="ew", pady=(0, 12))
        card.columnconfigure(0, weight=1)
        card.columnconfigure(1, weight=1)

        label = ttk.Label(card, text="Push Current Repo", style="CardTitle.TLabel")
        label.grid(row=0, column=0, sticky="w")

        description = ttk.Label(
            card,
            text=(
                "Selectionne la cible Git a utiliser, puis lance le flux automatise de commit "
                "conditionnel et de push sur origin/main."
            ),
            style="CardBody.TLabel",
            wraplength=700,
            justify="left",
        )
        description.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 12))

        selector_label = ttk.Label(card, text="Target", style="Muted.TLabel")
        selector_label.grid(row=2, column=0, sticky="w", pady=(0, 6))

        if self._git_target_var.get() not in self._git_target_lookup:
            self._git_target_var.set(GIT_PUSH_TARGETS[0].label)

        target_selector = ttk.Combobox(
            card,
            textvariable=self._git_target_var,
            values=[target.label for target in GIT_PUSH_TARGETS],
            state="readonly",
        )
        target_selector.grid(row=3, column=0, sticky="ew", padx=(0, 12))

        button = ttk.Button(card, text="Push Current Repo", command=self._launch_git_push)
        button.grid(row=3, column=1, sticky="e")

        self._controls.append((target_selector, True))
        self._buttons.append((button, True))

    def _launch_git_push(self) -> None:
        target = self._git_target_lookup[self._git_target_var.get()]
        self._start_workflow(GitPushWorkflow(target))

    def _activate_button(self, config: WorkflowButtonConfig) -> None:
        if config.action is not None:
            config.action()
            return
        if config.factory is None:
            self.log_console.write_line(f"[workflow] No action configured for '{config.label}'.")
            return
        self._start_workflow(config.factory())

    def _launch_workflow(self, config: WorkflowButtonConfig) -> None:
        self._activate_button(config)

    def _save_console_report(self) -> None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = filedialog.asksaveasfilename(
            title="Save diagnostic report",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"diagnostic-report-{timestamp}.txt",
        )
        if not path:
            return

        content = self.log_console.get_content()
        if not content.strip():
            self.log_console.write_line("[workflow] No console output available to save.")
            return

        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(content)
        except OSError as exc:
            self.log_console.write_line(f"[workflow] Failed to save diagnostic report: {exc}")
            return

        self.log_console.write_line(f"[workflow] Saved console output to {path}")

    def _start_workflow(self, workflow: BaseWorkflow) -> None:
        if self.active_workflow and self.active_workflow.is_running:
            self.log_console.write_line("[workflow] Another workflow is already running.")
            return

        active_remote_dashboard = (
            self._remote_unlock_dashboard if self._is_remote_unlock_workflow(workflow) else None
        )
        self._active_remote_unlock_dashboard = active_remote_dashboard
        if active_remote_dashboard is not None and active_remote_dashboard.winfo_exists():
            active_remote_dashboard.prepare_for_workflow(workflow)
            if workflow.__class__.__name__ == "RemoteUnlockFullFlowWorkflow":
                self.log_console.clear()

        def workflow_callback(message: str) -> None:
            self.log_console.write_line(message)
            if active_remote_dashboard is not None and active_remote_dashboard.winfo_exists():
                self.after(
                    0,
                    lambda current=message, dashboard=active_remote_dashboard: (
                        dashboard.handle_log_message(current) if dashboard.winfo_exists() else None
                    ),
                )

        started = workflow.run(workflow_callback)
        if not started:
            return

        self.active_workflow = workflow
        self._status_var.set(f"Running: {workflow.name}")
        self._set_buttons_enabled(False)
        self.after(WORKFLOW_POLL_INTERVAL_MS, self._watch_active_workflow)

    def _watch_active_workflow(self) -> None:
        workflow = self.active_workflow
        if workflow is None:
            self._status_var.set("Ready")
            self._set_buttons_enabled(True)
            return

        if workflow.is_running:
            self.after(WORKFLOW_POLL_INTERVAL_MS, self._watch_active_workflow)
            return

        outcome = "Success" if workflow.last_success else "Failed"
        if self._is_remote_unlock_workflow(workflow):
            dashboard = self._active_remote_unlock_dashboard
            if dashboard is not None and dashboard.winfo_exists():
                dashboard.finish_workflow(workflow, workflow.last_success)
            self._active_remote_unlock_dashboard = None
        self._status_var.set(f"{workflow.name}: {outcome}")
        self._set_buttons_enabled(True)
        self.active_workflow = None

    def _set_buttons_enabled(self, enabled: bool) -> None:
        self._panel_selector.configure(state="readonly" if enabled else "disabled")
        if self._remote_unlock_dashboard is not None:
            self._remote_unlock_dashboard.set_enabled(enabled)
        for control, default_enabled in self._controls:
            if isinstance(control, ttk.Combobox):
                control.configure(state="readonly" if enabled and default_enabled else "disabled")
            else:
                control.configure(state="normal" if enabled and default_enabled else "disabled")

        for button, default_enabled in self._buttons:
            if enabled:
                if default_enabled:
                    button.state(["!disabled"])
                else:
                    button.state(["disabled"])
            else:
                button.state(["disabled"])

    @staticmethod
    def _is_remote_unlock_workflow(workflow: BaseWorkflow) -> bool:
        return workflow.__class__.__module__.endswith(".remote_unlock")
