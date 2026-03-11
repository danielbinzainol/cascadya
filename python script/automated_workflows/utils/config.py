import os
from dataclasses import dataclass

from utils.prompts import InteractivePrompt


APP_TITLE = "Cascadya Admin Tool"
APP_GEOMETRY = "1180x760"
MIN_WINDOW_SIZE = (960, 640)
LOG_POLL_INTERVAL_MS = 100
WORKFLOW_POLL_INTERVAL_MS = 250
WSL_DISTRO = "ubuntu"
RSYNC_WARNING_EXIT_CODES = frozenset({24})
SSH_PASSWORD = os.environ.get("CASCADYA_SSH_PASSWORD", "admin")
SUDO_PASSWORD = os.environ.get("CASCADYA_SUDO_PASSWORD", SSH_PASSWORD)
WSL_SUDO_PASSWORD = os.environ.get("CASCADYA_WSL_SUDO_PASSWORD", SUDO_PASSWORD)
PASSWORD_PROMPT_PATTERN = r"password.*:\s*$"
HOST_KEY_PROMPT_PATTERN = r"are you sure you want to continue connecting.*\?\s*$"
SSH_CLIENT_OPTIONS = (
    "-o StrictHostKeyChecking=accept-new "
    "-o PreferredAuthentications=password,keyboard-interactive "
    "-o PubkeyAuthentication=no"
)

INDUSTRIAL_PC_TARGET = "cascadya@192.168.10.109"
JUMP_HOST = INDUSTRIAL_PC_TARGET
MODBUS_SIM_TARGET = "cascadya@192.168.50.2"
INDUSTRIAL_PC_SOURCE = (
    "~/git/cascadya-project/Mosquitto\\ Scripts/Full\\ System/Industrial\\ PC/"
)
INDUSTRIAL_PC_DESTINATION = "~/python_scripts/"
INDUSTRIAL_PC_GATEWAY_SERVICE = "cascadya-gateway.service"
INDUSTRIAL_PC_TELEMETRY_SERVICE = "cascadya-telemetry.service"
MODBUS_SIM_SOURCE = (
    "~/git/cascadya-project/Mosquitto\\ Scripts/Full\\ System/Modbus\\ Simulator/"
)
MODBUS_SIM_DESTINATION = "~/simulator_sbc/"
BROKER_VM_TARGET = "ubuntu@51.15.64.139"
BROKER_VM_SOURCE = "~/git/cascadya-project/Mosquitto\\ Scripts/Full\\ System/VM\\ Broker/"
BROKER_VM_DESTINATION = "~/nats_bridge/"
BROKER_VM_SSH_KEY = "~/.ssh/id_ed25519"
BROKER_VM_PASSWORD = os.environ.get("CASCADYA_BROKER_VM_PASSWORD", "")
GIT_PUSH_REPO_PATH = r"C:\Users\Daniel BIN ZAINOL\Desktop\GIT - Daniel"
GIT_PUSH_COMMIT_MESSAGE = "update project"
GIT_PUSH_USER_NAME = "Daniel Bin Zainol"
GIT_ENTERPRISE_REMOTE = "git@github-pro:cascadya/C-Switch.git"
GIT_ENTERPRISE_EMAIL = "Daniel.BINZAINOL@cascadya.com"
GIT_PERSONAL_REMOTE = os.environ.get(
    "CASCADYA_GIT_PERSONAL_REMOTE",
    "git@github-perso:danielbinzainol/cascadya.git",
)
GIT_PERSONAL_EMAIL = "danielbinzainol@gmail.com"
ANSIBLE_MTLS_CERTS_PATH = "~/git/cascadya-project/playbook_ansible/ansible-mosquitto-certificats"
TERRAFORM_DEV_ENV_PATH = "~/git/cascadya-project/Infra-MVP/infrastructure/environments/dev/"
VAULT_ADDR = os.environ.get("CASCADYA_VAULT_ADDR", "https://secrets.cascadya.com")
VAULT_TOKEN_ENV_VAR = "CASCADYA_VAULT_TOKEN"
DIAGNOSTIC_SSH_KEY_RELATIVE_PATH = ".ssh\\id_ed25519"


@dataclass(frozen=True)
class WorkflowStepConfig:
    title: str
    command: str
    description: str
    accepted_exit_codes: frozenset[int] = frozenset({0})
    interactive_prompts: tuple[InteractivePrompt, ...] = ()
    shell_mode: str | None = None
    cwd: str | None = None
    continue_on_error: bool = False


