from pathlib import Path
from dataclasses import replace

from oatbrain.core.state.app_state import AppState
from oatbrain.core.commands.editor import SetDirty, UpdateVimMode, UpdateWordCount


def _base_state() -> AppState:
    return AppState(vault_root=Path("/tmp"))


def test_editor_state_default_vim_mode() -> None:
    state = _base_state()
    assert state.editor.vim_mode == "NORMAL"


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


def test_update_vim_mode() -> None:
    state = _base_state()
    for mode in ("INSERT", "VISUAL", "REPLACE", "NORMAL"):
        new_editor = replace(state.editor, vim_mode=mode)
        state = replace(state, editor=new_editor)
        assert state.editor.vim_mode == mode


def test_set_dirty_command_fields() -> None:
    cmd = SetDirty(dirty=True)
    assert cmd.dirty is True


def test_update_vim_mode_command_fields() -> None:
    cmd = UpdateVimMode(mode="INSERT")
    assert cmd.mode == "INSERT"


def test_update_word_count_command_fields() -> None:
    cmd = UpdateWordCount(count=42)
    assert cmd.count == 42
