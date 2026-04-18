from typing import Any, List
from dataclasses import replace
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, Gio, GLib  # noqa: E402

from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.state.app_state import AppState  # noqa: E402
from oatbrain.core.events.state import StateUpdated  # noqa: E402
from oatbrain.core.commands import OpenFile  # noqa: E402
from oatbrain.core.commands.editor import UpdateWordCount  # noqa: E402
from oatbrain.core.ports.filestore import FileStore  # noqa: E402
from oatbrain.core.ports.state import StateStore  # noqa: E402
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
        state_store: StateStore,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._event_bus = event_bus
        self._command_router = command_router
        self._state = initial_state
        self._filestore = filestore
        self._state_store = state_store

        self._command_router.register(OpenFile, self._handle_open_file)
        self._command_router.register(
            UpdateWordCount, self._handle_update_word_count
        )

        self.connect("activate", self.on_activate)
        self.connect("shutdown", self._on_shutdown)

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
        self._save_state()

    def _handle_update_word_count(self, command: UpdateWordCount) -> None:
        """Updates word count in state."""
        new_editor = replace(self._state.editor, word_count=command.count)
        self._state = replace(self._state, editor=new_editor)
        self._event_bus.publish(StateUpdated(self._state))

    def _save_state(self) -> None:
        """Collects current UI state and persists it via StateStore."""
        if not hasattr(self, "main_window") or not self.main_window.get_realized():
            return

        # Get current dimensions
        width = self.main_window.get_width()
        height = self.main_window.get_height()

        # Get pane visibility
        tree_visible = self.tree_pane.get_visible()
        terminal_visible = self.terminal_placeholder.get_visible()

        # Get pane positions (only update if visible and reasonable)
        tree_width = self._state.tree_width
        if tree_visible:
            pos = self.main_paned.get_position()
            if pos > 0:
                tree_width = pos

        terminal_width = self._state.terminal_width
        if terminal_visible:
            total_right = self.right_paned.get_width()
            pos = self.right_paned.get_position()
            if total_right > 0 and pos > 0:
                terminal_width = total_right - pos

        self._state = replace(
            self._state,
            window_width=width,
            window_height=height,
            tree_width=tree_width,
            tree_visible=tree_visible,
            terminal_width=terminal_width,
            terminal_visible=terminal_visible,
        )
        self._state_store.save(self._state)

    def _on_shutdown(self, *args: Any) -> None:
        """Ensures state is saved on application exit."""
        self._save_state()

    def on_activate(self, app: Adw.Application) -> None:
        # 1. Build window
        self.main_window = Adw.ApplicationWindow(application=app)
        self.main_window.set_title("oatbrain")
        self.main_window.set_default_size(
            self._state.window_width, self._state.window_height
        )

        # 2. Build layout components
        self.toolbar_view = Adw.ToolbarView()
        self.header_bar = HeaderBar(self._event_bus)
        self.toolbar_view.add_top_bar(self.header_bar.widget)

        self.main_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.right_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)

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

        # 3. Assemble hierarchy (Bottom-Up)
        self.right_paned.set_start_child(self.editor.widget)
        self.right_paned.set_end_child(self.terminal_placeholder)
        self.right_paned.set_resize_start_child(True)
        self.right_paned.set_resize_end_child(False)

        self.main_paned.set_start_child(self.tree_pane)
        self.main_paned.set_end_child(self.right_paned)
        self.main_paned.set_resize_start_child(False)
        self.main_paned.set_resize_end_child(True)

        self.toolbar_view.set_content(self.main_paned)
        self.status_bar = StatusBar(self._event_bus)
        self.toolbar_view.add_bottom_bar(self.status_bar.widget)

        self.main_window.set_content(self.toolbar_view)

        # 4. Initial layout from state
        self.tree_pane.set_visible(self._state.tree_visible)
        self.header_bar.tree_toggle.set_active(self._state.tree_visible)
        self.terminal_placeholder.set_visible(self._state.terminal_visible)
        self.header_bar.terminal_toggle.set_active(self._state.terminal_visible)
        self.main_paned.set_position(self._state.tree_width)
        self._update_right_paned_position()

        # 5. Wire non-critical signals
        self.header_bar.tree_toggle.connect("toggled", self._on_tree_toggled)
        self.header_bar.terminal_toggle.connect(
            "toggled", self._on_terminal_toggled
        )
        self._setup_actions()
        self._setup_shortcuts()

        # 6. Finalize
        self.main_window.present()

        # 7. Wire proactive saving LATE to avoid construction noise
        GLib.idle_add(self._connect_late_signals)

        # Emit initial state
        self._event_bus.publish(StateUpdated(self._state))

    def _connect_late_signals(self) -> bool:
        """Connects signals that trigger state saving."""
        if not hasattr(self, "main_window") or not self.main_window.get_realized():
             return bool(GLib.SOURCE_CONTINUE)

        self.main_paned.connect(
            "notify::position", lambda *_: self._save_state()
        )
        self.right_paned.connect(
            "notify::position", lambda *_: self._save_state()
        )
        self.main_window.connect(
            "notify::default-width", lambda *_: self._save_state()
        )
        self.main_window.connect(
            "notify::default-height", lambda *_: self._save_state()
        )
        return bool(GLib.SOURCE_REMOVE)

    def _update_right_paned_position(self) -> None:
        """Calculates and sets the right paned position."""
        # Use state width as a proxy before realization.
        total_width = self._state.window_width
        tree_width = self._state.tree_width
        terminal_width = self._state.terminal_width

        editor_target_width = total_width - tree_width - terminal_width
        if editor_target_width > 0:
            self.right_paned.set_position(editor_target_width)

    def _setup_actions(self) -> None:
        """Sets up GActions for the menu items."""
        actions = [
            ("open_config", self._on_open_config),
            ("set_theme_light", lambda *_: self._on_set_theme("Light")),
            ("set_theme_dark", lambda *_: self._on_set_theme("Dark")),
            ("new_note", self._on_new_note),
            ("new_folder", self._on_new_folder),
            ("rename_file", self._on_rename_file),
            ("delete_file", self._on_delete_file),
        ]
        for name, callback in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

    def _on_open_config(self, *args: Any) -> None:
        print("Action: Open config file")

    def _on_set_theme(self, theme: str) -> None:
        print(f"Action: Set theme to {theme}")

    def _on_new_note(self, *args: Any) -> None:
        print("Action: New Note")

    def _on_new_folder(self, *args: Any) -> None:
        print("Action: New Folder")

    def _on_rename_file(self, *args: Any) -> None:
        print("Action: Rename File")

    def _on_delete_file(self, *args: Any) -> None:
        print("Action: Delete File")

    def _on_tree_toggled(self, btn: Gtk.ToggleButton) -> None:
        visible = btn.get_active()
        self.tree_pane.set_visible(visible)
        self._save_state()

    def _on_terminal_toggled(self, btn: Gtk.ToggleButton) -> None:
        visible = btn.get_active()
        self.terminal_placeholder.set_visible(visible)
        self._save_state()

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

        # Ctrl+Tab: Cycle focus (§18.2)
        controller.add_shortcut(Gtk.Shortcut.new(
            trigger=Gtk.ShortcutTrigger.parse_string("<Control>Tab"),
            action=Gtk.CallbackAction.new(self._shortcut_cycle_focus)
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

    def _shortcut_cycle_focus(self, *_: Any) -> bool:
        targets: List[Gtk.Widget] = [
            self.tree_pane,
            self.editor.view,
            self.terminal_placeholder
        ]

        current = self.main_window.get_focus()

        start_idx = 0
        if current:
            for i in range(len(targets)):
                t = targets[i]
                if current == t or current.is_ancestor(t):
                    start_idx = (i + 1) % len(targets)
                    break

        for j in range(len(targets)):
            idx = (start_idx + j) % len(targets)
            target = targets[idx]
            if target.get_visible():
                target.grab_focus()
                return True

        return True
