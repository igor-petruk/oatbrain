from pathlib import Path
from dataclasses import replace

from oatbrain.core.state import AppState, EditorAreaState, GroupState, TabState
from oatbrain.core.commands.editor import ToggleMode


def _base_state() -> AppState:
    return AppState(vault_root=Path("/tmp"))


def test_toggle_mode_command_instantiates() -> None:
    cmd = ToggleMode()
    assert isinstance(cmd, ToggleMode)


def test_toggle_mode_state_transition() -> None:
    tab = TabState(mode="editor")
    group = GroupState(tabs=(tab,))
    ea = EditorAreaState(groups=(group,))
    state = AppState(vault_root=Path("/tmp"), editor_area=ea)

    assert state.editor_area.groups[0].tabs[0].mode == "editor"

    # Simulate toggling to preview
    new_tab = replace(tab, mode="preview")
    new_group = replace(group, tabs=(new_tab,))
    state = replace(state, editor_area=replace(ea, groups=(new_group,)))
    assert state.editor_area.groups[0].tabs[0].mode == "preview"

    # Simulate toggling back
    new_tab2 = replace(new_tab, mode="editor")
    new_group2 = replace(new_group, tabs=(new_tab2,))
    state = replace(state, editor_area=replace(state.editor_area, groups=(new_group2,)))
    assert state.editor_area.groups[0].tabs[0].mode == "editor"
