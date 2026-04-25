from pathlib import Path
from typing import Callable, Protocol, Optional

from oatbrain.core.events.watcher import Unsubscribe

__all__ = ["FileWatcher", "Unsubscribe"]


class FileWatcher(Protocol):
    """Protocol for observing file system changes within the vault."""

    def subscribe_file(
        self, path: Path, cb: Callable[[str, Path, Optional[Path]], None]
    ) -> Unsubscribe:
        """
        Subscribe to events for a specific file.
        Callback receives (action, path, new_path)
        where action is one of "CREATED", "DELETED", "MODIFIED", "RENAMED".
        """
        ...

    def subscribe_dir(
        self, path: Path, cb: Callable[[str, Path, Optional[Path]], None]
    ) -> Unsubscribe:
        """
        Subscribe to events for a specific directory.
        Callback receives (action, path, new_path).
        """
        ...
