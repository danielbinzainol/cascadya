from __future__ import annotations

from workflows.base_workflow import BaseWorkflow, CommandStep
from utils.config import (
    DIAGNOSTIC_SSH_KEY_RELATIVE_PATH,
    DIAGNOSTIC_VM_TARGETS,
    DiagnosticVmTargetConfig,
)


def _build_vm_diagnostic_command(target: DiagnosticVmTargetConfig) -> str:
    return "\n".join(
        [
            '$sshExe = Join-Path $env:SystemRoot "System32\\OpenSSH\\ssh.exe"',
            f'$sshKey = Join-Path $env:USERPROFILE "{DIAGNOSTIC_SSH_KEY_RELATIVE_PATH}"',
            'if (-not (Test-Path $sshExe)) { Write-Error "Windows OpenSSH ssh.exe was not found."; exit 1 }',
            'if (-not (Test-Path $sshKey)) { Write-Error "Diagnostic SSH key $sshKey was not found."; exit 1 }',
            "ssh-add -l",
            'if ($LASTEXITCODE -eq 2) { Write-Error "ssh-agent is unavailable. Start the ssh-agent service first."; exit 2 } '
            'elseif ($LASTEXITCODE -eq 1) { Write-Error "No SSH identities are loaded in ssh-agent. Load your diagnostic key with ssh-add first."; exit 1 }',
            f'Write-Output "=== {target.label} ({target.host}) ==="',
            f'& $sshExe -i $sshKey -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 {target.username}@{target.host} \'sh -lc "docker ps -a || sudo -n docker ps -a"\'',
        ]
    )


class VmDockerStatusWorkflow(BaseWorkflow):
    def __init__(self, target: DiagnosticVmTargetConfig) -> None:
        super().__init__()
        self.target = target
        self.name = f"Diagnostic {target.label}"

    def build_steps(self) -> tuple[CommandStep, ...]:
        return (
            CommandStep(
                title=f"Check {self.target.label}",
                command=_build_vm_diagnostic_command(self.target),
                description=(
                    f"Connects to {self.target.username}@{self.target.host} and runs docker ps -a, then sudo -n docker ps -a if needed."
                ),
                shell_mode="powershell",
            ),
        )


class AllVmDockerStatusWorkflow(BaseWorkflow):
    name = "Diagnostic All VMs"

    def build_steps(self) -> tuple[CommandStep, ...]:
        return tuple(
            CommandStep(
                title=f"Check {target.label}",
                command=_build_vm_diagnostic_command(target),
                description=(
                    f"Connects to {target.username}@{target.host} and runs docker ps -a, then sudo -n docker ps -a if needed."
                ),
                shell_mode="powershell",
                continue_on_error=True,
            )
            for target in DIAGNOSTIC_VM_TARGETS
        )
