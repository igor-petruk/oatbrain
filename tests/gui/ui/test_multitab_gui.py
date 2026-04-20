import gi
import pytest
from pathlib import Path
from unittest.mock import MagicMock

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, GLib  # noqa: E402

from oatbrain.ui.window import AdwAppShell  # noqa: E402
from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.state.app_state import AppState  # noqa: E402
from oatbrain.core.ports.filestore import FileStore, VaultPath  # noqa: E402
from oatbrain.core.ports.state import StateStore  # noqa: E402
from oatbrain.core.commands import OpenFile  # noqa: E402
from oatbrain.core.commands.editor import (  # noqa: E402
    CloseTab,
    SwitchTab,
    ToggleSplit,
    ToggleMode,
)


def spin_loop():
    """Spin the GLib main loop to process idle tasks (limited)."""
    for _ in range(20):
        if not GLib.main_context_default().iteration(False):
            break


def sync_gui(app_shell):
    """Force sync tabs and process events."""
    app_shell._sync_tabs_to_state()
    spin_loop()


def make_env() -> MagicMock:
    env = MagicMock()
    env.get_xdg_cache_home.return_value = Path("/tmp/cache")
    return env


@pytest.fixture
def app_shell() -> AdwAppShell:
    event_bus = EventBus()
    command_router = CommandRouter()
    state = AppState(vault_root=Path("/tmp/vault"))
    filestore = MagicMock(spec=FileStore)
    filestore.read_text.return_value = "# Test content"
    state_store = MagicMock(spec=StateStore)

    app = AdwAppShell(
        event_bus=event_bus,
        command_router=command_router,
        initial_state=state,
        filestore=filestore,
        state_store=state_store,
        config=MagicMock(),
        env=make_env(),
        renderer=MagicMock(),
        application_id="org.oatbrain.MultitabTest",
    )
    app.on_activate(app)
    sync_gui(app)
    return app


def test_initial_tab(app_shell):
    """Verify that the app starts with one empty tab."""
    assert app_shell.tab_view.get_n_pages() == 1
    assert app_shell._state.active_tab.open_file is None


def test_open_multiple_tabs(app_shell):
    """Verify that multiple tabs can be opened."""
    path1 = VaultPath.from_str("note1.md")
    path2 = VaultPath.from_str("note2.md")

    app_shell._command_router.dispatch(OpenFile(path=path1))
    sync_gui(app_shell)
    assert app_shell.tab_view.get_n_pages() == 1
    assert app_shell.tab_view.get_nth_page(0).get_title() == "note1.md"

    app_shell._command_router.dispatch(OpenFile(path=path2, new_tab=True))
    sync_gui(app_shell)
    assert app_shell.tab_view.get_n_pages() == 2
    assert app_shell.tab_view.get_nth_page(1).get_title() == "note2.md"
    assert app_shell.tab_view.get_selected_page() == app_shell.tab_view.get_nth_page(1)


def test_switch_tabs(app_shell):
    """Verify switching between tabs via command and UI."""
    path1 = VaultPath.from_str("note1.md")
    path2 = VaultPath.from_str("note2.md")

    app_shell._command_router.dispatch(OpenFile(path=path1))
    app_shell._command_router.dispatch(OpenFile(path=path2, new_tab=True))
    sync_gui(app_shell)

    assert app_shell._state.active_tab_index == 1

    # Switch via command
    app_shell._command_router.dispatch(SwitchTab(index=0))
    sync_gui(app_shell)
    assert app_shell._state.active_tab_index == 0
    assert app_shell.tab_view.get_selected_page() == app_shell.tab_view.get_nth_page(0)

    # Switch via UI (simulated)
    app_shell.tab_view.set_selected_page(app_shell.tab_view.get_nth_page(1))
    sync_gui(app_shell)
    assert app_shell._state.active_tab_index == 1


def test_close_tabs(app_shell):
    """Verify closing tabs."""
    path1 = VaultPath.from_str("note1.md")
    path2 = VaultPath.from_str("note2.md")

    app_shell._command_router.dispatch(OpenFile(path=path1))
    app_shell._command_router.dispatch(OpenFile(path=path2, new_tab=True))
    sync_gui(app_shell)

    app_shell._command_router.dispatch(CloseTab(index=1))
    sync_gui(app_shell)
    assert app_shell.tab_view.get_n_pages() == 1
    assert app_shell._state.active_tab.open_file == path1


def test_split_mode_ui(app_shell):
    """Verify split mode UI structure."""
    path1 = VaultPath.from_str("note1.md")
    app_shell._command_router.dispatch(OpenFile(path=path1))
    sync_gui(app_shell)

    page = app_shell.tab_view.get_selected_page()
    editor = app_shell._editors[page]

    assert not editor._split_mode
    assert editor._stack.get_visible_child_name() == "source"

    app_shell._command_router.dispatch(ToggleSplit())
    sync_gui(app_shell)
    assert editor._split_mode
    assert editor._stack.get_visible_child_name() == "split"
    assert isinstance(editor._split_paned.get_start_child(), Gtk.ScrolledWindow)
    assert editor._split_paned.get_end_child() is not None  # Preview


def test_tab_persistence_simulation(app_shell):
    """Verify that state store saves and loads multiple tabs."""
    path1 = VaultPath.from_str("note1.md")
    path2 = VaultPath.from_str("note2.md")

    app_shell._command_router.dispatch(OpenFile(path=path1))
    app_shell._command_router.dispatch(OpenFile(path=path2, new_tab=True))
    sync_gui(app_shell)

    # Trigger save
    app_shell._save_state()

    # Get the saved state from mock
    saved_state = app_shell._state_store.save.call_args[0][0]
    assert len(saved_state.tabs) == 2
    assert saved_state.tabs[0].open_file == path1
    assert saved_state.tabs[1].open_file == path2
    assert saved_state.active_tab_index == 1


def test_scroll_sync_logic(app_shell):
    """Verify that scrolling source updates internal fraction."""
    path1 = VaultPath.from_str("note1.md")
    app_shell._command_router.dispatch(OpenFile(path=path1))
    sync_gui(app_shell)
    app_shell._command_router.dispatch(ToggleMode())  # Enter read mode to enable sync
    sync_gui(app_shell)

    page = app_shell.tab_view.get_selected_page()
    editor = app_shell._editors[page]

    # Mock adjustment
    adj = editor._source_scroll.get_vadjustment()
    # We must set these because ScrolledWindow defaults them to 0 if not realized
    adj.set_upper(1000)
    adj.set_page_size(200)

    # Scroll to 50%
    adj.set_value(400)  # (1000-200) * 0.5 = 400
    # Manually trigger signal as it might not fire in headless easily
    editor._on_source_scrolled(adj)

    assert editor._scroll_fraction == 0.5
