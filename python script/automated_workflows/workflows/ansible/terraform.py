from workflows.base_workflow import BaseWorkflow, CommandStep
from utils.config import TERRAFORM_DEV_ENV_PATH


class _BaseTerraformWorkflow(BaseWorkflow):
    name = "Terraform"
    script_name = ""
    step_description = ""

    def build_steps(self) -> tuple[CommandStep, ...]:
        return (
            CommandStep(
                title="Terraform",
                command=self._build_command(),
                description=self.step_description,
            ),
        )

    def _build_command(self) -> str:
        return "\n".join(
            [
                f"cd {TERRAFORM_DEV_ENV_PATH}",
                "chmod +x plan_terraform.sh apply_terraform.sh",
                f"./{self.script_name}",
            ]
        )


class TerraformPlanWorkflow(_BaseTerraformWorkflow):
    name = "Terraform Plan"
    script_name = "plan_terraform.sh"
    step_description = "Runs the Terraform plan wrapper script from the dev environment."


class TerraformApplyWorkflow(_BaseTerraformWorkflow):
    name = "Terraform Apply"
    script_name = "apply_terraform.sh"
    step_description = "Runs the Terraform apply wrapper script from the dev environment."
