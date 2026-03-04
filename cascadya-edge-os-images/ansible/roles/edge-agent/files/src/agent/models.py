from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass(order=True)
class Job:
    priority: int
    created_at: datetime = field(compare=False)
    kind: str = field(compare=False)  # "write" | "read"
    payload: Dict[str, Any] = field(compare=False)
    valid_to: Optional[datetime] = field(compare=False, default=None)
    grace_period_s: float = field(compare=False, default=0.0)
