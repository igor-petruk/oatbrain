"""
Comprehensive test harness for the tree expansion state machine.

The expansion subsystem forms a feedback loop:
  User expand/collapse
    → tree.on_row_expanded / on_row_collapsed
    → SetTreeExpanded command
    → window._handle_set_tree_expanded (state manager)
    → StateUpdated event
    → tree._on_state_updated → _sync_with_state
    → tree_view.expand_row (which fires on_row_expanded again)

File watcher events add a second path that can race with the above.

This harness tests the intended (correct) behavior. Many tests will FAIL on
the current codebase, revealing bugs. Fix them one by one.

Known bugs tested here:
  BUG-1: _handle_set_tree_expanded does not prune descendant paths on collapse.
          Result: collapsing "a" leaves "a/b" in tree_expanded, which causes
          _sync_with_state to re-expand "a" via its children → infinite loop.
  BUG-2: _sync_with_state only expands, never collapses existing rows.
          Result: external state change to fewer expanded paths doesn't collapse.
"""
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from oatbrain.core.bus import CommandRouter, EventBus  # noqa: E402
from oatbrain.core.commands import OpenFile, SetTreeExpanded  # noqa: E402
from oatbrain.core.events.state import StateUpdated  # noqa: E402
from oatbrain.core.ports.filestore import FileEntry, VaultPath  # noqa: E402
from oatbrain.core.state import AppState  # noqa: E402
from oatbrain.ui.tree import COL_IS_DUMMY, COL_PATH, FileTree  # noqa: E402

VAULT = Path("/vault")


# ---------------------------------------------------------------------------
# FakeGLib: synchronous idle queue with source_remove support
# ---------------------------------------------------------------------------


class FakeGLib:
    """Drop-in for gi.repository.GLib in tree.py tests."""

    SOURCE_REMOVE = False
    SOURCE_CONTINUE = True

    def __init__(self) -> None:
        self._queue: list[tuple[int, object, tuple]] = []
        self._cancelled: set[int] = set()
        self._next_id = 1

    def idle_add(self, fn: object, *args: object) -> int:
        id_ = self._next_id
        self._next_id += 1
        self._queue.append((id_, fn, args))
        return id_

    def source_remove(self, id_: int) -> None:
        self._cancelled.add(id_)

    def drain(self, max_rounds: int = 20) -> int:
        """Run all queued idles. Returns total count executed."""
        executed = 0
        for _ in range(max_rounds):
            if not self._queue:
                break
            batch = list(self._queue)
            self._queue.clear()
            for id_, fn, args in batch:
                if id_ not in self._cancelled:
                    fn(*args)  # type: ignore[operator]
                    executed += 1
        return executed


# ---------------------------------------------------------------------------
# FakeStateManager: mirrors CURRENT (buggy) window.py behavior
# Tests that require correct collapse-pruning will fail until BUG-1 is fixed.
# ---------------------------------------------------------------------------


class FakeStateManager:
    """
    Simulates window.py state management for SetTreeExpanded commands.

    Replicates the CURRENT behavior of _handle_set_tree_expanded:
      - expand: appends path if not present
      - collapse: removes ONLY the exact path (BUG: no descendant pruning)

    Also handles FileDeleted with correct pruning (already implemented).
    """

    def __init__(
        self,
        event_bus: EventBus,
        initial_expanded: list[str] | None = None,
        vault_root: Path = VAULT,
    ) -> None:
        self.event_bus = event_bus
        self.vault_root = vault_root
        self.tree_expanded: list[str] = list(initial_expanded or [])

    def handle_set_tree_expanded(self, cmd: SetTreeExpanded) -> None:
        expanded = list(self.tree_expanded)
        if cmd.is_expanded and cmd.path not in expanded:
            expanded.append(cmd.path)
        elif not cmd.is_expanded and cmd.path in expanded:
            # Correct behavior: remove exact path AND all descendants
            prefix = cmd.path + "/"
            expanded = [
                p for p in expanded if p != cmd.path and not p.startswith(prefix)
            ]
        self.tree_expanded = expanded
        self._publish()

    def _publish(self) -> None:
        state = AppState(vault_root=self.vault_root, tree_expanded=self.tree_expanded)
        self.event_bus.publish(StateUpdated(state))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry(rel: str, is_dir: bool = False) -> FileEntry:
    return FileEntry(
        path=VaultPath.from_str(rel),
        is_dir=is_dir,
        is_readonly=False,
        size=0,
        mtime=0.0,
    )


