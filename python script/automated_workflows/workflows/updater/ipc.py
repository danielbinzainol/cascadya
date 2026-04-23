from workflows.base_workflow import BaseWorkflow, CommandStep
from utils.config import INDUSTRIAL_PC_GATEWAY_STEPS, INDUSTRIAL_PC_TELEMETRY_STEPS


def _build_steps(step_configs: tuple) -> tuple[CommandStep, ...]:
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
        for step in step_configs
    )


class GatewayModbusSbcUpdater(BaseWorkflow):
    name = "Update IPC Gateway Modbus SBC"

    def build_steps(self) -> tuple[CommandStep, ...]:
        return _build_steps(INDUSTRIAL_PC_GATEWAY_STEPS)


class TelemetryPublisherUpdater(BaseWorkflow):
    name = "Update IPC Telemetry Publisher"

    def build_steps(self) -> tuple[CommandStep, ...]:
        return _build_steps(INDUSTRIAL_PC_TELEMETRY_STEPS)
