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

    @classmethod
    def get_palette_commands(cls) -> list[tuple[str, "ToggleMode"]]:
        return [("Toggle Read Mode", cls())]


@dataclass(frozen=True)
class ToggleZen:
    """Enter or exit Zen (distraction-free) mode (SPEC §7.5)."""

    @classmethod
    def get_palette_commands(cls) -> list[tuple[str, "ToggleZen"]]:
        return [("Toggle Zen Mode", cls())]
