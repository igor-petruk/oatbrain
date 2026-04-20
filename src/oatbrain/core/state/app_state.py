from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List
from oatbrain.core.ports.filestore import VaultPath


@dataclass(frozen=True)
class TabState:
    open_file: Optional[VaultPath] = None
    is_dirty: bool = False
    read_mode: bool = False
    split_mode: bool = False
    word_count: int = 0
    title: str = "Untitled"


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

    # Editor state
    tabs: List[TabState] = field(default_factory=lambda: [TabState()])
    active_tab_index: int = 0
    editor_zoom: float = 1.0
    preview_zoom: float = 1.0

    status_message: str = "Ready"
    theme_name: str = "Solarized Light"
    theme_id: str = "solarized-light"
    mermaid_dismissed: bool = False

    @property
    def active_tab(self) -> TabState:
        if 0 <= self.active_tab_index < len(self.tabs):
            return self.tabs[self.active_tab_index]
        return TabState()
