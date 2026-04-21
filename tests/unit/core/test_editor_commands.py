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
    assert state.active_tab.read_mode is False
    tabs = list(state.tabs)
    tabs[0] = replace(tabs[0], read_mode=True)
    state = replace(state, tabs=tabs)
    assert state.active_tab.read_mode is True
    tabs[0] = replace(tabs[0], read_mode=False)
    state = replace(state, tabs=tabs)
    assert state.active_tab.read_mode is False
