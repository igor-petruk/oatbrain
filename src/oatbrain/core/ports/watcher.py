from pathlib import Path
from typing import Callable, Protocol

from oatbrain.core.events.watcher import FileEvent, Unsubscribe

__all__ = ["FileWatcher", "Unsubscribe"]


class FileWatcher(Protocol):
    """Protocol for observing file system changes within the vault."""

    def subscribe(self, cb: Callable[[FileEvent], None]) -> Unsubscribe:
        """Subscribe to file system events. Returns an unsubscribe callable."""
        ...

    def start(self, vault_path: Path) -> None:
        """Start observing the given vault directory."""
        ...

    def stop(self) -> None:
        """Stop observing and release resources."""
        ...
