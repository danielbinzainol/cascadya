from __future__ import annotations

from workflows.base_workflow import BaseWorkflow, CommandStep
from utils.config import (
    ANSIBLE_IPC_PASSWORD_PROMPTS,
    INDUSTRIAL_PC_HOST_KEY_CONFIRMATION_PROMPTS,
    INDUSTRIAL_PC_LOGIN_PASSWORD_PROMPTS,
    INDUSTRIAL_PC_TARGET,
    REMOTE_SUDO_PASSWORD_PROMPT,
    REMOTE_UNLOCK_ANSIBLE_PATH,
    REMOTE_UNLOCK_BROKER_INVENTORY,
    REMOTE_UNLOCK_BROKER_SSH_KEY_PASSPHRASE_PROMPTS,
    REMOTE_UNLOCK_BROKER_VAULT_TOKEN_ENV_VAR,
    REMOTE_UNLOCK_DEVICE_ID,
    REMOTE_UNLOCK_IPC_INVENTORY,
    REMOTE_UNLOCK_VAULT_SECRET_VALUE,
    REMOTE_UNLOCK_WIREGUARD_KEY_PATH,
)


SYNC_WARNING_EXIT_CODES = frozenset({0, 23, 24})


def _sync_step() -> CommandStep:
    return CommandStep(
        title="Synchronise WSL Mirror",
        command="\n".join(
            (
                f"cd {REMOTE_UNLOCK_ANSIBLE_PATH}",
                "syncproject",
            )
        ),
        description=(
            "Refreshes the WSL copy of the ansible repository. Exit codes 23 and 24 are "
            "tolerated because your local syncproject currently reports known rsync warnings."
        ),
        accepted_exit_codes=SYNC_WARNING_EXIT_CODES,
    )


def _ipc_playbook_step(title: str, playbook: str, description: str) -> CommandStep:
    return CommandStep(
        title=title,
        command="\n".join(
            (
                f"cd {REMOTE_UNLOCK_ANSIBLE_PATH}",
                f"ANSIBLE_CONFIG=./ansible.cfg ansible-playbook -i {REMOTE_UNLOCK_IPC_INVENTORY} -k -K {playbook}",
            )
        ),
        description=description,
        interactive_prompts=ANSIBLE_IPC_PASSWORD_PROMPTS,
    )


def _broker_playbook_step(title: str, playbook: str, description: str) -> CommandStep:
    return CommandStep(
        title=title,
        command="\n".join(
            (
                f"cd {REMOTE_UNLOCK_ANSIBLE_PATH}",
                f'if [ -z "${REMOTE_UNLOCK_BROKER_VAULT_TOKEN:-}" ]; then echo "{REMOTE_UNLOCK_BROKER_VAULT_TOKEN_ENV_VAR} is not set"; exit 1; fi',
                (
                    f"ANSIBLE_CONFIG=./ansible.cfg ansible-playbook -i {REMOTE_UNLOCK_BROKER_INVENTORY} "
                    f"{playbook} -e remote_unlock_device_id={REMOTE_UNLOCK_DEVICE_ID} "
                    f"-e remote_unlock_vault_secret_value='{REMOTE_UNLOCK_VAULT_SECRET_VALUE}'"
                ),
            )
        ),
        description=description,
        interactive_prompts=REMOTE_UNLOCK_BROKER_SSH_KEY_PASSPHRASE_PROMPTS,
    )


def _broker_ping_step() -> CommandStep:
    return CommandStep(
        title="Broker Connectivity Check",
        command="\n".join(
            (
                f"cd {REMOTE_UNLOCK_ANSIBLE_PATH}",
                f"ANSIBLE_CONFIG=./ansible.cfg ansible -i {REMOTE_UNLOCK_BROKER_INVENTORY} remote_unlock_broker -m ping",
            )
        ),
        description=(
            "Verifies that the broker inventory is reachable with the current SSH key setup. "
            "Load ssh-agent first, or provide CASCADYA_BROKER_SSH_KEY_PASSPHRASE in the app environment."
        ),
        interactive_prompts=REMOTE_UNLOCK_BROKER_SSH_KEY_PASSPHRASE_PROMPTS,
    )


def _generate_certs_step() -> CommandStep:
    return CommandStep(
        title="Generate Remote Unlock Certificates",
        command="\n".join(
            (
                f"cd {REMOTE_UNLOCK_ANSIBLE_PATH}",
                f"ANSIBLE_CONFIG=./ansible.cfg ansible-playbook -i {REMOTE_UNLOCK_IPC_INVENTORY} remote-unlock-generate-certs.yml",
            )
        ),
        description=(
            "Generates the local CA and the per-device mTLS bundle consumed by the remote unlock broker."
        ),
    )


def _bootstrap_step() -> CommandStep:
    return CommandStep(
        title="Bootstrap IPC",
        command="\n".join(
            (
                f"cd {REMOTE_UNLOCK_ANSIBLE_PATH}",
                f'IPC_WG_PRIV=$(cat "{REMOTE_UNLOCK_WIREGUARD_KEY_PATH}")',
                (
                    f"ANSIBLE_CONFIG=./ansible.cfg ansible-playbook -i {REMOTE_UNLOCK_IPC_INVENTORY} -k -K "
                    f'remote-unlock-bootstrap.yml -e network_wireguard_private_key="$IPC_WG_PRIV"'
                ),
            )
        ),
        description=(
            "Installs WireGuard, remote unlock prerequisites, staged certificates, and the boot-time service."
        ),
        interactive_prompts=ANSIBLE_IPC_PASSWORD_PROMPTS,
    )


