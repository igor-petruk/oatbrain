from unittest.mock import MagicMock
from pathlib import Path
from oatbrain.core.bus import EventBus
from oatbrain.ui.tree import FileTree


class _MockEntry:
    def __init__(self, name: str, is_dir: bool = False):
        self.path = MagicMock()
        self.path.path.name = name
        self.path.__str__.return_value = name
        self.is_dir = is_dir


def _make_tree(initial_entries: list[str]) -> tuple[FileTree, EventBus]:
    bus = EventBus()
    router = MagicMock()
    vault_root = Path("/fake/vault")
    filestore = MagicMock()

    # Needs a filestore to initialize properly
    filestore.list_dir.return_value = [_MockEntry(e) for e in initial_entries]

    tree = FileTree(
        filestore=filestore,
        event_bus=bus,
        command_router=router,
        vault_root=vault_root,
    )

    return tree, bus


def test_tree_duplicate_rename_bug() -> None:
    """
    Simulates the bug where a rename into an existing file created a duplicate row.
    Now, the registry should enforce uniqueness by removing the existing row first.
    """
    # Start with two files
    tree, _ = _make_tree(["source.md", "target.md"])

    # Assert two rows
    iter_ = tree.store.get_iter_first()
    count = 0
    names = set()
    while iter_:
        names.add(tree.store.get_value(iter_, 1))  # COL_NAME
        count += 1
        iter_ = tree.store.iter_next(iter_)

    assert count == 2
    assert "source.md" in names
    assert "target.md" in names

    # Simulate moving source.md over target.md
    # _handle_file_renamed takes absolute paths
    tree._handle_file_renamed("/fake/vault/source.md", "/fake/vault/target.md")

    # Assert only one row now
    iter_ = tree.store.get_iter_first()
    new_count = 0
    new_names = set()
    while iter_:
        new_names.add(tree.store.get_value(iter_, 1))
        new_count += 1
        iter_ = tree.store.iter_next(iter_)

    assert new_count == 1
    assert "target.md" in new_names
    assert "source.md" not in new_names
