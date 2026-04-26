import gi
import pytest
import os
from dataclasses import replace

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, GLib  # noqa: E402

from oatbrain.app.bootstrap import build_app  # noqa: E402
from oatbrain.core.commands import OpenFile  # noqa: E402
from oatbrain.core.commands.editor import (  # noqa: E402
    SplitGroupRight,
    CloseTab,
    NewTab,
)
from oatbrain.core.ports.filestore import VaultPath  # noqa: E402


def _run_loop(loop, iterations=10):
    for _ in range(iterations):
        GLib.idle_add(loop.quit)
        loop.run()


@pytest.fixture
def app_and_loop(tmp_path):
    # Use a temporary state file to avoid interference from/to local dev state
    os.environ["XDG_STATE_HOME"] = str(tmp_path)

    app, _ = build_app([])
    app.set_application_id(f"org.oatbrain.TestComplex{os.getpid()}")
    app.register()
    app.emit("startup")
    app.activate()

    loop = GLib.MainLoop()
    _run_loop(loop)

    yield app, loop

    for window in app.get_windows():
        window.close()
    app.emit("shutdown")


def test_complex_split_and_tab_flow(app_and_loop):
    """
    Test a complex sequence of splits and tab operations to ensure stability
    and correct state propagation across groups.
    """
    app, loop = app_and_loop

    # Initial state: 1 group, 1 tab
    ea = app._state.editor_area
    assert len(ea.groups) == 1
    assert len(ea.groups[0].tabs) == 1

    # 1. Add a second tab to Group 0
    app._command_router.dispatch(NewTab())
    _run_loop(loop)

    ea = app._state.editor_area
    assert len(ea.groups) == 1
    assert len(ea.groups[0].tabs) == 2
    assert ea.groups[0].active_tab_index == 1

    # 2. Split Group 0 to the right
    # This should create Group 1 with a clone of the active tab from Group 0
    app._command_router.dispatch(SplitGroupRight())
    _run_loop(loop)

    ea = app._state.editor_area
    assert len(ea.groups) == 2
    assert len(ea.groups[1].tabs) == 1
    assert ea.focused_group_index == 1

    # 3. Split Group 1 to the right again
    app._command_router.dispatch(SplitGroupRight())
    _run_loop(loop)

    ea = app._state.editor_area
    assert len(ea.groups) == 3
    assert ea.focused_group_index == 2

    # 4. Close the middle group (Group 1)
    # Focus group 1 first
    app.editor_area._on_state_change_requested(replace(ea, focused_group_index=1))
    _run_loop(loop)
    app._command_router.dispatch(CloseTab())
    _run_loop(loop)

    ea = app._state.editor_area
    # Since Group 1 had only one tab, closing it removes the group
    assert len(ea.groups) == 2

    # 5. Verify widget structure
    # EditorArea should have a Gtk.Paned with two children
    paned = app.editor_area._paned_root
    assert isinstance(paned, Gtk.Paned)
    assert paned.get_start_child() is not None
    assert paned.get_end_child() is not None


def test_focus_switching_between_groups(app_and_loop):
    """Verify that clicking an editor in a group updates the focused group index."""
    app, loop = app_and_loop

    # 1. Create two groups
    app._command_router.dispatch(SplitGroupRight())
    _run_loop(loop)

    ea = app._state.editor_area
    assert ea.focused_group_index == 1

    # 2. Manually trigger focus on an editor in Group 0
    # We find an editor in Group 0's GroupPane
    gid0 = ea.groups[0].group_id
    pane0 = app.editor_area.groups_panes[gid0]
    tid0 = ea.groups[0].tabs[0].tab_id
    editor0 = pane0.editors[tid0]

    # Simulate focus
    app.editor_area._on_editor_focused(editor0)
    _run_loop(loop)

    assert app._state.editor_area.focused_group_index == 0

    # 3. Trigger focus back to Group 1
    gid1 = ea.groups[1].group_id
    pane1 = app.editor_area.groups_panes[gid1]
    tid1 = ea.groups[1].tabs[0].tab_id
    editor1 = pane1.editors[tid1]

    app.editor_area._on_editor_focused(editor1)
    _run_loop(loop)

    assert app._state.editor_area.focused_group_index == 1


