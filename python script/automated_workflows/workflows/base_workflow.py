from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Sequence

from utils.executor import ShellExecutor
from utils.prompts import InteractivePrompt


ConsoleCallback = Callable[[str], None]


@dataclass(frozen=True)
class CommandStep:
    title: str
    command: str
    description: str = ""
    accepted_exit_codes: frozenset[int] = frozenset({0})
    interactive_prompts: tuple[InteractivePrompt, ...] = ()
    shell_mode: str | None = None
    cwd: str | None = None
    continue_on_error: bool = False


class BaseWorkflow(ABC):
    """Base class for sequential workflows.

    To add a new workflow:
    1. Create a class inheriting from BaseWorkflow.
    2. Implement build_steps() and return CommandStep objects in execution order.
    3. Register the workflow in gui/views/update_view.py to expose a new button.
    """

    name = "Unnamed Workflow"

    def __init__(self, executor: ShellExecutor | None = None) -> None:
        self.executor = executor or ShellExecutor()
        self._state_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._is_running = False
        self.last_success: bool | None = None

    @property
    def is_running(self) -> bool:
        with self._state_lock:
            return self._is_running

    def run(self, console_callback: ConsoleCallback) -> bool:
        with self._state_lock:
            if self._is_running:
                console_callback(f"[workflow] '{self.name}' is already running.")
                return False

            self._is_running = True
            self.last_success = None
            self._thread = threading.Thread(
                target=self._execute,
                args=(console_callback,),
                daemon=True,
            )
            self._thread.start()
            return True

    def _execute(self, console_callback: ConsoleCallback) -> None:
        success = False
        try:
            steps = list(self.build_steps())
            if not steps:
                console_callback(f"[workflow] No steps configured for '{self.name}'.")
                success = False
                return

            console_callback("")
            console_callback(f"=== {self.name} ===")
            had_step_errors = False

            for index, step in enumerate(steps, start=1):
                console_callback(f"[step {index}/{len(steps)}] {step.title}")
                if step.description:
                    console_callback(f"[info] {step.description}")

                result = self.executor.run(
                    step.command,
                    output_callback=console_callback,
                    interactive_prompts=step.interactive_prompts,
                    shell_mode=step.shell_mode,
                    cwd=step.cwd,
                )
                if result.return_code not in step.accepted_exit_codes:
                    if step.continue_on_error:
                        had_step_errors = True
                        console_callback(
                            f"[workflow] Step '{step.title}' failed with exit code {result.return_code}, continuing."
                        )
                        continue
                    console_callback(
                        f"[workflow] Stopped at step '{step.title}' due to exit code {result.return_code}."
                    )
                    success = False
                    break

                if result.return_code == 0:
                    console_callback(f"[workflow] Step '{step.title}' completed successfully.")
                else:
                    console_callback(
                        f"[workflow] Step '{step.title}' completed with tolerated warning exit code {result.return_code}."
                    )
            else:
                success = not had_step_errors
                if had_step_errors:
                    console_callback(
                        f"[workflow] '{self.name}' completed with one or more step errors."
                    )
                else:
                    console_callback(f"[workflow] '{self.name}' completed successfully.")
        except Exception as exc:
            console_callback(f"[workflow] Unexpected error in '{self.name}': {exc}")
            success = False
        finally:
            self.last_success = success
            with self._state_lock:
                self._is_running = False

    @abstractmethod
    def build_steps(self) -> Sequence[CommandStep]:
        """Return the ordered list of shell commands executed by the workflow."""
