"""
Regression tests for Theory A: atomic write temp files causing tree duplication.

LocalFileStore.write_text creates a `.oatbrain.tmp` temp file in the same
directory as the target, then renames it atomically.  Watchdog fires:
  1. FileCreatedEvent(tmp_path)
  2. FileMovedEvent(tmp_path → target)

Without filtering, the tree gets a spurious row for the temp file which is then
renamed to the real file, producing a duplicate.
"""
from unittest.mock import MagicMock, patch

from oatbrain.adapters.watcher import WatchdogFileWatcher
from oatbrain.core.events.watcher import FileModified, FileRenamed
from watchdog.events import FileCreatedEvent, FileMovedEvent, FileDeletedEvent


def _make_watcher() -> WatchdogFileWatcher:
    return WatchdogFileWatcher()


def _drain_idle(mock_glib: MagicMock) -> list:
    received: list = []
    for args in mock_glib.idle_add.call_args_list:
        fn = args[0][0]
        fn()
    mock_glib.idle_add.reset_mock()
    return received


@patch("oatbrain.adapters.watcher.GLib")
def test_temp_file_created_is_not_forwarded(mock_glib: MagicMock) -> None:
    """FileCreated for a .oatbrain.tmp file must be silently dropped."""
    watcher = _make_watcher()
    received: list = []
    watcher.subscribe(received.append)

    watcher.on_created(FileCreatedEvent("/vault/1/.abc123.oatbrain.tmp"))
    _drain_idle(mock_glib)

    assert received == [], "temp file creation must not reach subscribers"


@patch("oatbrain.adapters.watcher.GLib")
def test_temp_file_deleted_is_not_forwarded(mock_glib: MagicMock) -> None:
    """FileDeleted for a .oatbrain.tmp file must be silently dropped."""
    watcher = _make_watcher()
    received: list = []
    watcher.subscribe(received.append)

    watcher.on_deleted(FileDeletedEvent("/vault/1/.abc123.oatbrain.tmp"))
    _drain_idle(mock_glib)

    assert received == [], "temp file deletion must not reach subscribers"


@patch("oatbrain.adapters.watcher.GLib")
def test_temp_rename_emits_file_modified_not_renamed(mock_glib: MagicMock) -> None:
    """
    When a .oatbrain.tmp file is renamed to the real target (atomic save),
    subscribers must receive FileModified(target), NOT FileRenamed.
    This lets the editor reload on external atomic writes without confusing
    the tree into thinking the file was renamed.
    """
    watcher = _make_watcher()
    received: list = []
    watcher.subscribe(received.append)

    watcher.on_moved(FileMovedEvent("/vault/1/.abc123.oatbrain.tmp", "/vault/1/yo.md"))
    _drain_idle(mock_glib)

    assert len(received) == 1
    assert isinstance(
        received[0], FileModified
    ), f"Expected FileModified but got {type(received[0])}"
    assert received[0].path == "/vault/1/yo.md"


@patch("oatbrain.adapters.watcher.GLib")
def test_real_rename_still_emits_file_renamed(mock_glib: MagicMock) -> None:
    """Non-temp renames must still produce FileRenamed."""
    watcher = _make_watcher()
    received: list = []
    watcher.subscribe(received.append)

    watcher.on_moved(FileMovedEvent("/vault/a.md", "/vault/b.md"))
    _drain_idle(mock_glib)

    assert len(received) == 1
    assert isinstance(received[0], FileRenamed)
    assert received[0].old_path == "/vault/a.md"
    assert received[0].new_path == "/vault/b.md"


@patch("oatbrain.adapters.watcher.GLib")
def test_full_atomic_save_sequence_emits_only_file_modified(
    mock_glib: MagicMock,
) -> None:
    """
    Full sequence: temp created → temp renamed to target.
    Total subscriber notifications must be exactly one FileModified(target).
    (Previously this produced one spurious FileCreated + one FileRenamed = duplicate.)
    """
    watcher = _make_watcher()
    received: list = []
    watcher.subscribe(received.append)

    # Step 1: mkstemp creates temp file
    watcher.on_created(FileCreatedEvent("/vault/1/.abc123.oatbrain.tmp"))
    _drain_idle(mock_glib)

    # Step 2: os.replace renames temp → target
    watcher.on_moved(FileMovedEvent("/vault/1/.abc123.oatbrain.tmp", "/vault/1/yo.md"))
    _drain_idle(mock_glib)

    assert len(received) == 1, f"Expected 1 event but got {len(received)}: {received}"
    assert isinstance(received[0], FileModified)
    assert received[0].path == "/vault/1/yo.md"
