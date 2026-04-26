"""Tests for Editor file lifecycle events: external deletion and rename."""
from pathlib import Path
from unittest.mock import MagicMock

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")

from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.commands import CloseFile, UpdateOpenFilePath  # noqa: E402
from oatbrain.core.events.ui import StatusMessageRequested  # noqa: E402
from oatbrain.core.ports.filestore import VaultPath  # noqa: E402
from oatbrain.ui.editor import Editor  # noqa: E402

VAULT = Path("/fake/vault")


def _make_editor() -> tuple[Editor, CommandRouter, list]:
    filestore = MagicMock()
    event_bus = EventBus()
    command_router = CommandRouter()

    dispatched: list = []
    command_router.register(
        CloseFile, lambda cmd: dispatched.append(cmd), visible=False
    )
    command_router.register(
        UpdateOpenFilePath, lambda cmd: dispatched.append(cmd), visible=False
    )

    editor = Editor(
        filestore=filestore,
        event_bus=event_bus,
        command_router=command_router,
        env=MagicMock(),
        vault_root=VAULT,
        vim_enabled=False,
    )
    return editor, command_router, dispatched


def _call_idle_synchronously(editor_module, event_method, *args):
    """Monkey-patches GLib.idle_add to capture and call the callback synchronously."""
    import oatbrain.ui.editor as editor_mod

    captured = []

    orig = editor_mod.GLib.idle_add

    def capture(fn, *fn_args):
        captured.append((fn, fn_args))

    editor_mod.GLib.idle_add = capture
    try:
        event_method(*args)
    finally:
        editor_mod.GLib.idle_add = orig

    for fn, fn_args in captured:
        fn(*fn_args)


def test_editor_external_clean_deletion_closes_file() -> None:
    """External deletion of a clean file clears current path and shows placeholder."""
    editor, _, _ = _make_editor()

    editor._current_path = VaultPath.from_str("active.md")
    editor._is_dirty = False
    editor._stack.set_visible_child_name("source")

    _call_idle_synchronously(
        None,
        editor._on_file_watched_event,
        "DELETED",
        VAULT / "active.md",
        None,
    )

    assert editor._current_path is None
    assert editor._stack.get_visible_child_name() == "placeholder"


def test_editor_external_dirty_deletion_shows_toast() -> None:
    """External deletion of a dirty file publishes a warning toast."""
    editor, _, dispatched = _make_editor()

    editor._current_path = VaultPath.from_str("active.md")
    editor._is_dirty = True

    received: list[StatusMessageRequested] = []
    editor._event_bus.subscribe(StatusMessageRequested, received.append)

    _call_idle_synchronously(
        None,
        editor._on_file_watched_event,
        "DELETED",
        VAULT / "active.md",
        None,
    )

    assert len(received) == 1
    assert "deleted" in received[0].message.lower()


def test_editor_external_rename_updates_path() -> None:
    """Our file renamed/moved away calls on_path_changed callback."""
    editor, _, _ = _make_editor()
    editor._current_path = VaultPath.from_str("active.md")

    changed_paths = []
    editor.on_path_changed = changed_paths.append

    _call_idle_synchronously(
        None,
        editor._on_file_watched_event,
        "RENAMED",
        VAULT / "active.md",
        VAULT / "new_name.md",
    )

    assert len(changed_paths) == 1
    assert str(changed_paths[0]) == "new_name.md"


def test_editor_rename_onto_open_file_reloads_content() -> None:
    """When a DIFFERENT file is moved onto the currently open file, the editor should
    reload content (not update path). Reproduces the bug: rename 3.md→4.md while 4.md
    is open should show the content of 3.md."""
    editor, _, dispatched = _make_editor()
    editor._current_path = VaultPath.from_str("4.md")

    reload_calls: list[str] = []
    editor._reload_if_clean = (  # type: ignore[method-assign]
        lambda path_str: reload_calls.append(path_str)
    )

    # 3.md is moved onto 4.md (the open file)
    _call_idle_synchronously(
        None,
        editor._on_file_watched_event,
        "RENAMED",
        VAULT / "3.md",  # source (foreign file)
        VAULT / "4.md",  # dest (our open file — content replaced)
    )

    # Should NOT dispatch UpdateOpenFilePath
    assert not any(isinstance(c, UpdateOpenFilePath) for c in dispatched)
    # Should trigger a reload at the open file's path
    assert len(reload_calls) == 1
    assert reload_calls[0] == str(VAULT / "4.md")


def test_editor_rename_of_unrelated_file_is_ignored() -> None:
    """A RENAMED event for two paths neither of which is the open file is a no-op."""
    editor, _, dispatched = _make_editor()
    editor._current_path = VaultPath.from_str("open.md")

    reload_calls: list[str] = []
    editor._reload_if_clean = (  # type: ignore[method-assign]
        lambda path_str: reload_calls.append(path_str)
    )

    _call_idle_synchronously(
        None,
        editor._on_file_watched_event,
        "RENAMED",
        VAULT / "other_src.md",
        VAULT / "other_dst.md",
    )

    assert not dispatched
    assert not reload_calls