def test_tab_reordering_smoke(app_and_loop):
    """Verify state update when tabs are switched via notebook (UI -> State)."""
    app, loop = app_and_loop

    # 1. Add two tabs
    app._command_router.dispatch(NewTab())
    _run_loop(loop)
    app._command_router.dispatch(NewTab())
    _run_loop(loop)

    ea = app._state.editor_area
    assert len(ea.groups[0].tabs) == 3
    assert ea.groups[0].active_tab_index == 2

    # 2. Switch to tab index 0 in the Notebook
    pane = app.editor_area.groups_panes[ea.groups[0].group_id]
    pane.notebook.set_current_page(0)
    # The 'switch-page' signal should trigger
    # _on_tab_switched -> _on_state_change_requested
    _run_loop(loop)

    assert app._state.editor_area.groups[0].active_tab_index == 0


def test_new_tab_button_in_group_pane(app_and_loop):
    """Verify that clicking the '+' button in GroupPane creates a new tab."""
    app, loop = app_and_loop

    # 1. Initial state: 1 group, 1 tab
    ea = app._state.editor_area
    assert len(ea.groups[0].tabs) == 1

    # 2. Find the '+' button in the first GroupPane and click it
    gid0 = ea.groups[0].group_id
    pane = app.editor_area.groups_panes[gid0]

    # Trigger the button's clicked signal
    pane._btn_new_tab.emit("clicked")
    _run_loop(loop)

    # 3. Verify state updated
    assert len(app._state.editor_area.groups[0].tabs) == 2


def test_mode_switch_targets_correct_tab(app_and_loop):
    """
    Verify that clicking the mode toggle in an unfocused tab
    only affects that tab.
    """
    app, loop = app_and_loop

    # 1. Open a markdown file so toggle is visible
    test_path = VaultPath.from_str("test_mode.md")
    app._command_router.dispatch(OpenFile(path=test_path))
    _run_loop(loop)

    # 2. Split to have two tabs (in different groups for easier tracking)
    app._command_router.dispatch(SplitGroupRight())
    _run_loop(loop)

    ea = app._state.editor_area
    assert len(ea.groups) == 2
    assert ea.focused_group_index == 1

    # Group 1 is focused. Tab 0 in Group 0 is NOT focused.
    gid0 = ea.groups[0].group_id
    pane0 = app.editor_area.groups_panes[gid0]
    tid0 = ea.groups[0].tabs[0].tab_id
    editor0 = pane0.editors[tid0]

    # Verify initial mode is 'editor'
    assert ea.groups[0].tabs[0].mode == "editor"
    assert ea.groups[1].tabs[0].mode == "editor"

    # 3. Toggle mode on the UNIFOCUSED tab (Group 0)
    # Trigger the 'Read' button on the unfocused editor0
    editor0._btn_read.emit("clicked")
    _run_loop(loop)

    # 4. Verify only Group 0 tab mode changed
    new_ea = app._state.editor_area
    assert new_ea.groups[0].tabs[0].mode == "preview"
    assert new_ea.groups[1].tabs[0].mode == "editor"


def test_divider_fractions_are_saved(app_and_loop):
    """Verify that moving a divider updates the state with the new fraction."""
    app, loop = app_and_loop

    # 1. Split to have two groups
    app._command_router.dispatch(SplitGroupRight())
    _run_loop(loop)

    ea = app._state.editor_area
    assert len(ea.groups) == 2
    assert len(app.editor_area._paned_widgets) == 1

    paned = app.editor_area._paned_widgets[0]

    # Force a width for calculation (though in tests it might be small/zero)
    # If width is 0, we can't test real fraction, but we can mock or check logic.
    # Fortunately xvfb usually gives some default window size.

    width = paned.get_width()
    if width <= 0:
        # Fallback if window not fully realized/sized in test environment
        paned.set_size_request(1000, 800)
        _run_loop(loop)
        width = paned.get_width()

    if width > 0:
        # 2. Move divider to 25% (0.25)
        new_pos = int(width * 0.25)
        paned.set_position(new_pos)
        _run_loop(loop)

        # 3. Verify state updated
        new_ea = app._state.editor_area
        assert len(new_ea.divider_fractions) == 1
        # Use approx for float comparison
        assert pytest.approx(new_ea.divider_fractions[0], rel=0.01) == 0.25
