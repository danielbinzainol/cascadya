from __future__ import annotations

from dataclasses import dataclass

from backend.config import (
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
    SYNC_WARNING_EXIT_CODES,
)
from backend.workflow import BaseWorkflow, CommandStep


@dataclass(frozen=True)
class ProvisionStepDefinition:
    key: str
    title: str
    category: str
    actual_titles: tuple[str, ...] = ()


PROVISION_STEP_ORDER = (
    ProvisionStepDefinition(
        key="sync",
        title="Synchronise workspace mirror",
        category="sync",
        actual_titles=("Synchronise WSL Mirror",),
    ),
    ProvisionStepDefinition(
        key="baseline",
        title="Collect fresh IPC baseline",
        category="baseline",
        actual_titles=("Baseline Report",),
    ),
    ProvisionStepDefinition(
        key="certs",
        title="Generate remote unlock certificates",
        category="pki",
        actual_titles=("Generate Remote Unlock Certificates",),
    ),
    ProvisionStepDefinition(
        key="broker",
        title="Verify broker connectivity",
        category="broker",
        actual_titles=("Broker Connectivity Check",),
    ),
    ProvisionStepDefinition(
        key="vault",
        title="Seed Vault unlock secret",
        category="vault",
        actual_titles=("Seed Vault Secret",),
    ),
    ProvisionStepDefinition(
        key="bootstrap",
        title="Bootstrap IPC and WireGuard",
        category="deploy",
        actual_titles=("Bootstrap IPC",),
    ),
    ProvisionStepDefinition(
        key="preflight",
        title="Run preflight checks",
        category="deploy",
        actual_titles=("Preflight",),
    ),
    ProvisionStepDefinition(
        key="validate",
        title="Validate broker unlock path",
        category="proof",
        actual_titles=("Validate",),
    ),
    ProvisionStepDefinition(
        key="cutover",
        title="Apply cutover",
        category="deploy",
        actual_titles=("Cutover",),
    ),
    ProvisionStepDefinition(
        key="reboot",
        title="Reboot IPC and wait for reconnect",
        category="manual",
    ),
    ProvisionStepDefinition(
        key="proof",
        title="Run post-reboot proof",
        category="proof",
        actual_titles=("Post-Reboot Checks",),
    ),
    ProvisionStepDefinition(
        key="finalize",
        title="Remove local TPM fallback",
        category="finalize",
        actual_titles=("Remove Local TPM Token",),
    ),
)


def _sync_step() -> CommandStep:
    return CommandStep(
        title="Synchronise WSL Mirror",
        command="\n".join((f"cd {REMOTE_UNLOCK_ANSIBLE_PATH}", "syncproject")),
        description="Refreshes the WSL ansible mirror. Known syncproject rsync warnings are tolerated.",
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


def _generate_certs_step() -> CommandStep:
    return CommandStep(
        title="Generate Remote Unlock Certificates",
        command="\n".join(
            (
                f"cd {REMOTE_UNLOCK_ANSIBLE_PATH}",
                f"ANSIBLE_CONFIG=./ansible.cfg ansible-playbook -i {REMOTE_UNLOCK_IPC_INVENTORY} remote-unlock-generate-certs.yml",
            )
        ),
        description="Generates the controller CA and the IPC client bundle used by the broker.",
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
        description="Verifies that the broker inventory is reachable before Vault seeding.",
        interactive_prompts=REMOTE_UNLOCK_BROKER_SSH_KEY_PASSPHRASE_PROMPTS,
    )


def _seed_vault_step() -> CommandStep:
    return CommandStep(
        title="Seed Vault Secret",
        command="\n".join(
            (
                f"cd {REMOTE_UNLOCK_ANSIBLE_PATH}",
                f'if [ -z "${REMOTE_UNLOCK_BROKER_VAULT_TOKEN:-}" ]; then echo "{REMOTE_UNLOCK_BROKER_VAULT_TOKEN_ENV_VAR} is not set"; exit 1; fi',
                (
                    f"ANSIBLE_CONFIG=./ansible.cfg ansible-playbook -i {REMOTE_UNLOCK_BROKER_INVENTORY} "
                    "remote-unlock-seed-vault-secret.yml "
                    f"-e remote_unlock_device_id={REMOTE_UNLOCK_DEVICE_ID} "
                    f"-e remote_unlock_vault_secret_value='{REMOTE_UNLOCK_VAULT_SECRET_VALUE}'"
                ),
            )
        ),
        description="Stores the current LUKS passphrase in Vault for the fresh IPC.",
        interactive_prompts=REMOTE_UNLOCK_BROKER_SSH_KEY_PASSPHRASE_PROMPTS,
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
                    'remote-unlock-bootstrap.yml -e network_wireguard_private_key="$IPC_WG_PRIV"'
                ),
            )
        ),
        description="Installs WireGuard, stages certs, and deploys the unlock service onto the IPC.",
        interactive_prompts=ANSIBLE_IPC_PASSWORD_PROMPTS,
    )


def _post_reboot_proof_step() -> CommandStep:
    return CommandStep(
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
        description="Runs the final reboot proof checks directly against the IPC over SSH.",
        interactive_prompts=(
            INDUSTRIAL_PC_HOST_KEY_CONFIRMATION_PROMPTS
            + INDUSTRIAL_PC_LOGIN_PASSWORD_PROMPTS
            + REMOTE_SUDO_PASSWORD_PROMPT
        ),
    )


def _remove_local_tpm_step() -> CommandStep:
    return _ipc_playbook_step(
        "Remove Local TPM Token",
        "remote-unlock-remove-local-tpm.yml",
        "Removes the local TPM fallback after reboot proof passes.",
    )


class RemoteUnlockPreRebootWorkflow(BaseWorkflow):
    name = "Fresh IPC Provisioning"

    def build_steps(self) -> tuple[CommandStep, ...]:
        return (
            _sync_step(),
            _ipc_playbook_step(
                "Baseline Report",
                "baseline-report.yml",
                "Captures the fresh IPC baseline before any provisioning change.",
            ),
            _generate_certs_step(),
            _broker_ping_step(),
            _seed_vault_step(),
            _bootstrap_step(),
            _ipc_playbook_step(
                "Preflight",
                "remote-unlock-preflight.yml",
                "Checks that the IPC and broker are ready for validation.",
            ),
            _ipc_playbook_step(
                "Validate",
                "remote-unlock-validate.yml",
                "Exercises the broker challenge path before cutover.",
            ),
            _ipc_playbook_step(
                "Cutover",
                "remote-unlock-cutover.yml",
                "Applies the boot-time remote unlock configuration.",
            ),
        )


class RemoteUnlockPostRebootWorkflow(BaseWorkflow):
    name = "Post-Reboot Provisioning Proof"

    def build_steps(self) -> tuple[CommandStep, ...]:
        return (
            _post_reboot_proof_step(),
            _remove_local_tpm_step(),
        )