@dataclass(frozen=True)
class GitPushTargetConfig:
    label: str
    remote: str
    email: str


@dataclass(frozen=True)
class DiagnosticVmTargetConfig:
    label: str
    host: str
    username: str = "ubuntu"


SSH_HOST_KEY_CONFIRMATION_PROMPTS = (
    InteractivePrompt(
        pattern=HOST_KEY_PROMPT_PATTERN,
        response="yes",
        description="jump host key confirmation",
    ),
    InteractivePrompt(
        pattern=HOST_KEY_PROMPT_PATTERN,
        response="yes",
        description="simulator host key confirmation",
    ),
)

SSH_LOGIN_PASSWORD_PROMPTS = (
    InteractivePrompt(
        pattern=PASSWORD_PROMPT_PATTERN,
        response=SSH_PASSWORD,
        description="jump host password",
    ),
    InteractivePrompt(
        pattern=PASSWORD_PROMPT_PATTERN,
        response=SSH_PASSWORD,
        description="simulator password",
    ),
)

INDUSTRIAL_PC_HOST_KEY_CONFIRMATION_PROMPTS = (
    InteractivePrompt(
        pattern=HOST_KEY_PROMPT_PATTERN,
        response="yes",
        description="industrial pc key confirmation",
    ),
)

INDUSTRIAL_PC_LOGIN_PASSWORD_PROMPTS = (
    InteractivePrompt(
        pattern=PASSWORD_PROMPT_PATTERN,
        response=SSH_PASSWORD,
        description="industrial pc password",
    ),
)

REMOTE_SUDO_PASSWORD_PROMPT = (
    InteractivePrompt(
        pattern=PASSWORD_PROMPT_PATTERN,
        response=SUDO_PASSWORD,
        description="remote sudo password",
    ),
)

BROKER_VM_HOST_KEY_CONFIRMATION_PROMPTS = (
    InteractivePrompt(
        pattern=HOST_KEY_PROMPT_PATTERN,
        response="yes",
        description="broker vm key confirmation",
    ),
)

BROKER_VM_LOGIN_PASSWORD_PROMPTS = (
    InteractivePrompt(
        pattern=PASSWORD_PROMPT_PATTERN,
        response=BROKER_VM_PASSWORD,
        description="broker vm password",
    ),
)

LOCAL_WSL_SUDO_PASSWORD_PROMPT = (
    InteractivePrompt(
        pattern=PASSWORD_PROMPT_PATTERN,
        response=WSL_SUDO_PASSWORD,
        description="local WSL sudo password",
    ),
)

GIT_PUSH_TARGETS = (
    GitPushTargetConfig(
        label="GitHub Entreprise",
        remote=GIT_ENTERPRISE_REMOTE,
        email=GIT_ENTERPRISE_EMAIL,
    ),
    GitPushTargetConfig(
        label="GitHub Perso",
        remote=GIT_PERSONAL_REMOTE,
        email=GIT_PERSONAL_EMAIL,
    ),
)

DIAGNOSTIC_VM_TARGETS = (
    DiagnosticVmTargetConfig(label="Vault", host="51.15.36.65"),
    DiagnosticVmTargetConfig(label="Thingsboard", host="51.15.115.203"),
    DiagnosticVmTargetConfig(label="VM Broker", host="51.15.64.139"),
    DiagnosticVmTargetConfig(label="Wireguard", host="51.15.84.140"),
    DiagnosticVmTargetConfig(label="Monitoring", host="51.15.83.22"),
)


