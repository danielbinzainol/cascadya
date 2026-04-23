from workflows.base_workflow import BaseWorkflow, CommandStep
from utils.config import BROKER_VM_STEPS


class BrokerUpdater(BaseWorkflow):
    name = "Update Broker"

    def build_steps(self) -> tuple[CommandStep, ...]:
        return tuple(
            CommandStep(
                title=step.title,
                command=step.command,
                description=step.description,
                accepted_exit_codes=step.accepted_exit_codes,
                interactive_prompts=step.interactive_prompts,
                shell_mode=step.shell_mode,
                cwd=step.cwd,
                continue_on_error=step.continue_on_error,
            )
            for step in BROKER_VM_STEPS
        )
