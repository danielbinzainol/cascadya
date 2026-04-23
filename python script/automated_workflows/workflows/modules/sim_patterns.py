from workflows.base_workflow import BaseWorkflow, CommandStep


class SimulationPatternsWorkflow(BaseWorkflow):
    name = "Modules Simulation Patterns"

    def build_steps(self) -> tuple[CommandStep, ...]:
        # Add module-specific simulation variants here when their command sequence is defined.
        return ()