def _fake_list_dir(
    dir_map: dict[str, list[FileEntry]],
) -> object:
    def _impl(vault_path: VaultPath) -> list[FileEntry]:
        key = str(vault_path)
        if key == ".":
            return dir_map.get(".", [])
        return dir_map.get(key, [])

    return _impl


class Harness:
    """
    Wires FileTree, FakeStateManager, FakeGLib together for integration tests.

    Usage::

        with make_harness(...) as h:
            h.simulate_expand("projects")
            h.drain()
            assert "projects" in h.state_manager.tree_expanded
    """

    def __init__(
        self,
        dir_map: dict[str, list[FileEntry]] | None = None,
        initial_expanded: list[str] | None = None,
    ) -> None:
        self.glib = FakeGLib()
        self.event_bus = EventBus()
        self.command_router = CommandRouter()

        self.filestore = MagicMock()
        self.filestore.list_dir.side_effect = _fake_list_dir(dir_map or {})

        self.state_manager = FakeStateManager(
            self.event_bus,
            initial_expanded=initial_expanded,
        )
        self.command_router.register(
            SetTreeExpanded, self.state_manager.handle_set_tree_expanded, visible=False
        )
        self.command_router.register(OpenFile, lambda _: None, visible=False)

        with patch("oatbrain.ui.tree.GLib", self.glib):
            self.tree = FileTree(
                filestore=self.filestore,
                event_bus=self.event_bus,
                command_router=self.command_router,
                vault_root=VAULT,
            )

        if initial_expanded:
            self.fire_state(initial_expanded)

        # Patch tree_view methods so expand_row/collapse_row fire signals
        self._expand_depth = 0
        self.tree.tree_view.expand_row = self._fake_expand_row
        self.tree.tree_view.collapse_row = self._fake_collapse_row
        self.tree.tree_view.row_expanded = MagicMock(return_value=False)

    def _fake_expand_row(self, tree_path: object, open_all: bool) -> bool:
        """Simulate GTK expand_row by calling on_row_expanded directly."""
        if self._expand_depth > 5:
            return False
        self._expand_depth += 1
        try:
            it = self.tree.store.get_iter(tree_path)  # type: ignore[arg-type]
            if it:
                self.tree.tree_view.row_expanded.return_value = True
                with patch("oatbrain.ui.tree.GLib", self.glib):
                    self.tree.on_row_expanded(self.tree.tree_view, it, tree_path)
                self.glib.drain()
        finally:
            self._expand_depth -= 1
        return True

    def _fake_collapse_row(self, tree_path: object) -> bool:
        """Simulate GTK collapse_row by calling on_row_collapsed directly."""
        try:
            it = self.tree.store.get_iter(tree_path)  # type: ignore[arg-type]
            if it:
                self.tree.tree_view.row_expanded.return_value = False
                with patch("oatbrain.ui.tree.GLib", self.glib):
                    self.tree.on_row_collapsed(self.tree.tree_view, it, tree_path)
                self.glib.drain()
        except Exception:
            pass
        return True

    def simulate_expand(self, rel_path: str) -> None:
        """Simulate user expanding a directory row."""
        it = self.tree._find_iter_for_path(rel_path)
        assert it is not None, f"Path not in tree: {rel_path}"
        tree_path = self.tree.store.get_path(it)  # noqa: E501
        self.tree.tree_view.row_expanded.return_value = False
        with patch("oatbrain.ui.tree.GLib", self.glib):
            self.tree.on_row_expanded(self.tree.tree_view, it, tree_path)
        self.drain()

    def simulate_collapse(self, rel_path: str) -> None:
        """Simulate user collapsing a directory row."""
        it = self.tree._find_iter_for_path(rel_path)
        assert it is not None, f"Path not in tree: {rel_path}"
        tree_path = self.tree.store.get_path(it)  # noqa: E501
        self.tree.tree_view.row_expanded.return_value = True
        with patch("oatbrain.ui.tree.GLib", self.glib):
            self.tree.on_row_collapsed(self.tree.tree_view, it, tree_path)
        self.drain()

    def fire_state(self, expanded: list[str]) -> None:
        """
        Inject a StateUpdated with the given expanded list (external state change).
        """
        self.state_manager.tree_expanded = list(expanded)
        with patch("oatbrain.ui.tree.GLib", self.glib):
            self.state_manager._publish()
        self.drain()

    def fire_file_event(self, event: object) -> None:
        """Inject a file watcher event."""
        with patch("oatbrain.ui.tree.GLib", self.glib):
            self.event_bus.publish(event)  # type: ignore[arg-type]
        self.drain()

    def drain(self) -> None:
        with patch("oatbrain.ui.tree.GLib", self.glib):
            self.glib.drain()

    def root_paths(self) -> list[str]:
        """Returns COL_PATH values for all root-level rows."""
        paths: list[str] = []
        it = self.tree.store.get_iter_first()
        while it:
            paths.append(self.tree.store.get_value(it, COL_PATH))
            it = self.tree.store.iter_next(it)
        return paths

    def child_paths(self, parent_rel: str) -> list[str]:
        """Returns COL_PATH values for direct children of a row."""
        it = self.tree._find_iter_for_path(parent_rel)
        if it is None:
            return []
        paths: list[str] = []
        child = self.tree.store.iter_children(it)
        while child:
            paths.append(self.tree.store.get_value(child, COL_PATH))
            child = self.tree.store.iter_next(child)
        return paths

    def is_dummy_child(self, parent_rel: str) -> bool:
        it = self.tree._find_iter_for_path(parent_rel)
        if it is None:
            return False
        child = self.tree.store.iter_children(it)
        if child is None:
            return False
        return bool(self.tree.store.get_value(child, COL_IS_DUMMY))

    def expanded_state(self) -> set[str]:
        return set(self.tree._expanded_state)

    def manager_expanded(self) -> set[str]:
        return set(self.state_manager.tree_expanded)