MODBUS_SIMULATOR_STEPS = (
    WorkflowStepConfig(
        title="Synchronisation locale",
        command="syncproject",
        description="Recopie les fichiers sources dans l'environnement WSL local.",
        accepted_exit_codes=RSYNC_WARNING_EXIT_CODES | {0},
    ),
    WorkflowStepConfig(
        title="Synchronisation distante",
        command=(
            f'rsync -avz -e "ssh {SSH_CLIENT_OPTIONS} -J {JUMP_HOST}" '
            f"{MODBUS_SIM_SOURCE} "
            f"{MODBUS_SIM_TARGET}:{MODBUS_SIM_DESTINATION}"
        ),
        description="Envoie les scripts du simulateur vers la cible distante via le jump host.",
        accepted_exit_codes=RSYNC_WARNING_EXIT_CODES | {0},
        interactive_prompts=SSH_HOST_KEY_CONFIRMATION_PROMPTS + SSH_LOGIN_PASSWORD_PROMPTS,
    ),
    WorkflowStepConfig(
        title="Redemarrage du service",
        command=(
            f'ssh -tt {SSH_CLIENT_OPTIONS} -J {JUMP_HOST} {MODBUS_SIM_TARGET} '
            '"sudo systemctl stop modbus-serveur.service '
            "&& sudo systemctl start modbus-serveur.service "
            '&& sudo env SYSTEMD_COLORS=0 SYSTEMD_PAGER=cat systemctl --no-pager --full status modbus-serveur.service"'
        ),
        description="Redemarre le service SystemD du simulateur puis affiche son statut.",
        interactive_prompts=SSH_HOST_KEY_CONFIRMATION_PROMPTS
        + SSH_LOGIN_PASSWORD_PROMPTS
        + REMOTE_SUDO_PASSWORD_PROMPT,
    ),
)

BROKER_VM_STEPS = (
    WorkflowStepConfig(
        title="Synchronisation locale",
        command="syncproject",
        description="Recopie les fichiers sources dans l'environnement WSL local.",
        accepted_exit_codes=RSYNC_WARNING_EXIT_CODES | {0},
    ),
    WorkflowStepConfig(
        title="Synchronisation distante",
        command=(
            f'rsync -avz -e "ssh -i {BROKER_VM_SSH_KEY} -o StrictHostKeyChecking=accept-new" '
            f"{BROKER_VM_SOURCE} "
            f"{BROKER_VM_TARGET}:{BROKER_VM_DESTINATION}"
        ),
        description="Envoie les fichiers du VM Broker vers la cible distante.",
        accepted_exit_codes=RSYNC_WARNING_EXIT_CODES | {0},
        interactive_prompts=BROKER_VM_HOST_KEY_CONFIRMATION_PROMPTS + BROKER_VM_LOGIN_PASSWORD_PROMPTS,
    ),
)

def build_industrial_pc_steps(service_name: str) -> tuple[WorkflowStepConfig, ...]:
    return (
        WorkflowStepConfig(
            title="Synchronisation locale",
            command="syncproject",
            description="Recopie les fichiers sources dans l'environnement WSL local.",
            accepted_exit_codes=RSYNC_WARNING_EXIT_CODES | {0},
        ),
        WorkflowStepConfig(
            title="Synchronisation distante",
            command=(
                f'rsync -avz -e "ssh {SSH_CLIENT_OPTIONS}" '
                f"{INDUSTRIAL_PC_SOURCE} "
                f"{INDUSTRIAL_PC_TARGET}:{INDUSTRIAL_PC_DESTINATION}"
            ),
            description="Envoie les scripts Python vers l'Industrial PC.",
            accepted_exit_codes=RSYNC_WARNING_EXIT_CODES | {0},
            interactive_prompts=INDUSTRIAL_PC_HOST_KEY_CONFIRMATION_PROMPTS
            + INDUSTRIAL_PC_LOGIN_PASSWORD_PROMPTS,
        ),
        WorkflowStepConfig(
            title="Redemarrage du service",
            command=(
                f'ssh -tt {SSH_CLIENT_OPTIONS} {INDUSTRIAL_PC_TARGET} '
                f'"sudo systemctl stop {service_name} '
                f"&& sudo systemctl start {service_name} "
                f'&& sudo env SYSTEMD_COLORS=0 SYSTEMD_PAGER=cat systemctl --no-pager --full status {service_name}"'
            ),
            description=f"Redemarre le service {service_name} de l'Industrial PC puis affiche son statut.",
            interactive_prompts=INDUSTRIAL_PC_HOST_KEY_CONFIRMATION_PROMPTS
            + INDUSTRIAL_PC_LOGIN_PASSWORD_PROMPTS
            + REMOTE_SUDO_PASSWORD_PROMPT,
        ),
    )


INDUSTRIAL_PC_GATEWAY_STEPS = build_industrial_pc_steps(INDUSTRIAL_PC_GATEWAY_SERVICE)
INDUSTRIAL_PC_TELEMETRY_STEPS = build_industrial_pc_steps(INDUSTRIAL_PC_TELEMETRY_SERVICE)

