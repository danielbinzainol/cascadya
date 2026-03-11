from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InteractivePrompt:
    pattern: str
    response: str
    description: str = ""
    stream: str = "any"
    ignore_case: bool = True