class RemoteUnlockBaselineWorkflow(BaseWorkflow):
    name = "Remote Unlock Baseline"

    def build_steps(self) -> tuple[CommandStep, ...]:
        return (
            _sync_step(),
            _ipc_playbook_step(
                "Baseline Report",
                "baseline-report.yml",
                "Collects the fresh IPC state before remote unlock changes are applied.",
            ),
        )


class RemoteUnlockGenerateCertificatesWorkflow(BaseWorkflow):
    name = "Remote Unlock Generate Certificates"

    def build_steps(self) -> tuple[CommandStep, ...]:
        return (
            _sync_step(),
            _generate_certs_step(),
        )


class RemoteUnlockBrokerPingWorkflow(BaseWorkflow):
    name = "Remote Unlock Broker Check"

    def build_steps(self) -> tuple[CommandStep, ...]:
        return (
            _sync_step(),
            _broker_ping_step(),
        )


class RemoteUnlockSeedVaultSecretWorkflow(BaseWorkflow):
    name = "Remote Unlock Seed Vault Secret"

    def build_steps(self) -> tuple[CommandStep, ...]:
        return (
            _sync_step(),
            _broker_playbook_step(
                "Seed Vault Secret",
                "remote-unlock-seed-vault-secret.yml",
                (
                    "Seeds the current LUKS passphrase in Vault for the selected device id. "
                    "Requires REMOTE_UNLOCK_BROKER_VAULT_TOKEN in the app environment."
                ),
            ),
        )


class RemoteUnlockBootstrapWorkflow(BaseWorkflow):
    name = "Remote Unlock Bootstrap"

    def build_steps(self) -> tuple[CommandStep, ...]:
        return (
            _sync_step(),
            _bootstrap_step(),
        )


class RemoteUnlockPreflightWorkflow(BaseWorkflow):
    name = "Remote Unlock Preflight"

    def build_steps(self) -> tuple[CommandStep, ...]:
        return (
            _sync_step(),
            _ipc_playbook_step(
                "Preflight",
                "remote-unlock-preflight.yml",
                "Runs the IPC-side preflight checks before validation and cutover.",
            ),
        )


class RemoteUnlockValidateWorkflow(BaseWorkflow):
    name = "Remote Unlock Validate"

    def build_steps(self) -> tuple[CommandStep, ...]:
        return (
            _sync_step(),
            _ipc_playbook_step(
                "Validate",
                "remote-unlock-validate.yml",
                "Exercises the broker challenge/unlock path before cutover.",
            ),
        )


class RemoteUnlockCutoverWorkflow(BaseWorkflow):
    name = "Remote Unlock Cutover"

    def build_steps(self) -> tuple[CommandStep, ...]:
        return (
            _sync_step(),
            _ipc_playbook_step(
                "Cutover",
                "remote-unlock-cutover.yml",
                "Switches crypttab and fstab into the remote-unlock boot configuration.",
            ),
        )


class RemoteUnlockPostRebootProofWorkflow(BaseWorkflow):
    name = "Remote Unlock Post-Reboot Proof"

    def build_steps(self) -> tuple[CommandStep, ...]:
        return (
            CommandStep(
                title="Post-Reboot Checks",
                command="\n".join(
                    (
                        "ssh -tt -o StrictHostKeyChecking=accept-new "
                        "-o PreferredAuthentications=password,keyboard-interactive "
                        "-o PubkeyAuthentication=no "
                        f"{INDUSTRIAL_PC_TARGET} "
                        "\"ip route; "
                        "sudo wg show; "
                        "findmnt /data || echo NOT_MOUNTED; "
                        "sudo systemctl status cascadya-unlock-data.service --no-pager -l; "
                        "sudo journalctl -b -u cascadya-unlock-data.service --no-pager; "
                        "sudo systemctl status systemd-cryptsetup@cascadya_data.service --no-pager -l; "
                        "sudo journalctl -b -u wg-quick@wg0.service --no-pager\""
                    )
                ),
                description=(
                    "Runs the same proof checks we used manually after reboot. Use this after the operator "
                    "has triggered a reboot from the IPC or another workflow."
                ),
                interactive_prompts=(
                    INDUSTRIAL_PC_HOST_KEY_CONFIRMATION_PROMPTS
                    + INDUSTRIAL_PC_LOGIN_PASSWORD_PROMPTS
                    + REMOTE_SUDO_PASSWORD_PROMPT
                ),
            ),
        )


class RemoteUnlockFullFlowWorkflow(BaseWorkflow):
    name = "Remote Unlock Full Flow"

    def build_steps(self) -> tuple[CommandStep, ...]:
        return (
            _sync_step(),
            _ipc_playbook_step(
                "Baseline Report",
                "baseline-report.yml",
                "Captures the fresh IPC baseline before any remote unlock changes.",
            ),
            _generate_certs_step(),
            _broker_ping_step(),
            _broker_playbook_step(
                "Seed Vault Secret",
                "remote-unlock-seed-vault-secret.yml",
                (
                    "Stores the current passphrase in Vault. Requires REMOTE_UNLOCK_BROKER_VAULT_TOKEN "
                    "and broker SSH access."
                ),
            ),
            _bootstrap_step(),
            _ipc_playbook_step(
                "Preflight",
                "remote-unlock-preflight.yml",
                "Checks transport, mounted state, and phase prerequisites before validation.",
            ),
            _ipc_playbook_step(
                "Validate",
                "remote-unlock-validate.yml",
                "Confirms the remote unlock broker path before making boot-time changes.",
            ),
            _ipc_playbook_step(
                "Cutover",
                "remote-unlock-cutover.yml",
                "Applies the remote unlock boot configuration. Reboot proof is a separate operator step.",
            ),
        )
