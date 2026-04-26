import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List
from oatbrain.core.ports.filestore import VaultPath


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass(frozen=True)
class TabState:
    """State for a single editor/preview tab."""

    tab_id: str = field(default_factory=_new_id)
    open_file: Optional[VaultPath] = None
    mode: str = "editor"  # "editor" | "preview"
    zoom: float = 1.0
    preview_zoom: float = 1.0


@dataclass(frozen=True)
class GroupState:
    """State for one tab group (a horizontal column of tabs)."""

    group_id: str = field(default_factory=_new_id)
    tabs: tuple[TabState, ...] = field(default_factory=lambda: (TabState(),))
    active_tab_index: int = 0


@dataclass(frozen=True)
class EditorAreaState:
    """State for the whole multi-group editor area."""

    groups: tuple[GroupState, ...] = field(default_factory=lambda: (GroupState(),))
    # One fraction per divider; len == len(groups) - 1
    divider_fractions: tuple[float, ...] = field(default_factory=tuple)
    focused_group_index: int = 0


@dataclass(frozen=True)
class AppState:
    vault_root: Path

    # Window state (§27.2)
    window_width: int = 1200
    window_height: int = 800
    window_fullscreen: bool = False

    # Pane state (§27.2)
    tree_width: int = 180
    tree_visible: bool = True
    tree_expanded: List[str] = field(default_factory=list)
    tree_zoom: float = 1.0
    terminal_width: int = 360
    terminal_visible: bool = True
    terminal_zoom: float = 1.0

    # Editor area state (replaces old EditorState)
    editor_area: EditorAreaState = field(default_factory=EditorAreaState)

    theme_name: str = "Solarized Light"
    theme_id: str = "solarized-light"
    mermaid_dismissed: bool = False
