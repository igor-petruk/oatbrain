from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ToggleMode:
    """Flip between editor and preview mode for the focused tab."""

    tab_id: str = ""

    @classmethod
    def get_palette_commands(cls) -> list[tuple[str, "ToggleMode"]]:
        return [("Toggle Preview Mode", cls())]


@dataclass(frozen=True)
class ToggleZen:
    """Enter or exit Zen (distraction-free) mode (SPEC §7.5)."""

    @classmethod
    def get_palette_commands(cls) -> list[tuple[str, "ToggleZen"]]:
        return [("Toggle Zen Mode", cls())]


@dataclass(frozen=True)
class RefreshFile:
    """Reload the current file from disk, discarding unsaved changes."""

    @classmethod
    def get_palette_commands(cls) -> list[tuple[str, "RefreshFile"]]:
        return [("Refresh Current File", cls())]


@dataclass(frozen=True)
class NewTab:
    """Open a new tab (duplicate of focused) in the focused group."""

    @classmethod
    def get_palette_commands(cls) -> list[tuple[str, "NewTab"]]:
        return [("New Tab", cls())]


@dataclass(frozen=True)
class NewNote:
    """Create a new unsaved note in the focused group."""

    target_dir: Optional[str] = None

    @classmethod
    def get_palette_commands(cls) -> list[tuple[str, "NewNote"]]:
        return [("New Note", cls())]


@dataclass(frozen=True)
class CloseTab:
    """Close the focused tab."""

    @classmethod
    def get_palette_commands(cls) -> list[tuple[str, "CloseTab"]]:
        return [("Close Tab", cls())]


@dataclass(frozen=True)
class SplitGroupRight:
    """Move the focused tab into a new group to the right."""

    @classmethod
    def get_palette_commands(cls) -> list[tuple[str, "SplitGroupRight"]]:
        return [("Split Group Right", cls())]
