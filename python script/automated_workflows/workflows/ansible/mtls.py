from workflows.base_workflow import BaseWorkflow, CommandStep
from utils.config import (
    ANSIBLE_MTLS_CERTS_PATH,
    LOCAL_WSL_SUDO_PASSWORD_PROMPT,
    VAULT_ADDR,
    VAULT_TOKEN_ENV_VAR,
)


class _BaseMtlsCertificatesWorkflow(BaseWorkflow):
    name = "mTLS Certificates"
    playbook = ""
    extra_args = ""
    preamble: tuple[str, ...] = ()
    interactive_prompts = ()
    step_description = ""

    def build_steps(self) -> tuple[CommandStep, ...]:
        return (
            CommandStep(
                title="Ansible Playbook",
                command=self._build_command(),
                description=self.step_description,
                interactive_prompts=self.interactive_prompts,
            ),
        )

    def _build_command(self) -> str:
        lines = [
            f"cd {ANSIBLE_MTLS_CERTS_PATH}",
            *self.preamble,
            f'export VAULT_ADDR="{VAULT_ADDR}"',
            f'export VAULT_TOKEN="${{{VAULT_TOKEN_ENV_VAR}:?{VAULT_TOKEN_ENV_VAR} is not set}}"',
            "export ANSIBLE_ROLES_PATH=./roles",
            f"ansible-playbook -i inventory/hosts.ini {self.playbook}{self.extra_args}",
        ]
        return "\n".join(lines)


class BrokerVmServerCertificatesWorkflow(_BaseMtlsCertificatesWorkflow):
    name = "Broker VM Server Certificates"
    playbook = "playbooks/regen_broker_server.yml"
    step_description = (
        "Regenerates the broker-side mTLS certificates from the ansible-mosquitto-certificats repository."
    )


class EdgeComputerClientCertificatesWorkflow(_BaseMtlsCertificatesWorkflow):
    name = "Edge Computer Client Certificates"
    playbook = "playbooks/regen_edge_clients.yml"
    extra_args = " --limit edge-local"
    preamble = ("sudo rm -f /opt/mosquitto/clients/client.crt",)
    interactive_prompts = LOCAL_WSL_SUDO_PASSWORD_PROMPT
    step_description = (
        "Deletes the current local edge client certificate, then regenerates it with the edge-local limit."
    )


class UserClientCertificatesWorkflow(_BaseMtlsCertificatesWorkflow):
    name = "User Client Certificates"
    playbook = "playbooks/regen_app_cert_client.yml"
    step_description = "Regenerates the user-facing application client certificate."
