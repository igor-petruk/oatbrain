from dataclasses import dataclass
from typing import Optional
from oatbrain.core.ports.filestore import VaultPath


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


@dataclass(frozen=True)
class FileChangedOnDisk:
    """Emitted when the current file changed on disk but has unsaved edits."""

    path: str


@dataclass(frozen=True)
class TabPathChanged:
    """Emitted by an Editor when its file is renamed on disk."""

    tab_id: str
    new_path: VaultPath


@dataclass(frozen=True)
class TabTitleChanged:
    """Emitted when a tab's display title changes (e.g. from heading)."""

    tab_id: str
    title: str


@dataclass(frozen=True)
class SaveAsRequested:
    """Emitted when a new note needs a filename to be saved."""

    tab_id: str
    suggested_filename: str
    target_dir: Optional[str]
    content: str


@dataclass(frozen=True)
class FocusedTabStats:
    """Emitted when the stats of the focused tab change."""

    path: Optional[VaultPath]
    word_count: int
    is_dirty: bool
