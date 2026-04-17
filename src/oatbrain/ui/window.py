from typing import Any
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.state.app_state import AppState  # noqa: E402
from oatbrain.core.events.state import StateUpdated  # noqa: E402
from oatbrain.ui.headerbar import HeaderBar  # noqa: E402
from oatbrain.ui.statusbar import StatusBar  # noqa: E402


class AdwAppShell(Adw.Application):  # type: ignore[misc]
    """Main application shell using Libadwaita."""

    def __init__(
        self,
        event_bus: EventBus,
        command_router: CommandRouter,
        initial_state: AppState,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._event_bus = event_bus
        self._command_router = command_router
        self._state = initial_state
        self.connect("activate", self.on_activate)

    def on_activate(self, app: Adw.Application) -> None:
        self.main_window = Adw.ApplicationWindow(application=app)
        self.main_window.set_title("oatbrain")
        self.main_window.set_default_size(1200, 800)

        # Main layout using ToolbarView for header/footer support
        self.toolbar_view = Adw.ToolbarView()
        self.main_window.set_content(self.toolbar_view)

        # Header Bar
        self.header_bar = HeaderBar(self._event_bus)
        self.toolbar_view.add_top_bar(self.header_bar.widget)

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

        # Status Bar
        self.status_bar = StatusBar(self._event_bus)
        self.toolbar_view.add_bottom_bar(self.status_bar.widget)

        self.main_window.present()

        # Emit initial state
        self._event_bus.publish(StateUpdated(self._state))