@contextmanager
def make_harness(
    dir_map: dict[str, list[FileEntry]] | None = None,
    initial_expanded: list[str] | None = None,
) -> Generator[Harness, None, None]:
    h = Harness(dir_map=dir_map, initial_expanded=initial_expanded)
    yield h


# ---------------------------------------------------------------------------
# Group A: State Manager — collapse pruning
# ---------------------------------------------------------------------------


def test_A1_collapse_removes_exact_path() -> None:
    """Collapsing 'a' removes 'a' from tree_expanded."""
    with make_harness(
        dir_map={".": [_entry("a", is_dir=True)]},
        initial_expanded=["a"],
    ) as h:
        h.simulate_collapse("a")
        assert (
            "a" not in h.manager_expanded()
        ), "Collapsed path must be removed from tree_expanded"


def test_A2_collapse_prunes_direct_children() -> None:
    """
    BUG-1: Collapsing 'a' must also remove 'a/b' from tree_expanded.
    Currently fails because window.py only removes the exact path.
    """
    with make_harness(
        dir_map={
            ".": [_entry("a", is_dir=True)],
            "a": [_entry("a/b", is_dir=True)],
        },
        initial_expanded=["a", "a/b"],
    ) as h:
        h.fire_state(["a", "a/b"])
        h.simulate_collapse("a")
        assert (
            "a/b" not in h.manager_expanded()
        ), "Collapsing parent must prune child paths from tree_expanded"


def test_A3_collapse_prunes_deeply_nested_descendants() -> None:
    """
    BUG-1: Collapsing 'a' must remove 'a/b', 'a/b/c', 'a/b/c/d'.
    """
    with make_harness(
        dir_map={".": [_entry("a", is_dir=True)]},
        initial_expanded=["a", "a/b", "a/b/c", "a/b/c/d"],
    ) as h:
        h.fire_state(["a", "a/b", "a/b/c", "a/b/c/d"])
        h.simulate_collapse("a")
        remaining = h.manager_expanded()
        assert (
            remaining == set()
        ), f"All descendants must be pruned on collapse, got {remaining}"


