from workflows.base_workflow import BaseWorkflow, CommandStep


class IndustrialComputerSetupProvisioner(BaseWorkflow):
    name = "Industrial Computer Setup"

    def build_steps(self) -> tuple[CommandStep, ...]:
        # Fill this workflow with the ordered Ansible playbooks once the repo paths and commands are known.
        return ()


# Backward-compatible alias while the GUI and imports move to the new naming.
AnsibleIndusProvisioner = IndustrialComputerSetupProvisioner
