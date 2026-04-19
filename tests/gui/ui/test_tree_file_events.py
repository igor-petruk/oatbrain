"""Tests for FileTree reactions to file watcher events."""
from pathlib import Path
from unittest.mock import MagicMock

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.commands import OpenFile, SetTreeExpanded  # noqa: E402
from oatbrain.core.ports.filestore import FileEntry, VaultPath  # noqa: E402
from oatbrain.ui.tree import COL_NAME, COL_PATH, FileTree  # noqa: E402

VAULT = Path("/vault")


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
    """Collect all COL_PATH values from the root level of the store."""
    paths: list[str] = []
    it = tree.store.get_iter_first()
    while it:
        paths.append(tree.store.get_value(it, COL_PATH))
        it = tree.store.iter_next(it)
    return paths


def test_file_created_adds_row_at_root() -> None:
    tree, _ = _make_tree([_fake_entry("existing.md")])

    tree._handle_file_created(str(VAULT / "new.md"))

    paths = _store_paths(tree)
    assert "new.md" in paths


def test_file_created_duplicate_not_added() -> None:
    tree, _ = _make_tree([_fake_entry("note.md")])

    tree._handle_file_created(str(VAULT / "note.md"))

    assert _store_paths(tree).count("note.md") == 1


def test_file_created_outside_vault_ignored() -> None:
    tree, _ = _make_tree([])

    tree._handle_file_created("/tmp/outside.md")

    assert _store_paths(tree) == []


def test_file_deleted_removes_row() -> None:
    tree, _ = _make_tree([_fake_entry("note.md"), _fake_entry("other.md")])

    tree._handle_file_deleted(str(VAULT / "note.md"))

    paths = _store_paths(tree)
    assert "note.md" not in paths
    assert "other.md" in paths


def test_file_deleted_missing_row_is_noop() -> None:
    tree, _ = _make_tree([_fake_entry("note.md")])

    tree._handle_file_deleted(str(VAULT / "ghost.md"))

    assert _store_paths(tree) == ["note.md"]


def test_file_deleted_outside_vault_ignored() -> None:
    tree, _ = _make_tree([_fake_entry("note.md")])

    tree._handle_file_deleted("/tmp/other.md")

    assert _store_paths(tree) == ["note.md"]


def test_file_renamed_updates_path_column() -> None:
    tree, _ = _make_tree([_fake_entry("old.md")])

    tree._handle_file_renamed(str(VAULT / "old.md"), str(VAULT / "new.md"))

    paths = _store_paths(tree)
    assert "old.md" not in paths
    assert "new.md" in paths


def test_file_renamed_updates_name_column() -> None:
    tree, _ = _make_tree([_fake_entry("old.md")])

    tree._handle_file_renamed(str(VAULT / "old.md"), str(VAULT / "new.md"))

    it = tree.store.get_iter_first()
    assert tree.store.get_value(it, COL_NAME) == "new.md"


def test_file_renamed_outside_vault_ignored() -> None:
    tree, _ = _make_tree([_fake_entry("note.md")])

    tree._handle_file_renamed("/tmp/a.md", "/tmp/b.md")

    assert _store_paths(tree) == ["note.md"]


def test_vault_rel_returns_none_for_outside_path() -> None:
    tree, _ = _make_tree([])
    assert tree._vault_rel("/other/place/file.md") is None


def test_vault_rel_strips_prefix() -> None:
    tree, _ = _make_tree([])
    assert tree._vault_rel(str(VAULT / "sub/note.md")) == "sub/note.md"