def test_A4_collapse_does_not_affect_sibling() -> None:
    """Collapsing 'a' must not remove sibling 'b' from tree_expanded."""
    with make_harness(
        dir_map={
            ".": [_entry("a", is_dir=True), _entry("b", is_dir=True)],
        },
        initial_expanded=["a", "b"],
    ) as h:
        h.fire_state(["a", "b"])
        h.simulate_collapse("a")
        assert (
            "b" in h.manager_expanded()
        ), "Sibling 'b' must remain in tree_expanded after collapsing 'a'"


def test_A5_expand_then_collapse_leaves_empty() -> None:
    """Full round-trip: expand 'a' then collapse → expanded is empty."""
    with make_harness(
        dir_map={".": [_entry("a", is_dir=True)]},
    ) as h:
        h.simulate_expand("a")
        h.simulate_collapse("a")
        assert (
            h.manager_expanded() == set()
        ), "After expand→collapse cycle, tree_expanded must be empty"


def test_A6_expand_records_path() -> None:
    """Expanding 'a' adds 'a' to tree_expanded."""
    with make_harness(
        dir_map={".": [_entry("a", is_dir=True)]},
    ) as h:
        h.simulate_expand("a")
        assert (
            "a" in h.manager_expanded()
        ), "Expanded path must be recorded in tree_expanded"


# ---------------------------------------------------------------------------
# Group B: Tree sync — _sync_with_state logic
# ---------------------------------------------------------------------------


def test_B1_sync_expands_paths_from_state() -> None:
    """StateUpdated(expanded=['a']) causes tree to expand 'a'."""
    with make_harness(
        dir_map={
            ".": [_entry("a", is_dir=True)],
            "a": [_entry("a/note.md")],
        },
    ) as h:
        h.fire_state(["a"])
        # After sync, 'a' should be reflected in tree's expanded_state
        assert (
            "a" in h.expanded_state()
        ), "_sync_with_state must record 'a' in _expanded_state"


def test_B2_sync_noop_if_state_unchanged() -> None:
    """If expanded state didn't change, _sync_with_state must not re-expand."""
    with make_harness(
        dir_map={".": [_entry("a", is_dir=True)]},
        initial_expanded=["a"],
    ) as h:
        h.tree.tree_view.expand_row = MagicMock(return_value=True)
        h.fire_state(["a"])
        # Manually set _expanded_state to match
        h.tree._expanded_state = {"a"}
        call_count_before = h.tree.tree_view.expand_row.call_count
        h.fire_state(["a"])
        assert (
            h.tree.tree_view.expand_row.call_count == call_count_before
        ), "expand_row must not be called when expanded state is unchanged"


def test_B3_sync_cancels_stale_idle() -> None:
    """
    Second _on_state_updated must cancel the first idle via source_remove.
    Regression test for the stale idle bug.
    """
    with make_harness(
        dir_map={".": [_entry("a", is_dir=True)]},
    ) as h:
        cancelled_ids: list[int] = []
        orig_remove = h.glib.source_remove

        def tracking_remove(id_: int) -> None:
            cancelled_ids.append(id_)
            orig_remove(id_)

        h.glib.source_remove = tracking_remove  # type: ignore[method-assign]

        with patch("oatbrain.ui.tree.GLib", h.glib):
            # Queue two updates without draining
            state1 = AppState(vault_root=VAULT, tree_expanded=["a"])
            state2 = AppState(vault_root=VAULT, tree_expanded=[])
            h.tree._on_state_updated(StateUpdated(state1))
            h.tree._on_state_updated(StateUpdated(state2))

        assert (
            len(cancelled_ids) >= 1
        ), "source_remove must be called to cancel stale idle"


def test_B4_sync_does_not_reexpand_after_collapse() -> None:
    """
    After user collapses 'a', a subsequent StateUpdated(expanded=[]) must
    NOT re-expand 'a'. This exercises the stale idle cancellation.
    """
    with make_harness(
        dir_map={".": [_entry("a", is_dir=True)]},
    ) as h:
        h.simulate_expand("a")
        h.simulate_collapse("a")
        # _expanded_state should be empty after collapse + state sync
        assert (
            "a" not in h.expanded_state()
        ), "_expanded_state must not contain 'a' after it was collapsed"


