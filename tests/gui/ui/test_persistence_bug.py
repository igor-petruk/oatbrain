import gi
from pathlib import Path
from unittest.mock import MagicMock
from dataclasses import replace

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")

from oatbrain.core.state import AppState  # noqa: E402
from oatbrain.core.ports.filestore import VaultPath  # noqa: E402
from oatbrain.ui.editor import Editor  # noqa: E402


def test_editor_mode_recovers_to_preview_when_returning_to_markdown() -> None:
    # Setup
    filestore = MagicMock()
    event_bus = MagicMock()
    command_router = MagicMock()
    renderer = MagicMock()
    env = MagicMock()

    editor = Editor(filestore, event_bus, command_router, env, renderer=renderer)
    state = AppState(vault_root=Path("/tmp"))

    # 1. Open MD file in Preview mode
    md_path = VaultPath("test.md")
    state = replace(
        state, editor=replace(state.editor, open_file=md_path, read_mode=True)
    )

    editor.update_from_state(state.editor, state)
    assert editor._stack.get_visible_child_name() == "preview"

    # 2. Open non-MD file (forces 'source')
    txt_path = VaultPath("test.txt")
    state = replace(
        state, editor=replace(state.editor, open_file=txt_path, read_mode=True)
    )
    editor.update_from_state(state.editor, state)
    assert editor._stack.get_visible_child_name() == "source"

    # 3. Back to MD (should restore Preview mode based on state)
    state = replace(
        state, editor=replace(state.editor, open_file=md_path, read_mode=True)
    )
    editor.update_from_state(state.editor, state)
    assert editor._stack.get_visible_child_name() == "preview"
