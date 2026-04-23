from __future__ import annotations

import base64
import errno
import json
import os
import re
import select
import sys
from typing import Any


def _load_payload(encoded_payload: str) -> dict[str, Any]:
    padding = "=" * (-len(encoded_payload) % 4)
    data = base64.urlsafe_b64decode(encoded_payload + padding)
    return json.loads(data.decode("utf-8"))


def _compile_prompt(prompt: dict[str, Any]) -> re.Pattern[str]:
    flags = re.DOTALL
    if prompt.get("ignore_case", True):
        flags |= re.IGNORECASE
    return re.compile(prompt["pattern"], flags)


def main() -> int:
    import pty

    if len(sys.argv) != 2:
        print("Usage: wsl_pty_runner.py <base64-payload>", file=sys.stderr)
        return 2

    payload = _load_payload(sys.argv[1])
    prompts = payload.get("prompts", [])
    compiled_prompts = [
        {
            **prompt,
            "compiled": _compile_prompt(prompt),
        }
        for prompt in prompts
    ]

    child_pid, master_fd = pty.fork()
    if child_pid == 0:
        os.execvp("bash", ["bash", "-lic", payload["command"]])

    prompt_buffer = ""
    child_exit_code: int | None = None

    try:
        while True:
            ready, _, _ = select.select([master_fd], [], [], 0.1)
            if ready:
                try:
                    chunk = os.read(master_fd, 1024)
                except OSError as exc:
                    if exc.errno == errno.EIO:
                        break
                    raise

                if not chunk:
                    continue

                text = chunk.decode("utf-8", errors="replace")
                sys.stdout.write(text)
                sys.stdout.flush()

                prompt_buffer = (prompt_buffer + text)[-1024:]
                for index, prompt in enumerate(compiled_prompts):
                    if not prompt["compiled"].search(prompt_buffer):
                        continue

                    os.write(master_fd, (prompt["response"] + "\n").encode("utf-8"))
                    label = prompt.get("description") or prompt["pattern"]
                    sys.stdout.write(
                        f"\n[executor] Responded to interactive prompt: {label}\n"
                    )
                    sys.stdout.flush()
                    compiled_prompts.pop(index)
                    prompt_buffer = ""
                    break

            waited_pid, status = os.waitpid(child_pid, os.WNOHANG)
            if waited_pid == child_pid:
                child_exit_code = os.waitstatus_to_exitcode(status)
                if not ready:
                    break
    finally:
        try:
            os.close(master_fd)
        except OSError:
            pass

    if child_exit_code is not None:
        return child_exit_code

    _, status = os.waitpid(child_pid, 0)
    return os.waitstatus_to_exitcode(status)


if __name__ == "__main__":
    raise SystemExit(main())