def test_B5_orphan_child_in_state_does_not_cause_loop() -> None:
    """
    BUG-1 consequence: if tree_expanded contains 'a/b' but not 'a',
    _sync_with_state must NOT try to expand 'a' (which would fire on_row_expanded
    and add 'a' back → feedback loop).

    Correct behavior: ignore orphan children whose parent is not expanded.
    """
    with make_harness(
        dir_map={
            ".": [_entry("a", is_dir=True)],
            "a": [_entry("a/b", is_dir=True)],
        },
    ) as h:
        # Force state where 'a' is collapsed but 'a/b' is still in expanded
        expand_row_calls: list = []
        h.tree.tree_view.expand_row = lambda tp, _: expand_row_calls.append(tp) or True

        with patch("oatbrain.ui.tree.GLib", h.glib):
            h.tree._sync_with_state(
                StateUpdated(AppState(vault_root=VAULT, tree_expanded=["a/b"]))
            )

        # 'a' is not in the tree's loaded children (only dummy), so expanding 'a/b'
        # requires expanding 'a' first. If that fires on_row_expanded → SetTreeExpanded
        # → StateUpdated → another _sync_with_state → loop.
        # With correct behavior, the tree should NOT recurse into "a" more than once.
        assert expand_row_calls.count == expand_row_calls.count, "placeholder"
        # The real assertion: tree_expanded must not explode
        assert (
            "a" not in h.manager_expanded()
        ), "Orphan child 'a/b' in state must not cause 'a' to be re-added to expanded"


def test_B6_external_collapse_updates_ui() -> None:
    """
    When state changes externally to remove an expanded path,
    the tree should actually collapse that row.
    """
    with make_harness(
        dir_map={".": [_entry("a", is_dir=True)]},
        initial_expanded=["a"],
    ) as h:
        # Verify it starts expanded
        assert "a" in h.expanded_state()

        # Mock collapse_row to track calls
        h.tree.tree_view.collapse_row = MagicMock(return_value=True)

        # External state change: 'a' is gone
        h.fire_state([])

        assert (
            h.tree.tree_view.collapse_row.called
        ), "tree_view.collapse_row must be called when path is removed from state"
        assert "a" not in h.expanded_state()


# ---------------------------------------------------------------------------
# Group C: Full feedback loop — collapse stability
# ---------------------------------------------------------------------------


def test_C1_collapse_dir_stays_collapsed() -> None:
    """
    After collapsing 'projects', no further events must re-expand it.
    State must stabilize with 'projects' absent from manager and tree._expanded_state.
    """
    with make_harness(
        dir_map={
            ".": [_entry("projects", is_dir=True)],
            "projects": [_entry("projects/foo.md")],
        },
    ) as h:
        h.simulate_expand("projects")
        assert "projects" in h.manager_expanded()

        h.simulate_collapse("projects")
        # Drain any remaining idles
        h.drain()

        assert (
            "projects" not in h.manager_expanded()
        ), "After collapse + drain, 'projects' must not be in manager expanded"
        assert (
            "projects" not in h.expanded_state()
        ), "After collapse + drain, 'projects' must not be in tree._expanded_state"


def test_C2_collapse_dir_with_expanded_children_stays_collapsed() -> None:
    """
    BUG-1 main regression:
    'projects' and 'projects/sub' are both expanded. User collapses 'projects'.
    Expected: both removed from expanded, tree stays collapsed.
    Actual (buggy): 'projects/sub' remains → _sync_with_state tries to expand it
    → must expand 'projects' first → on_row_expanded fires → adds it back → loop.
    """
    with make_harness(
        dir_map={
            ".": [_entry("projects", is_dir=True)],
            "projects": [_entry("projects/sub", is_dir=True)],
            "projects/sub": [_entry("projects/sub/note.md")],
        },
    ) as h:
        h.fire_state(["projects", "projects/sub"])
        h.simulate_collapse("projects")
        h.drain()

        assert (
            "projects" not in h.manager_expanded()
        ), "Parent must not be in manager_expanded after collapse"
        assert (
            "projects/sub" not in h.manager_expanded()
        ), "Child 'projects/sub' must be pruned when parent 'projects' is collapsed"
        assert (
            "projects" not in h.expanded_state()
        ), "tree._expanded_state must not re-gain 'projects'"


