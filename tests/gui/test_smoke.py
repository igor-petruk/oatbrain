import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib  # noqa: E402
from oatbrain.app.bootstrap import build_app  # noqa: E402
import pytest

def test_app_smoke_launch():
    """Smoke test to verify the app can instantiate its main window and panes."""
    app = build_app([])
    
    # We use a flag to track if we successfully verified the window
    verified = {"window": False, "panes": False}

    def on_activate(app):
        # The window is created in on_activate
        window = app.get_active_window()
        assert window is not None
        assert isinstance(window, Adw.ApplicationWindow)
        assert "oatbrain" in window.get_title()
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
        
        verified["panes"] = True
        app.quit()

    app.connect("activate", on_activate)
    
    # Run the app for a short moment
    # Since we are in a test, we don't want it to block forever if activate fails
    GLib.timeout_add(1000, app.quit) # Safety timeout
    app.run(None)
    
    assert verified["window"], "App window was not activated"
    assert verified["panes"], "App panes were not found in hierarchy"
