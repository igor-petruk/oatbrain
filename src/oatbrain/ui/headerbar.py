from gi.repository import Adw, Gtk, GLib, Gio
from oatbrain.core.events.state import StateUpdated
from oatbrain.core.events.ui import DirtyStateChanged
from oatbrain.core.commands.editor import RefreshFile
from oatbrain.core.bus import EventBus, CommandRouter


class HeaderBar:
    """A single header bar for the application."""

    def __init__(self, event_bus: EventBus, command_router: CommandRouter) -> None:
        self._command_router = command_router
        self.widget = Adw.HeaderBar()
        self.widget.add_css_class("oatbrain-headerbar")

        # --- Left (Start) ---
        self._hamburger_btn = Gtk.MenuButton(icon_name="open-menu-symbolic")
        self._hamburger_btn.set_tooltip_text("Menu")

        self.menu = Gio.Menu()
        self.menu.append("Open config file", "app.open_config")
        theme_section = Gio.Menu()
        theme_section.append("Light Theme", "app.set_theme_light")
        theme_section.append("Dark Theme", "app.set_theme_dark")
        theme_section.append("High Contrast Dark", "app.set_theme_high_contrast")
        self.menu.append_section("Theme", theme_section)
        self._hamburger_btn.set_menu_model(self.menu)

        self.tree_toggle = Gtk.ToggleButton(icon_name="sidebar-show-symbolic")
        self.tree_toggle.set_active(True)
        self.tree_toggle.set_tooltip_text("Toggle File Tree")

        self._new_note_btn = Gtk.Button(icon_name="document-new-symbolic")
        self._new_note_btn.set_tooltip_text("New Note (Ctrl+N)")

        self._refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        self._refresh_btn.set_tooltip_text("Refresh File (F5)")
        self._refresh_btn.connect("clicked", self._on_refresh_clicked)

        left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        left_box.append(self._hamburger_btn)
        left_box.append(self.tree_toggle)
        left_box.append(self._new_note_btn)
        left_box.append(self._refresh_btn)
        self.widget.pack_start(left_box)

        # --- Title ---
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title_box.set_halign(Gtk.Align.CENTER)

        self._title_label = Gtk.Label(label="oatbrain")
        self._title_label.add_css_class("title")

        self._unsaved_dot = Gtk.Label(label="●")
        self._unsaved_dot.set_visible(False)
        self._unsaved_dot.set_tooltip_text("Unsaved changes")

        self._readonly_lock = Gtk.Image.new_from_icon_name("changes-prevent-symbolic")
        self._readonly_lock.set_visible(False)
        self._readonly_lock.set_tooltip_text("Read-only")

        title_box.append(self._title_label)
        title_box.append(self._unsaved_dot)
        title_box.append(self._readonly_lock)
        self.widget.set_title_widget(title_box)

        # --- Right (End) ---
        # Terminal group
        self.terminal_toggle = Gtk.ToggleButton(icon_name="utilities-terminal-symbolic")
        self.terminal_toggle.set_active(True)
        self.terminal_toggle.set_tooltip_text("Toggle Terminal (Ctrl+`)")

        self.terminal_restart = Gtk.Button(icon_name="view-refresh-symbolic")
        self.terminal_restart.set_tooltip_text("Restart Terminal")

        terminal_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        terminal_box.add_css_class("linked")
        terminal_box.append(self.terminal_toggle)
        terminal_box.append(self.terminal_restart)
        self.widget.pack_end(terminal_box)

        # Zen mode toggle
        self.zen_toggle = Gtk.ToggleButton(icon_name="view-fullscreen-symbolic")
        self.zen_toggle.set_active(False)
        self.zen_toggle.set_tooltip_text("Zen Mode (Ctrl+Shift+Z)")
        self.widget.pack_end(self.zen_toggle)

        event_bus.subscribe(StateUpdated, self._on_state_updated)
        event_bus.subscribe(DirtyStateChanged, self._on_dirty_state_changed)

    def _on_dirty_state_changed(self, event: DirtyStateChanged) -> None:
        GLib.idle_add(lambda: self._unsaved_dot.set_visible(event.dirty))

    def _on_refresh_clicked(self, _btn: Gtk.Button) -> None:
        self._command_router.dispatch(RefreshFile())

    def _on_state_updated(self, event: StateUpdated) -> None:
        GLib.idle_add(self._update_ui, event)

    def _update_ui(self, event: StateUpdated) -> bool:
        state = event.state
        vault_path = str(state.vault_root)
        self._title_label.set_text(f"oatbrain — {vault_path}")
        return False
