from dataclasses import dataclass


@dataclass(frozen=True)
class UpdateWordCount:
    count: int


@dataclass(frozen=True)
class SetDirty:
    dirty: bool


@dataclass(frozen=True)
class ToggleMode:
    """Flip between source and read (preview) mode (SPEC §10.2)."""

