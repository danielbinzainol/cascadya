from workflows.base_workflow import BaseWorkflow, CommandStep
from utils.config import GIT_PUSH_COMMIT_MESSAGE, GIT_PUSH_REPO_PATH, GIT_PUSH_USER_NAME
from utils.config import GitPushTargetConfig


class GitPushWorkflow(BaseWorkflow):
    def __init__(self, target: GitPushTargetConfig) -> None:
        super().__init__()
        self.target = target
        self.name = f"Push {target.label}"

    def build_steps(self) -> tuple[CommandStep, ...]:
        command = "\n".join(
            [
                f'git remote set-url origin "{self.target.remote}"',
                f'git config --local user.name "{GIT_PUSH_USER_NAME}"',
                f'git config --local user.email "{self.target.email}"',
                'function Convert-ToGitPath([string]$Path) { '
                '$normalized = $Path -replace "\\\\", "/"; '
                'if ($normalized -match "^([A-Za-z]):(.*)$") { return "/$($matches[1].ToLower())$($matches[2])" } '
                'return $normalized }',
                '$windowsSshExe = Join-Path $env:SystemRoot "System32\\OpenSSH\\ssh.exe"',
                '$windowsSshConfig = Join-Path $env:USERPROFILE ".ssh\\config"',
                'if (-not (Test-Path $windowsSshExe)) { Write-Error "Windows OpenSSH ssh.exe was not found."; exit 1 }',
                'if (-not (Test-Path $windowsSshConfig)) { Write-Error "SSH config file $windowsSshConfig was not found."; exit 1 }',
                '$sshExe = Convert-ToGitPath $windowsSshExe',
                '$sshConfig = Convert-ToGitPath $windowsSshConfig',
                '$env:GIT_SSH_COMMAND = "$sshExe -F `"$sshConfig`" -o BatchMode=yes -o StrictHostKeyChecking=accept-new"',
                'Write-Output "[git] Using SSH command: $env:GIT_SSH_COMMAND"',
                "git remote -v",
                "git config --get user.email",
                "git branch --show-current",
                '$agentService = Get-Service -Name ssh-agent -ErrorAction SilentlyContinue',
                'if ($null -eq $agentService) { Write-Error "Windows ssh-agent service was not found."; exit 2 }',
                'if ($agentService.Status -ne "Running") { try { Start-Service ssh-agent -ErrorAction Stop; Write-Output "[git] Started ssh-agent service." } catch { Write-Error "ssh-agent is unavailable. Start the ssh-agent service first."; exit 2 } }',
                "ssh-add -l",
                'if ($LASTEXITCODE -eq 2) { Write-Error "ssh-agent is unavailable. Start the ssh-agent service first."; exit 2 } '
                'elseif ($LASTEXITCODE -eq 1) { Write-Error "No SSH identities are loaded in ssh-agent. Load your GitHub keys with ssh-add first."; exit 1 }',
                "git ls-remote --heads origin",
                "git add -A",
                "git status --short",
                "git diff --cached --quiet",
                f'if ($LASTEXITCODE -eq 1) {{ git commit -m "{GIT_PUSH_COMMIT_MESSAGE}" }} '
                "elseif ($LASTEXITCODE -gt 1) { exit $LASTEXITCODE }",
                "git push origin main",
            ]
        )
        return (
            CommandStep(
                title="Push Git",
                command=command,
                description=(
                    f"Applique l'identite Git locale pour {self.target.label}, "
                    "cree un commit si necessaire puis pousse sur origin/main."
                ),
                shell_mode="powershell",
                cwd=GIT_PUSH_REPO_PATH,
            ),
        )

