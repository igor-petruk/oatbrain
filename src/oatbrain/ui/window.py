from typing import Any
from dataclasses import replace
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.state.app_state import AppState  # noqa: E402
from oatbrain.core.events.state import StateUpdated  # noqa: E402
from oatbrain.core.commands import OpenFile  # noqa: E402
from oatbrain.core.commands.editor import UpdateWordCount  # noqa: E402
from oatbrain.core.ports.filestore import FileStore  # noqa: E402
from oatbrain.ui.headerbar import HeaderBar  # noqa: E402
from oatbrain.ui.statusbar import StatusBar  # noqa: E402
from oatbrain.ui.tree import FileTree  # noqa: E402
from oatbrain.ui.editor import Editor  # noqa: E402


class AdwAppShell(Adw.Application):  # type: ignore[misc]
    """Main application shell using Libadwaita."""

    def __init__(
        self,
        event_bus: EventBus,
        command_router: CommandRouter,
        initial_state: AppState,
        filestore: FileStore,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._event_bus = event_bus
        self._command_router = command_router
        self._state = initial_state
        self._filestore = filestore

        self._command_router.register(OpenFile, self._handle_open_file)
        self._command_router.register(
            UpdateWordCount, self._handle_update_word_count
        )

        self.connect("activate", self.on_activate)

    def _handle_open_file(self, command: OpenFile) -> None:
        """Updates state when a file is opened."""
        new_editor = replace(
            self._state.editor, open_file=command.path, word_count=0
        )
        self._state = replace(
            self._state,
            editor=new_editor,
            status_message=f"Opened {command.path}"
        )
        self._event_bus.publish(StateUpdated(self._state))

    def _handle_update_word_count(self, command: UpdateWordCount) -> None:
        """Updates word count in state."""
        new_editor = replace(self._state.editor, word_count=command.count)
        self._state = replace(self._state, editor=new_editor)
        self._event_bus.publish(StateUpdated(self._state))

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
        self.tree_pane = FileTree(
            self._filestore, self._event_bus, self._command_router
        )

        self.editor = Editor(
            self._filestore, self._event_bus, self._command_router
        )

        self.terminal_placeholder = Gtk.Frame(label="Terminal")
        self.terminal_placeholder.set_focusable(True)
        self.terminal_placeholder.set_child(
            Gtk.Label(label="[Terminal Placeholder]")
        )

        # Setup main_paned (Tree vs Rest)
        self.main_paned.set_start_child(self.tree_pane)
        self.main_paned.set_end_child(self.right_paned)
        self.main_paned.set_position(180)  # 15% of 1200

        # Setup right_paned (Editor vs Terminal)
        self.right_paned.set_start_child(self.editor.widget)
        self.right_paned.set_end_child(self.terminal_placeholder)
        # (1200-180)-360 = 660 (30% total for terminal)
        self.right_paned.set_position(660)

        self.toolbar_view.set_content(self.main_paned)

        # Status Bar
        self.status_bar = StatusBar(self._event_bus)
        self.toolbar_view.add_bottom_bar(self.status_bar.widget)

        # Wire Toggles
        self.header_bar.tree_toggle.connect("toggled", self._on_tree_toggled)
        self.header_bar.terminal_toggle.connect(
            "toggled", self._on_terminal_toggled
        )

        # Shortcuts
        self._setup_shortcuts()

        self.main_window.present()

        # Emit initial state
        self._event_bus.publish(StateUpdated(self._state))

    def _on_tree_toggled(self, btn: Gtk.ToggleButton) -> None:
        self.tree_pane.set_visible(btn.get_active())

    def _on_terminal_toggled(self, btn: Gtk.ToggleButton) -> None:
        self.terminal_placeholder.set_visible(btn.get_active())

    def _setup_shortcuts(self) -> None:
        controller = Gtk.ShortcutController.new()
        self.main_window.add_controller(controller)

        # Ctrl+B: Toggle Tree
        controller.add_shortcut(Gtk.Shortcut.new(
            trigger=Gtk.ShortcutTrigger.parse_string("<Control>b"),
            action=Gtk.CallbackAction.new(self._shortcut_toggle_tree)
        ))

        # Ctrl+`: Toggle Terminal
        controller.add_shortcut(Gtk.Shortcut.new(
            trigger=Gtk.ShortcutTrigger.parse_string("<Control>grave"),
            action=Gtk.CallbackAction.new(self._shortcut_toggle_terminal)
        ))

        # Ctrl+1: Focus Tree
        controller.add_shortcut(Gtk.Shortcut.new(
            trigger=Gtk.ShortcutTrigger.parse_string("<Control>1"),
            action=Gtk.CallbackAction.new(
                lambda *_: self.tree_pane.grab_focus() or True
            )
        ))

        # Ctrl+2: Focus Editor
        controller.add_shortcut(Gtk.Shortcut.new(
            trigger=Gtk.ShortcutTrigger.parse_string("<Control>2"),
            action=Gtk.CallbackAction.new(
                lambda *_: self.editor.view.grab_focus() or True
            )
        ))

        # Ctrl+3: Focus Terminal
        controller.add_shortcut(Gtk.Shortcut.new(
            trigger=Gtk.ShortcutTrigger.parse_string("<Control>3"),
            action=Gtk.CallbackAction.new(
                lambda *_: self.terminal_placeholder.grab_focus() or True
            )
        ))

    def _shortcut_toggle_tree(self, *_: Any) -> bool:
        self.header_bar.tree_toggle.set_active(
            not self.header_bar.tree_toggle.get_active()
        )
        return True

    def _shortcut_toggle_terminal(self, *_: Any) -> bool:
        self.header_bar.terminal_toggle.set_active(
            not self.header_bar.terminal_toggle.get_active()
        )
        return True
