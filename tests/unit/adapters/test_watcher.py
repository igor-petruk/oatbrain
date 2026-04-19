from unittest.mock import MagicMock, patch
from pathlib import Path

from oatbrain.adapters.watcher import WatchdogFileWatcher
from oatbrain.core.events.watcher import (
    FileCreated,
    FileDeleted,
    FileModified,
    FileRenamed,
)
from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    DirCreatedEvent,
    DirModifiedEvent,
)


def _make_watcher() -> WatchdogFileWatcher:
    return WatchdogFileWatcher()


def _drain_idle(mock_idle: MagicMock) -> None:
    """Execute all GLib.idle_add callbacks that were queued."""
    for args in mock_idle.call_args_list:
        fn = args[0][0]
        fn()
    mock_idle.reset_mock()


@patch("oatbrain.adapters.watcher.GLib")
def test_subscribe_receives_file_created(mock_glib: MagicMock) -> None:
    watcher = _make_watcher()
    received: list = []
    watcher.subscribe(received.append)

    watcher.on_created(FileCreatedEvent("/vault/note.md"))
    _drain_idle(mock_glib.idle_add)

    assert len(received) == 1
    assert isinstance(received[0], FileCreated)
    assert received[0].path == "/vault/note.md"


@patch("oatbrain.adapters.watcher.GLib")
def test_subscribe_receives_file_deleted(mock_glib: MagicMock) -> None:
    watcher = _make_watcher()
    received: list = []
    watcher.subscribe(received.append)

    watcher.on_deleted(FileDeletedEvent("/vault/old.md"))
    _drain_idle(mock_glib.idle_add)

    assert len(received) == 1
    assert isinstance(received[0], FileDeleted)
    assert received[0].path == "/vault/old.md"


@patch("oatbrain.adapters.watcher.GLib")
def test_subscribe_receives_file_modified(mock_glib: MagicMock) -> None:
    watcher = _make_watcher()
    received: list = []
    watcher.subscribe(received.append)

    watcher.on_modified(FileModifiedEvent("/vault/note.md"))
    _drain_idle(mock_glib.idle_add)

    assert len(received) == 1
    assert isinstance(received[0], FileModified)


@patch("oatbrain.adapters.watcher.GLib")
def test_subscribe_receives_file_renamed(mock_glib: MagicMock) -> None:
    watcher = _make_watcher()
    received: list = []
    watcher.subscribe(received.append)

    watcher.on_moved(FileMovedEvent("/vault/a.md", "/vault/b.md"))
    _drain_idle(mock_glib.idle_add)

    assert len(received) == 1
    assert isinstance(received[0], FileRenamed)
    assert received[0].old_path == "/vault/a.md"
    assert received[0].new_path == "/vault/b.md"


@patch("oatbrain.adapters.watcher.GLib")
def test_directory_created_event_is_skipped(mock_glib: MagicMock) -> None:
    watcher = _make_watcher()
    received: list = []
    watcher.subscribe(received.append)

    watcher.on_created(DirCreatedEvent("/vault/subdir"))
    _drain_idle(mock_glib.idle_add)

    assert len(received) == 0


@patch("oatbrain.adapters.watcher.GLib")
def test_directory_modified_event_is_skipped(mock_glib: MagicMock) -> None:
    watcher = _make_watcher()
    received: list = []
    watcher.subscribe(received.append)

    watcher.on_modified(DirModifiedEvent("/vault/subdir"))
    _drain_idle(mock_glib.idle_add)

    assert len(received) == 0


@patch("oatbrain.adapters.watcher.GLib")
def test_unsubscribe_stops_delivery(mock_glib: MagicMock) -> None:
    watcher = _make_watcher()
    received: list = []
    unsub = watcher.subscribe(received.append)

    unsub()
    watcher.on_modified(FileModifiedEvent("/vault/note.md"))
    _drain_idle(mock_glib.idle_add)

    assert received == []


@patch("oatbrain.adapters.watcher.GLib")
def test_multiple_subscribers(mock_glib: MagicMock) -> None:
    watcher = _make_watcher()
    a: list = []
    b: list = []
    watcher.subscribe(a.append)
    watcher.subscribe(b.append)

    watcher.on_modified(FileModifiedEvent("/vault/note.md"))
    _drain_idle(mock_glib.idle_add)

    assert len(a) == 1
    assert len(b) == 1


@patch("oatbrain.adapters.watcher.Observer")
def test_start_and_stop(mock_observer_cls: MagicMock) -> None:
    mock_obs = MagicMock()
    mock_observer_cls.return_value = mock_obs

    watcher = _make_watcher()
    vault = Path("/vault")
    watcher.start(vault)

    mock_obs.schedule.assert_called_once_with(watcher, str(vault), recursive=True)
    mock_obs.start.assert_called_once()

    watcher.stop()
    mock_obs.stop.assert_called_once()
    mock_obs.join.assert_called_once()


@patch("oatbrain.adapters.watcher.Observer")
def test_start_is_idempotent(mock_observer_cls: MagicMock) -> None:
    mock_obs = MagicMock()
    mock_observer_cls.return_value = mock_obs

    watcher = _make_watcher()
    watcher.start(Path("/vault"))
    watcher.start(Path("/vault"))  # second call is a no-op

    assert mock_obs.start.call_count == 1
