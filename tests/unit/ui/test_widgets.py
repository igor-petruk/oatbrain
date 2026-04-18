import gi
from unittest.mock import MagicMock
from pathlib import Path

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('GtkSource', '5')
from gi.repository import Adw, Gtk, GtkSource  # noqa: E402

from oatbrain.ui.headerbar import HeaderBar  # noqa: E402
from oatbrain.ui.statusbar import StatusBar  # noqa: E402
from oatbrain.ui.tree import FileTree  # noqa: E402
from oatbrain.ui.editor import Editor  # noqa: E402
from oatbrain.ui.window import AdwAppShell  # noqa: E402
from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.state.app_state import AppState  # noqa: E402
from oatbrain.core.ports.filestore import FileStore  # noqa: E402

def test_headerbar_instantiation() -> None:
    event_bus = EventBus()
    header = HeaderBar(event_bus)
    assert isinstance(header.widget, Adw.HeaderBar)

def test_statusbar_instantiation() -> None:
    event_bus = EventBus()
    status = StatusBar(event_bus)
    assert isinstance(status.widget, Gtk.Box)

def test_tree_instantiation() -> None:
    filestore = MagicMock(spec=FileStore)
    event_bus = EventBus()
    command_router = CommandRouter()
    tree = FileTree(filestore, event_bus, command_router)
    assert isinstance(tree, Gtk.Box)

def test_editor_instantiation() -> None:
    filestore = MagicMock(spec=FileStore)
    event_bus = EventBus()
    command_router = CommandRouter()
    editor = Editor(filestore, event_bus, command_router)
    assert isinstance(editor.widget, Gtk.Overlay)
    assert isinstance(editor.view, GtkSource.View)

def test_app_shell_activation_smoke() -> None:
    """
    Verifies that the main application shell can be activated and
    all its widgets are instantiated without AttributeError.
    """
    event_bus = EventBus()
    command_router = CommandRouter()
    state = AppState(vault_root=Path("/tmp"))
    filestore = MagicMock(spec=FileStore)
    
    app = AdwAppShell(
        event_bus=event_bus,
        command_router=command_router,
        initial_state=state,
        filestore=filestore,
        application_id="org.oatbrain.TestApp"
    )
    
    # Manually trigger on_activate to test widget creation logic
    # without starting the main loop.
    app.on_activate(app)
    
    assert isinstance(app.main_window, Adw.ApplicationWindow)
    assert isinstance(app.editor, Editor)
    assert isinstance(app.tree_pane, FileTree)
