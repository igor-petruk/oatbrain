from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List
from oatbrain.core.ports.filestore import VaultPath


@dataclass(frozen=True)
class EditorState:
    open_file: Optional[VaultPath] = None
    is_dirty: bool = False
    read_mode: bool = False
    word_count: int = 0
    mru: List[str] = field(default_factory=list)


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
    terminal_width: int = 360
    terminal_visible: bool = True

    editor: EditorState = field(default_factory=EditorState)
    status_message: str = "Ready"
    theme_name: str = "Solarized Light"
    theme_id: str = "solarized-light"
