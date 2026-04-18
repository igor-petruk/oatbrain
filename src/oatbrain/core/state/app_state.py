from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from oatbrain.core.ports.filestore import VaultPath

@dataclass(frozen=True)
class EditorState:
    open_file: Optional[VaultPath] = None
    is_dirty: bool = False
    read_mode: bool = False
    word_count: int = 0

@dataclass(frozen=True)
class AppState:
    vault_root: Path
    editor: EditorState = field(default_factory=EditorState)
    status_message: str = "Ready"
