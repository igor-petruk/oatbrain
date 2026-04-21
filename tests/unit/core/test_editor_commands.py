from pathlib import Path
from dataclasses import replace

from oatbrain.core.state.app_state import AppState
from oatbrain.core.commands.editor import ToggleMode


def _base_state() -> AppState:
    return AppState(vault_root=Path("/tmp"))


def test_toggle_mode_command_instantiates() -> None:
    cmd = ToggleMode()
    assert isinstance(cmd, ToggleMode)


def test_toggle_mode_state_transition() -> None:
    state = _base_state()
    assert state.editor.read_mode is False
    state = replace(state, editor=replace(state.editor, read_mode=True))
    assert state.editor.read_mode is True
    state = replace(state, editor=replace(state.editor, read_mode=False))
    assert state.editor.read_mode is False
