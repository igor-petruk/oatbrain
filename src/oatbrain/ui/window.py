from typing import Any
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402


class AdwAppShell(Adw.Application):  # type: ignore[misc]
    """Main application shell using Libadwaita."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.connect("activate", self.on_activate)

    def on_activate(self, app: Adw.Application) -> None:
        self.main_window = Adw.ApplicationWindow(application=app)
        self.main_window.set_title("oatbrain")
        self.main_window.set_default_size(1200, 800)

        # Main layout using ToolbarView for header/footer support
        self.toolbar_view = Adw.ToolbarView()
        self.main_window.set_content(self.toolbar_view)

        # Header Bar
        self.header_bar = Adw.HeaderBar()
        self.toolbar_view.add_top_bar(self.header_bar)

        # Three-pane layout using nested Gtk.Paned (SPEC §6.2)
        # Structure: [ Tree | [ Editor | Terminal ] ]
        self.main_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.right_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)

        # Placeholders for panes
        self.tree_placeholder = Gtk.Frame(label="File Tree")
        self.tree_placeholder.set_child(Gtk.Label(label="[Tree Placeholder]"))

        self.editor_placeholder = Gtk.Frame(label="Editor / Preview")
        self.editor_placeholder.set_child(Gtk.Label(label="[Editor Placeholder]"))

        self.terminal_placeholder = Gtk.Frame(label="Terminal")
        self.terminal_placeholder.set_child(Gtk.Label(label="[Terminal Placeholder]"))

        # Setup main_paned (Tree vs Rest)
        self.main_paned.set_start_child(self.tree_placeholder)
        self.main_paned.set_end_child(self.right_paned)
        self.main_paned.set_position(180)  # ~15% of 1200

        # Setup right_paned (Editor vs Terminal)
        self.right_paned.set_start_child(self.editor_placeholder)
        self.right_paned.set_end_child(self.terminal_placeholder)
        self.right_paned.set_position(660)  # ~30% for terminal in the end

        self.toolbar_view.set_content(self.main_paned)

        # Status Bar placeholder
        self.status_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.status_bar.set_margin_start(12)
        self.status_bar.set_margin_end(12)
        self.status_bar.set_margin_top(6)
        self.status_bar.set_margin_bottom(6)
        self.status_bar.append(Gtk.Label(label="Ready"))
        self.toolbar_view.add_bottom_bar(self.status_bar)

        self.main_window.present()
