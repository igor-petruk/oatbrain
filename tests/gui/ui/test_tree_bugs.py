"""
Regression tests for two tree bugs:

Bug 1 — auto-expand after collapse:
  Stale StateUpdated idle callbacks re-expand a directory the user just collapsed,
  because _on_state_updated queues one idle per event without cancelling old ones.

Bug 2 — new directory from git checkout not appearing:
  WatchdogFileWatcher.on_created drops DirCreatedEvent (is_directory check).
  The directory never fires FileCreated so the tree never adds a row for it.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from oatbrain.adapters.watcher import WatchdogFileWatcher  # noqa: E402
from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.commands import OpenFile, SetTreeExpanded  # noqa: E402
from oatbrain.core.events.watcher import FileCreated  # noqa: E402
from oatbrain.core.ports.filestore import FileEntry, VaultPath  # noqa: E402
from oatbrain.core.state.app_state import AppState  # noqa: E402
from oatbrain.core.events.state import StateUpdated  # noqa: E402
from oatbrain.ui.tree import COL_IS_DIR, COL_IS_DUMMY, COL_PATH, FileTree  # noqa: E402
from watchdog.events import DirCreatedEvent  # noqa: E402

VAULT = Path("/vault")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_entry(rel: str, is_dir: bool = False) -> FileEntry:
    return FileEntry(
        path=VaultPath.from_str(rel),
        is_dir=is_dir,
        is_readonly=False,
        size=0,
        mtime=0.0,
    )


def _make_tree(root_entries: list[FileEntry]) -> tuple[FileTree, EventBus]:
    filestore = MagicMock()
    filestore.list_dir.return_value = root_entries

    event_bus = EventBus()
    command_router = CommandRouter()
    command_router.register(OpenFile, lambda _: None, visible=False)
    command_router.register(SetTreeExpanded, lambda _: None, visible=False)

    tree = FileTree(
        filestore=filestore,
        event_bus=event_bus,
        command_router=command_router,
        vault_root=VAULT,
    )
    return tree, event_bus


def _store_paths(tree: FileTree) -> list[str]:
    paths: list[str] = []
    it = tree.store.get_iter_first()
    while it:
        paths.append(tree.store.get_value(it, COL_PATH))
        it = tree.store.iter_next(it)
    return paths


def _base_state(**kwargs) -> AppState:
    return AppState(vault_root=VAULT, **kwargs)


# ---------------------------------------------------------------------------
# Bug 1: stale StateUpdated re-expands a user-collapsed directory
# ---------------------------------------------------------------------------


def test_stale_state_updated_does_not_re_expand_collapsed_dir() -> None:
    """
    When the user collapses a directory, any pending _sync_with_state idle
    that still carries tree_expanded=["subdir"] must NOT re-open the row.

    Before fix: _on_state_updated blindly queues one idle per event.
    A stale idle with the old expanded state fires after collapse and calls
    _expand_path, re-opening the directory.

    After fix: _on_state_updated cancels the old idle before queuing a new one,
    so only the latest state (collapsed) is ever applied.
    """
    tree, event_bus = _make_tree([_fake_entry("subdir", is_dir=True)])

    # Simulate: user expanded "subdir" — stale idle queued with expanded state
    stale_state = _base_state(tree_expanded=["subdir"])
    stale_event = StateUpdated(stale_state)

    # Simulate: user immediately collapsed "subdir" — newer idle queued
    collapsed_state = _base_state(tree_expanded=[])
    collapsed_event = StateUpdated(collapsed_state)

    # Apply STALE event first (the bug: this re-expands what the user collapsed)
    tree._sync_with_state(stale_event)

    # Apply NEWER (collapsed) event — this should be the final word
    tree._sync_with_state(collapsed_event)

    # Confirm: _expanded_state reflects the collapsed state, not the stale one
    assert (
        tree._expanded_state == set()
    ), f"_expanded_state should be empty after collapse, got {tree._expanded_state}"


def test_only_latest_state_updated_is_processed() -> None:
    """
    _on_state_updated should cancel any pending idle and schedule only the latest
    StateUpdated, so rapid expand→collapse doesn't leave a stale expand pending.
    """
    tree, event_bus = _make_tree([_fake_entry("subdir", is_dir=True)])

    captured_idles: list = []

    def fake_idle_add(fn, *args):  # type: ignore[no-untyped-def]
        captured_idles.append((fn, args))
        return len(captured_idles)  # return a source id

    with patch("oatbrain.ui.tree.GLib") as mock_glib:
        mock_glib.idle_add.side_effect = fake_idle_add
        mock_glib.source_remove = MagicMock()
        mock_glib.SOURCE_REMOVE = 0

        # First StateUpdated (expanded)
        tree._on_state_updated(StateUpdated(_base_state(tree_expanded=["subdir"])))
        # Second StateUpdated (collapsed) — should cancel first
        tree._on_state_updated(StateUpdated(_base_state(tree_expanded=[])))

    # source_remove must have been called to cancel the first idle
    mock_glib.source_remove.assert_called_once()
    # Exactly two idle_add calls total (one per event)
    assert mock_glib.idle_add.call_count == 2


# ---------------------------------------------------------------------------
# Bug 2: new directory from git checkout not appearing in tree
# ---------------------------------------------------------------------------


@patch("oatbrain.adapters.watcher.GLib")
def test_dir_created_event_is_forwarded(mock_glib: MagicMock) -> None:
    """
    WatchdogFileWatcher.on_created must forward DirCreatedEvent as FileCreated
    so that newly checked-out directories appear in the tree.

    Before fix: on_created has 'if event.is_directory: return' which silently
    drops the event. The directory never appears in the tree.
    """
    watcher = WatchdogFileWatcher()
    received: list = []
    watcher.subscribe(received.append)

    watcher.on_created(DirCreatedEvent("/vault/oatbar"))

    for args in mock_glib.idle_add.call_args_list:
        args[0][0]()

    assert (
        len(received) == 1
    ), "DirCreatedEvent must produce exactly one FileCreated notification"
    assert isinstance(received[0], FileCreated)
    assert received[0].path == "/vault/oatbar"


def test_tree_adds_directory_row_on_file_created_for_dir() -> None:
    """
    When _handle_file_created is called with the path of a newly created
    directory, the tree must add a row with COL_IS_DIR=True and a dummy child.
    """
    tree, _ = _make_tree([])

    with patch.object(tree, "_path_is_dir", return_value=True):
        tree._handle_file_created(str(VAULT / "oatbar"))

    paths = _store_paths(tree)
    assert "oatbar" in paths, "new directory must appear in the tree"

    # Find the iter and verify it has is_dir=True and a dummy child
    it = tree.store.get_iter_first()
    assert it is not None
    assert tree.store.get_value(it, COL_IS_DIR) is True

    child = tree.store.iter_children(it)
    assert child is not None, "directory must have a dummy child for lazy load"
    assert tree.store.get_value(child, COL_IS_DUMMY) is True


def test_tree_shows_new_directory_after_git_checkout_sequence() -> None:
    """
    Full sequence: DirCreated(oatbar) fires, then FileCreated(oatbar/README.md).
    After DirCreated: oatbar row with dummy child must be in tree.
    After FileCreated for the file: file is silently deferred (parent has dummy).
    The directory row must not be duplicated.
    """
    tree, event_bus = _make_tree([])

    with patch.object(tree, "_path_is_dir", return_value=True):
        tree._handle_file_created(str(VAULT / "oatbar"))

    paths = _store_paths(tree)
    assert paths.count("oatbar") == 1, "oatbar must appear exactly once"

    # Now a file inside arrives (parent still has dummy — not expanded yet)
    tree._handle_file_created(str(VAULT / "oatbar" / "README.md"))

    # oatbar should still appear exactly once (file deferred until expanded)
    paths = _store_paths(tree)
    assert paths.count("oatbar") == 1
