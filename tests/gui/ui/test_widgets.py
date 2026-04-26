import gi
from unittest.mock import MagicMock
from pathlib import Path

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")
from gi.repository import Adw, Gtk, GtkSource  # noqa: E402

from oatbrain.ui.headerbar import HeaderBar  # noqa: E402
from oatbrain.ui.statusbar import StatusBar  # noqa: E402
from oatbrain.ui.tree import FileTree  # noqa: E402
from oatbrain.ui.editor import Editor  # noqa: E402
from oatbrain.ui.editor_area import EditorArea  # noqa: E402
from oatbrain.ui.window import AdwAppShell  # noqa: E402
from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.state import AppState  # noqa: E402
from oatbrain.core.ports.filestore import FileStore  # noqa: E402
from oatbrain.core.ports.state import StateStore  # noqa: E402


def test_headerbar_instantiation() -> None:
    event_bus = EventBus()
    command_router = CommandRouter()
    header = HeaderBar(event_bus, command_router)
    assert isinstance(header.widget, Adw.HeaderBar)
    assert hasattr(header, "tree_toggle")
    assert hasattr(header, "terminal_toggle")
    assert hasattr(header, "zen_toggle")


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
    env = MagicMock()
    editor = Editor(filestore, event_bus, command_router, env)
    assert isinstance(editor.widget, Gtk.Box)
    assert isinstance(editor.view, GtkSource.View)
    assert isinstance(editor.overlay, Gtk.Overlay)


def test_editor_vim_context_enabled() -> None:
    filestore = MagicMock(spec=FileStore)
    event_bus = EventBus()
    command_router = CommandRouter()
    env = MagicMock()
    editor = Editor(filestore, event_bus, command_router, env, vim_enabled=True)
    assert editor._vim_context is not None
    assert isinstance(editor._vim_context, GtkSource.VimIMContext)
    # Key controller must be wired with set_im_context (canonical setup)
    assert editor._vim_key_ctrl is not None
    assert isinstance(editor._vim_key_ctrl, Gtk.EventControllerKey)


def test_editor_vim_context_disabled() -> None:
    filestore = MagicMock(spec=FileStore)
    event_bus = EventBus()
    command_router = CommandRouter()
    env = MagicMock()
    editor = Editor(filestore, event_bus, command_router, env, vim_enabled=False)
    assert editor._vim_context is None
    assert editor._vim_key_ctrl is None


def test_editor_save_emits_dirty_state_changed() -> None:
    from oatbrain.core.ports.filestore import VaultPath
    from oatbrain.core.events.ui import DirtyStateChanged

    filestore = MagicMock(spec=FileStore)
    event_bus = EventBus()
    events = []
    event_bus.subscribe(DirtyStateChanged, events.append)

    command_router = CommandRouter()
    env = MagicMock()
    editor = Editor(filestore, event_bus, command_router, env, vim_enabled=False)
    editor._current_path = VaultPath.from_str("test.md")
    editor._is_dirty = True

    editor._save()

    filestore.write_text.assert_called_once()
    assert any(not e.dirty for e in events if isinstance(e, DirtyStateChanged))


def test_app_shell_activation_smoke() -> None:
    """
    Verifies that the main application shell can be activated and
    all its widgets are instantiated without AttributeError.
    """
    event_bus = EventBus()
    command_router = CommandRouter()
    state = AppState(vault_root=Path("/tmp"))
    filestore = MagicMock(spec=FileStore)
    state_store = MagicMock(spec=StateStore)

    app = AdwAppShell(
        event_bus=event_bus,
        command_router=command_router,
        initial_state=state,
        filestore=filestore,
        state_store=state_store,
        config=MagicMock(),
        env=MagicMock(),
        application_id="org.oatbrain.TestApp",
    )

    # Manually trigger on_activate to test widget creation logic
    # without starting the main loop.
    app.on_activate(app)

    assert isinstance(app.main_window, Adw.ApplicationWindow)
    assert isinstance(app.editor_area, EditorArea)
    assert isinstance(app.tree_pane, FileTree)


def test_app_shell_shutdown_saves_state() -> None:
    """Verifies that state is saved on shutdown without error."""
    event_bus = EventBus()
    command_router = CommandRouter()
    state = AppState(vault_root=Path("/tmp"))
    filestore = MagicMock(spec=FileStore)
    state_store = MagicMock(spec=StateStore)

    app = AdwAppShell(
        event_bus=event_bus,
        command_router=command_router,
        initial_state=state,
        filestore=filestore,
        state_store=state_store,
        config=MagicMock(),
        env=MagicMock(),
        application_id="org.oatbrain.ShutdownTest",
    )

    app.on_activate(app)

    # Simulate shutdown
    app.emit("shutdown")

    # Verify save was called
    state_store.save.assert_called()
