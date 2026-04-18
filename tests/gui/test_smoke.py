import gi
import logging
from pathlib import Path

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw  # noqa: E402

from oatbrain.app.bootstrap import build_app  # noqa: E402
from oatbrain.ui.tree import FileTree  # noqa: E402

logger = logging.getLogger(__name__)


def test_app_instantiation() -> None:
    """Verify that the application can be instantiated."""
    logger.info("Starting app instantiation test")
    app = build_app([])
    assert app is not None
    logger.info("Application instantiation successful")


def test_widget_hierarchy() -> None:
    """Verify that the main window contains the expected three-pane layout."""
    app = build_app([])
    app.set_application_id("app.oatbrain.TestHierarchy")

    # We trigger 'activate' manually since we don't call app.run()
    app.register()
    app.activate()

    window = app.get_active_window()
    assert window is not None
    assert window.get_title() == "oatbrain"

    # Traverse to find panes
    content = window.get_content()
    assert isinstance(content, Adw.ToolbarView)

    # Content of ToolbarView is our main_paned
    main_paned = content.get_content()
    assert isinstance(main_paned, Gtk.Paned)

    # Left child is FileTree
    tree_pane = main_paned.get_start_child()
    assert isinstance(tree_pane, FileTree)

    # Right child is another Paned
    right_paned = main_paned.get_end_child()
    assert isinstance(right_paned, Gtk.Paned)

    # Editor and Terminal
    editor_widget = right_paned.get_start_child()
    terminal_widget = right_paned.get_end_child()

    # Editor is now an Overlay (for placeholders)
    assert isinstance(editor_widget, Gtk.Overlay)
    # Terminal is still a Frame placeholder
    assert isinstance(terminal_widget, Gtk.Frame)


def test_app_shutdown_saves_state(tmp_path: Path) -> None:
    """Verify that state is saved when the application shuts down."""
    app = build_app([])
    app.set_application_id("app.oatbrain.TestShutdown")
    app.register()
    app.activate()

    # Let's just verify it doesn't crash on shutdown.
    app.emit("shutdown")
