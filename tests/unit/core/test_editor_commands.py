from pathlib import Path
from dataclasses import replace

from oatbrain.core.state.app_state import AppState
from oatbrain.core.commands.editor import SetDirty, UpdateWordCount, ToggleMode


def _base_state() -> AppState:
    return AppState(vault_root=Path("/tmp"))


def test_set_dirty_true() -> None:
    state = _base_state()
    new_editor = replace(state.editor, is_dirty=True)
    state = replace(state, editor=new_editor)
    assert state.editor.is_dirty is True


def test_set_dirty_false() -> None:
    state = _base_state()
    new_editor = replace(state.editor, is_dirty=True)
    state = replace(state, editor=new_editor)
    new_editor = replace(state.editor, is_dirty=False)
    state = replace(state, editor=new_editor)
    assert state.editor.is_dirty is False


def test_set_dirty_command_fields() -> None:
    cmd = SetDirty(dirty=True)
    assert cmd.dirty is True


def test_update_word_count_command_fields() -> None:
    cmd = UpdateWordCount(count=42)
    assert cmd.count == 42


def test_toggle_mode_command_instantiates() -> None:
    cmd = ToggleMode()
    assert isinstance(cmd, ToggleMode)


def test_toggle_mode_state_transition() -> None:
    state = _base_state()
    assert state.editor.read_mode is False
    new_editor = replace(state.editor, read_mode=True)
    state = replace(state, editor=new_editor)
    assert state.editor.read_mode is True
    new_editor = replace(state.editor, read_mode=False)
    state = replace(state, editor=new_editor)
    assert state.editor.read_mode is False
