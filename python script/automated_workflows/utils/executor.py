from __future__ import annotations

import base64
import json
import os
import re
import shlex
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence, TextIO

from utils.config import WSL_DISTRO
from utils.prompts import InteractivePrompt


OutputCallback = Callable[[str], None]


@dataclass(frozen=True)
class CommandResult:
    command: str
    return_code: int
    duration_seconds: float

    @property
    def succeeded(self) -> bool:
        return self.return_code == 0


class ShellExecutor:
    """Runs shell commands and streams stdout/stderr line by line."""

    def __init__(
        self,
        use_wsl: bool | None = None,
        wsl_distro: str = WSL_DISTRO,
    ) -> None:
        self.use_wsl = os.name == "nt" if use_wsl is None else use_wsl
        self.wsl_distro = wsl_distro

    def run(
        self,
        command: str,
        output_callback: OutputCallback,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        interactive_prompts: Sequence[InteractivePrompt] = (),
        shell_mode: str | None = None,
    ) -> CommandResult:
        start_time = time.perf_counter()
        prepared_command = self._prepare_command(command, interactive_prompts, shell_mode)
        invocation = self._build_invocation(prepared_command, shell_mode)

        output_callback(f"$ {command}")

        try:
            process = subprocess.Popen(
                invocation,
                cwd=cwd,
                env={**os.environ, **env} if env else None,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as exc:
            output_callback(f"[executor] Failed to start command: {exc}")
            return CommandResult(
                command=command,
                return_code=1,
                duration_seconds=time.perf_counter() - start_time,
            )

        prompt_responder = _PromptResponder(
            prompts=()
            if self._should_use_wsl_pty_runner(interactive_prompts, shell_mode)
            else interactive_prompts,
            stdin=process.stdin,
            output_callback=output_callback,
        )
        readers = [
            threading.Thread(
                target=self._read_stream,
                args=(process.stdout, "stdout", output_callback, prompt_responder),
                daemon=True,
            ),
            threading.Thread(
                target=self._read_stream,
                args=(process.stderr, "stderr", output_callback, prompt_responder),
                daemon=True,
            ),
        ]

        for reader in readers:
            reader.start()

        for reader in readers:
            reader.join()

        return_code = process.wait()
        duration = time.perf_counter() - start_time
        output_callback(
            f"[executor] Command finished with exit code {return_code} in {duration:.2f}s"
        )
        return CommandResult(
            command=command,
            return_code=return_code,
            duration_seconds=duration,
        )

    def _build_invocation(self, command: str, shell_mode: str | None = None) -> list[str]:
        if shell_mode == "powershell":
            if os.name == "nt":
                powershell = os.path.join(
                    os.environ.get("SystemRoot", r"C:\Windows"),
                    "System32",
                    "WindowsPowerShell",
                    "v1.0",
                    "powershell.exe",
                )
                return [powershell, "-NoProfile", "-Command", command]
            return ["pwsh", "-NoProfile", "-Command", command]
        if self.use_wsl:
            return ["wsl.exe", "-d", self.wsl_distro, "--", "bash", "-lic", command]
        return ["bash", "-lic", command]

    def _prepare_command(
        self,
        command: str,
        interactive_prompts: Sequence[InteractivePrompt],
        shell_mode: str | None = None,
    ) -> str:
        if self._should_use_wsl_pty_runner(interactive_prompts, shell_mode):
            return self._wrap_interactive_wsl_command(command, interactive_prompts)
        return command

    def _should_use_wsl_pty_runner(
        self,
        interactive_prompts: Sequence[InteractivePrompt],
        shell_mode: str | None = None,
    ) -> bool:
        return self.use_wsl and shell_mode is None and bool(interactive_prompts)

    def _wrap_interactive_wsl_command(
        self,
        command: str,
        interactive_prompts: Sequence[InteractivePrompt],
    ) -> str:
        payload = {
            "command": command,
            "prompts": [
                {
                    "pattern": prompt.pattern,
                    "response": prompt.response,
                    "description": prompt.description,
                    "ignore_case": prompt.ignore_case,
                }
                for prompt in interactive_prompts
            ],
        }
        encoded_payload = base64.urlsafe_b64encode(
            json.dumps(payload).encode("utf-8")
        ).decode("ascii")
        runner_path = self._windows_path_to_wsl(Path(__file__).with_name("wsl_pty_runner.py"))
        return f"python3 {shlex.quote(runner_path)} {shlex.quote(encoded_payload)}"

    @staticmethod
    def _windows_path_to_wsl(path: Path) -> str:
        drive = path.drive.rstrip(":").lower()
        suffix = path.as_posix().split(":", 1)[1]
        return f"/mnt/{drive}{suffix}"

    @staticmethod
    def _read_stream(
        stream: TextIO | None,
        stream_name: str,
        output_callback: OutputCallback,
        prompt_responder: "_PromptResponder",
    ) -> None:
        if stream is None:
            return

        line_buffer: list[str] = []
        prompt_buffer = ""

        try:
            while True:
                char = stream.read(1)
                if char == "":
                    break

                line_buffer.append(char)
                prompt_buffer = (prompt_buffer + char)[-512:]

                if prompt_responder.maybe_respond(stream_name, prompt_buffer):
                    prompt_buffer = ""

                if char == "\n":
                    message = "".join(line_buffer).rstrip("\r\n")
                    if message:
                        prefix = "[stderr] " if stream_name == "stderr" else ""
                        output_callback(f"{prefix}{message}")
                    line_buffer.clear()
        finally:
            if line_buffer:
                message = "".join(line_buffer).rstrip("\r\n")
                if message:
                    prefix = "[stderr] " if stream_name == "stderr" else ""
                    output_callback(f"{prefix}{message}")
            stream.close()


class _PromptResponder:
    def __init__(
        self,
        prompts: Sequence[InteractivePrompt],
        stdin: TextIO | None,
        output_callback: OutputCallback,
    ) -> None:
        self._prompts = list(prompts)
        self._stdin = stdin
        self._output_callback = output_callback
        self._lock = threading.Lock()

    def maybe_respond(self, stream_name: str, buffer: str) -> bool:
        with self._lock:
            if not self._prompts or self._stdin is None:
                return False

            for index, prompt in enumerate(self._prompts):
                if prompt.stream != "any" and prompt.stream != stream_name:
                    continue

                flags = re.DOTALL
                if prompt.ignore_case:
                    flags |= re.IGNORECASE
                if not re.search(prompt.pattern, buffer, flags):
                    continue

                try:
                    self._stdin.write(prompt.response + "\n")
                    self._stdin.flush()
                except (BrokenPipeError, OSError) as exc:
                    self._output_callback(
                        f"[executor] Failed to answer interactive prompt: {exc}"
                    )
                    return False

                label = prompt.description or prompt.pattern
                self._output_callback(f"[executor] Responded to interactive prompt: {label}")
                self._prompts.pop(index)
                return True

            return False
