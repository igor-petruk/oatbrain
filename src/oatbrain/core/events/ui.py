from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class WordCountChanged:
    count: int
    sender_id: Optional[int] = None


@dataclass(frozen=True)
class DirtyStateChanged:
    dirty: bool
    sender_id: Optional[int] = None


@dataclass(frozen=True)
class StatusMessageRequested:
    message: str
    timeout_ms: Optional[int] = None