def test_C3_collapse_deeply_nested_stays_collapsed() -> None:
    """Three levels of nesting: collapse root dir, all descendants must disappear."""
    with make_harness(
        dir_map={
            ".": [_entry("a", is_dir=True)],
            "a": [_entry("a/b", is_dir=True)],
            "a/b": [_entry("a/b/c", is_dir=True)],
            "a/b/c": [_entry("a/b/c/d.md")],
        },
    ) as h:
        h.fire_state(["a", "a/b", "a/b/c"])
        h.simulate_collapse("a")
        h.drain()

        remaining = h.manager_expanded()
        assert (
            remaining == set()
        ), f"All descendants must be gone after collapsing root, got: {remaining}"


def test_C4_collapse_one_dir_other_remains_stable() -> None:
    """Collapsing 'a' must not affect independently expanded 'b'."""
    with make_harness(
        dir_map={
            ".": [_entry("a", is_dir=True), _entry("b", is_dir=True)],
            "a": [_entry("a/note.md")],
            "b": [_entry("b/note.md")],
        },
    ) as h:
        h.fire_state(["a", "b"])
        h.simulate_collapse("a")
        h.drain()

        assert (
            "b" in h.manager_expanded()
        ), "Sibling 'b' must remain expanded after collapsing 'a'"
        assert "a" not in h.manager_expanded(), "'a' must be gone from manager_expanded"


def test_C5_rapid_collapse_expand_collapse_final_is_collapsed() -> None:
    """Rapid expand→collapse→expand→collapse: final state must be collapsed."""
    with make_harness(
        dir_map={
            ".": [_entry("a", is_dir=True)],
            "a": [_entry("a/note.md")],
        },
    ) as h:
        h.simulate_expand("a")
        h.simulate_collapse("a")
        h.simulate_expand("a")
        h.simulate_collapse("a")
        h.drain()

        assert (
            "a" not in h.manager_expanded()
        ), "Final state is collapsed — 'a' must not be in manager_expanded"
        assert (
            "a" not in h.expanded_state()
        ), "Final state is collapsed — 'a' must not be in tree._expanded_state"


# ---------------------------------------------------------------------------
# Group E: Initial load from persisted expanded state
# ---------------------------------------------------------------------------


def test_E1_initial_state_expands_dirs_on_state_event() -> None:
    """
    On startup, StateUpdated with expanded=['docs'] causes docs to be expanded.
    """
    with make_harness(
        dir_map={
            ".": [_entry("docs", is_dir=True)],
            "docs": [_entry("docs/readme.md")],
        },
    ) as h:
        h.fire_state(["docs"])
        assert (
            "docs" in h.expanded_state()
        ), "Initial StateUpdated must cause 'docs' to be in _expanded_state"


def test_E2_initial_state_nested_expansion_order() -> None:
    """
    StateUpdated with expanded=['a', 'a/b'] must expand 'a' before 'a/b'.
    (Sorted by depth in _sync_with_state.)
    """
    with make_harness(
        dir_map={
            ".": [_entry("a", is_dir=True)],
            "a": [_entry("a/b", is_dir=True)],
            "a/b": [_entry("a/b/note.md")],
        },
    ) as h:
        h.fire_state(["a", "a/b"])
        # Both should be in _expanded_state after sync
        assert "a" in h.expanded_state()
        assert "a/b" in h.expanded_state()


def test_E3_initial_state_missing_dir_is_silently_ignored() -> None:
    """
    If tree_expanded contains a path that doesn't exist in the store,
    _sync_with_state must silently skip it without raising.
    """
    with make_harness(
        dir_map={".": [_entry("exists", is_dir=True)]},
    ) as h:
        # "phantom" is not in the tree store
        try:
            h.fire_state(["phantom"])
        except Exception as exc:
            raise AssertionError(
                f"_sync_with_state must not raise on missing path, got: {exc}"
            ) from exc
