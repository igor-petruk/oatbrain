import logging
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib  # noqa: E402
from oatbrain.app.bootstrap import build_app  # noqa: E402

logger = logging.getLogger(__name__)

def test_app_smoke_launch():
    """Smoke test to verify the app can instantiate its main window and panes."""
    logger.info("Starting app smoke launch test")
    app = build_app([])
    
    # We use a flag to track if we successfully verified the window
    verified = {"window": False, "panes": False}

    def on_activate(app):
        logger.info("App activated: on_activate triggered")
        # The window is created in on_activate
        window = app.get_active_window()
        assert window is not None
        assert isinstance(window, Adw.ApplicationWindow)
        assert "oatbrain" in window.get_title()
        logger.info(f"Verified window found with title: {window.get_title()}")
        verified["window"] = True

        # Traverse to find the main paned and check for 3 distinct areas
        # AdwApplicationWindow -> AdwToolbarView -> GtkPaned (main) -> GtkPaned (right)
        content = window.get_content()
        assert isinstance(content, Adw.ToolbarView)
        
        main_paned = content.get_content()
        assert isinstance(main_paned, Gtk.Paned)
        
        # Check for Tree and Right Paned
        assert main_paned.get_start_child() is not None # Tree
        right_paned = main_paned.get_end_child()
        assert isinstance(right_paned, Gtk.Paned)
        
        # Check for Editor and Terminal
        assert right_paned.get_start_child() is not None # Editor
        assert right_paned.get_end_child() is not None   # Terminal
        
        logger.info("Verified UI hierarchy: all 3 panes found")
        verified["panes"] = True
        
        logger.info("Quitting app from within test")
        app.quit()

    app.connect("activate", on_activate)
    
    # Run the app for a short moment
    # Since we are in a test, we don't want it to block forever if activate fails
    def on_timeout():
        logger.warning("Safety timeout reached, force quitting app")
        app.quit()
        return GLib.SOURCE_REMOVE

    GLib.timeout_add(2000, on_timeout) # 2s timeout
    
    logger.info("Running app main loop")
    app.run(None)
    logger.info("App main loop exited")
    
    assert verified["window"], "App window was not activated"
    assert verified["panes"], "App panes were not found in hierarchy"
    logger.info("Test completed successfully")
