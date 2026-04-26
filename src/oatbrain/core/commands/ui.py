from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ToggleTree:
    """Toggle file tree visibility."""

    @classmethod
    def get_palette_commands(cls) -> list[tuple[str, "ToggleTree"]]:
        return [("Toggle File Tree", cls())]


@dataclass(frozen=True)
class ToggleTerminal:
    """Toggle terminal visibility."""

    @classmethod
    def get_palette_commands(cls) -> list[tuple[str, "ToggleTerminal"]]:
        return [("Toggle Terminal", cls())]


@dataclass(frozen=True)
class RestartTerminal:
    """Restart the terminal session and clear the buffer."""

    @classmethod
    def get_palette_commands(cls) -> list[tuple[str, "RestartTerminal"]]:
        return [("Restart Terminal", cls())]


@dataclass(frozen=True)
class SendToTerminal:
    """Send text to the terminal stdin."""

    text: str
    execute: bool = False


@dataclass(frozen=True)
class DismissMermaidWarning:
    """Dismiss the mermaid.js fetch failure warning."""


@dataclass(frozen=True)
class SetTreeExpanded:
    """Update the expansion state of a directory in the tree."""

    path: str
    is_expanded: bool


@dataclass(frozen=True)
class ProcessFile:
    """Process a file (e.g. send to AI for categorization)."""

    path: Optional[str] = None


@dataclass(frozen=True)
class Zoom:
    """Zoom in/out or reset zoom for a specific component."""

    component: str  # "tree", "editor", "preview", "terminal"
    delta: float = 0.0
    reset: bool = False
