from workflows.base_workflow import BaseWorkflow, CommandStep
from utils.config import MODBUS_SIMULATOR_STEPS


class ModbusSimUpdater(BaseWorkflow):
    name = "Update Modbus Simulator"

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
            for step in MODBUS_SIMULATOR_STEPS
        )
