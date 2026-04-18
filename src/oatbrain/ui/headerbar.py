from gi.repository import Adw, Gtk, GLib, Gio
from oatbrain.core.events.state import StateUpdated
from oatbrain.core.bus import EventBus

class HeaderBar:
    """Main header bar for oatbrain."""

    def __init__(self, event_bus: EventBus) -> None:
        self.widget = Adw.HeaderBar()

        # Left: hamburger, tree toggle, new note
        self._hamburger_btn = Gtk.MenuButton(icon_name="open-menu-symbolic")
        self._hamburger_btn.set_tooltip_text("Menu")
        
        # Hamburger Menu (§8.5)
        self.menu = Gio.Menu()
        self.menu.append("Open config file", "app.open_config")
        
        # Theme section in menu
        theme_section = Gio.Menu()
        theme_section.append("Light Theme", "app.set_theme_light")
        theme_section.append("Dark Theme", "app.set_theme_dark")
        self.menu.append_section("Theme", theme_section)
        
        self._hamburger_btn.set_menu_model(self.menu)

        self.tree_toggle = Gtk.ToggleButton(icon_name="sidebar-show-symbolic")
        self.tree_toggle.set_active(True)
        self.tree_toggle.set_tooltip_text("Toggle File Tree (Ctrl+B)")

        self._new_note_btn = Gtk.Button(icon_name="document-new-symbolic")
        self._new_note_btn.set_tooltip_text("New Note (Ctrl+N)")

        left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        left_box.append(self._hamburger_btn)
        left_box.append(self.tree_toggle)
        left_box.append(self._new_note_btn)
        self.widget.pack_start(left_box)

        # Center: title/filename
        self._title_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )
        self._title_box.set_halign(Gtk.Align.CENTER)

        self._title_label = Gtk.Label(label="oatbrain")
        self._title_label.add_css_class("title")

        self._unsaved_dot = Gtk.Label(label="●")
        self._unsaved_dot.set_visible(False)
        self._unsaved_dot.set_tooltip_text("Unsaved changes")

        self._readonly_lock = Gtk.Image.new_from_icon_name(
            "changes-prevent-symbolic"
        )
        self._readonly_lock.set_visible(False)
        self._readonly_lock.set_tooltip_text("Read-only")

        self._title_box.append(self._title_label)
        self._title_box.append(self._unsaved_dot)
        self._title_box.append(self._readonly_lock)
        self.widget.set_title_widget(self._title_box)

        # Right: terminal toggle
        self.terminal_toggle = Gtk.ToggleButton(
            icon_name="utilities-terminal-symbolic"
        )
        self.terminal_toggle.set_active(True)
        self.terminal_toggle.set_tooltip_text("Toggle Terminal (Ctrl+`)")

        self.widget.pack_end(self.terminal_toggle)

        event_bus.subscribe(StateUpdated, self._on_state_updated)

    def _on_state_updated(self, event: StateUpdated) -> None:
        GLib.idle_add(self._update_ui, event)

    def _update_ui(self, event: StateUpdated) -> bool:
        state = event.state
        if state.editor.open_file:
            filename = str(state.editor.open_file.path.name)
            self._title_label.set_text(filename)
            self._unsaved_dot.set_visible(state.editor.is_dirty)
            # readonly check would go here once implemented in state
        else:
            self._title_label.set_text("oatbrain")
            self._unsaved_dot.set_visible(False)
            self._readonly_lock.set_visible(False)
        return bool(GLib.SOURCE_REMOVE)
