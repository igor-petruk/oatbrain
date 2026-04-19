import gi
import threading
from pathlib import Path
from typing import Any, Callable, Optional, Union

gi.require_version("GLib", "2.0")
from gi.repository import GLib  # noqa: E402

from watchdog.events import (  # noqa: E402
    DirCreatedEvent,
    DirDeletedEvent,
    DirModifiedEvent,
    DirMovedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer  # noqa: E402

from oatbrain.core.events.watcher import (  # noqa: E402
    FileCreated,
    FileDeleted,
    FileEvent,
    FileModified,
    FileRenamed,
)
from oatbrain.core.ports.watcher import FileWatcher, Unsubscribe  # noqa: E402


class WatchdogFileWatcher(FileSystemEventHandler, FileWatcher):
    """FileWatcher adapter using watchdog."""

    def __init__(self) -> None:
        super().__init__()
        self._observer: Optional[Any] = None
        self._watch_path: Optional[Path] = None
        self._subscribers: list[Callable[[FileEvent], None]] = []
        self._lock = threading.Lock()

    def subscribe(self, cb: Callable[[FileEvent], None]) -> Unsubscribe:
        """Subscribe to file system events. Returns an unsubscribe callable."""
        with self._lock:
            self._subscribers.append(cb)
        return lambda: self._remove_subscriber(cb)

    def _remove_subscriber(self, cb: Callable[[FileEvent], None]) -> None:
        with self._lock:
            try:
                self._subscribers.remove(cb)
            except ValueError:
                pass

    def _publish_event(self, event: FileEvent) -> None:
        """Marshal event onto the GLib main loop and notify all subscribers."""

        def publish() -> bool:
            with self._lock:
                handlers = list(self._subscribers)
            for handler in handlers:
                handler(event)
            return False

        GLib.idle_add(publish)

    @staticmethod
    def _is_tmp(path: str) -> bool:
        return path.endswith(".oatbrain.tmp")

    def on_created(self, event: Union[DirCreatedEvent, FileCreatedEvent]) -> None:
        if self._is_tmp(str(event.src_path)):
            return
        self._publish_event(FileCreated(str(event.src_path)))

    def on_deleted(self, event: Union[DirDeletedEvent, FileDeletedEvent]) -> None:
        if self._is_tmp(str(event.src_path)):
            return
        self._publish_event(FileDeleted(str(event.src_path)))

    def on_modified(self, event: Union[DirModifiedEvent, FileModifiedEvent]) -> None:
        if event.is_directory or self._is_tmp(str(event.src_path)):
            return
        self._publish_event(FileModified(str(event.src_path)))

    def on_moved(self, event: Union[DirMovedEvent, FileMovedEvent]) -> None:
        src = str(event.src_path)
        dest = str(event.dest_path)
        if self._is_tmp(src):
            # Atomic write (mkstemp → rename): report as FileModified on target.
            self._publish_event(FileModified(dest))
        else:
            self._publish_event(FileRenamed(src, dest))

    def start(self, vault_path: Path) -> None:
        """Start observing the vault directory."""
        if self._observer is not None:
            return

        self._watch_path = vault_path
        self._observer = Observer()
        self._observer.schedule(self, str(vault_path), recursive=True)
        self._observer.start()

    def stop(self) -> None:
        """Stop observing and clean up."""
        if self._observer is None:
            return

        self._observer.stop()
        self._observer.join()
        self._observer = None
        self._watch_path = None
        with self._lock:
            self._subscribers.clear()


__all__ = ["WatchdogFileWatcher"]
