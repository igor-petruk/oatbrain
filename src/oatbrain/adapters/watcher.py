import gi
import logging
from pathlib import Path
from typing import Callable, Optional

gi.require_version("GLib", "2.0")
gi.require_version("Gio", "2.0")
from gi.repository import GLib, Gio  # noqa: E402

from oatbrain.core.ports.watcher import FileWatcher, Unsubscribe  # noqa: E402


class GioFileWatcher(FileWatcher):
    """FileWatcher adapter using Gio.FileMonitor."""

    def __init__(self) -> None:
        super().__init__()
        self._logger = logging.getLogger("oatbrain.watcher")

    def _on_changed(
        self,
        cb: Callable[[str, Path, Optional[Path]], None],
        monitor: Gio.FileMonitor,
        file: Gio.File,
        other_file: Optional[Gio.File],
        event_type: Gio.FileMonitorEvent,
    ) -> None:
        path_str = file.get_path()

        other_path_str = other_file.get_path() if other_file else "None"
        try:
            event_name = event_type.value_name
        except AttributeError:
            event_name = str(event_type)

        self._logger.debug(
            "[RAW] %s | %s | %s",
            event_name,
            path_str,
            other_path_str,
        )

        if not path_str:
            return

        action: Optional[str] = None
        target_path: Optional[Path] = None
        new_target_path: Optional[Path] = None

        if event_type == Gio.FileMonitorEvent.CREATED:
            action = "CREATED"
            target_path = Path(path_str)
        elif event_type == Gio.FileMonitorEvent.DELETED:
            action = "DELETED"
            target_path = Path(path_str)
        elif event_type == Gio.FileMonitorEvent.CHANGES_DONE_HINT:
            action = "MODIFIED"
            target_path = Path(path_str)
        elif (
            event_type == Gio.FileMonitorEvent.RENAMED
            or event_type == Gio.FileMonitorEvent.MOVED
            or event_type == Gio.FileMonitorEvent.MOVED_OUT
        ):
            action = "RENAMED"
            target_path = Path(path_str)
            if other_path_str != "None":
                new_target_path = Path(other_path_str)
        elif event_type == Gio.FileMonitorEvent.MOVED_IN:
            action = "RENAMED"
            # For MOVED_IN, `file` is the new location, `other_file` is the old location
            if other_path_str != "None":
                target_path = Path(other_path_str)
                new_target_path = Path(path_str)
            else:
                # If old path is missing, treat as simple CREATED
                action = "CREATED"
                target_path = Path(path_str)

        if action and target_path:
            if action == "RENAMED" and new_target_path:
                self._logger.debug(
                    "%s  %s  →  %s", action, target_path, new_target_path
                )
            else:
                self._logger.debug("%s  %s", action, target_path)

            # Bind the current loop variables for the closure
            a: str = action
            tp: Path = target_path
            ntp: Optional[Path] = new_target_path

            def dispatch(
                a_val: str = a,
                tp_val: Path = tp,
                ntp_val: Optional[Path] = ntp,
            ) -> bool:
                cb(a_val, tp_val, ntp_val)
                return False

            # Dispatch clearly on the main loop
            GLib.idle_add(dispatch)

    def subscribe_file(
        self, path: Path, cb: Callable[[str, Path, Optional[Path]], None]
    ) -> Unsubscribe:
        """Subscribe to events for a specific file."""
        return self._subscribe_internal(path, cb, is_dir=False)

    def subscribe_dir(
        self, path: Path, cb: Callable[[str, Path, Optional[Path]], None]
    ) -> Unsubscribe:
        """Subscribe to events for a specific directory."""
        return self._subscribe_internal(path, cb, is_dir=True)

    def _subscribe_internal(
        self, path: Path, cb: Callable[[str, Path, Optional[Path]], None], is_dir: bool
    ) -> Unsubscribe:
        gfile = Gio.File.new_for_path(str(path))

        try:
            if is_dir:
                monitor = gfile.monitor_directory(
                    Gio.FileMonitorFlags.WATCH_MOVES, None
                )
            else:
                monitor = gfile.monitor_file(Gio.FileMonitorFlags.WATCH_MOVES, None)
        except Exception as e:
            self._logger.error("watch failed  %s  — %s", path, e)
            return lambda: None

        handler_id = monitor.connect(
            "changed", lambda m, f, of, et: self._on_changed(cb, m, f, of, et)
        )

        def unsubscribe() -> None:
            self._logger.debug("⊖  %s", path)
            monitor.disconnect(handler_id)
            monitor.cancel()

        self._logger.debug("⊕  %s  [%s]", path, "dir" if is_dir else "file")
        return unsubscribe


__all__ = ["GioFileWatcher"]
