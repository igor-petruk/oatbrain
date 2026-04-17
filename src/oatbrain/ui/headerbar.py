from gi.repository import Adw, Gtk, GLib
from oatbrain.core.events.state import StateUpdated
from oatbrain.core.bus import EventBus

class HeaderBar:
    """Main header bar for oatbrain."""

    def __init__(self, event_bus: EventBus) -> None:
        self.widget = Adw.HeaderBar()
        
        # Left: hamburger, tree toggle, new note
        self._tree_toggle = Gtk.ToggleButton(icon_name="sidebar-show-symbolic")
        self._tree_toggle.set_active(True)
        self._tree_toggle.set_tooltip_text("Toggle File Tree")
        
        self._new_note_btn = Gtk.Button(icon_name="document-new-symbolic")
        self._new_note_btn.set_tooltip_text("New Note")

        left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        left_box.append(self._tree_toggle)
        left_box.append(self._new_note_btn)
        self.widget.pack_start(left_box)

        # Center: title/filename
        self._title_label = Gtk.Label(label="oatbrain")
        self._title_label.add_css_class("title")
        self.widget.set_title_widget(self._title_label)

        # Right: terminal toggle, theme switcher
        self._terminal_toggle = Gtk.ToggleButton(
            icon_name="utilities-terminal-symbolic"
        )
        self._terminal_toggle.set_active(True)
        self._terminal_toggle.set_tooltip_text("Toggle Terminal")

        self._theme_btn = Gtk.Button(icon_name="display-brightness-symbolic")
        self._theme_btn.set_tooltip_text("Switch Theme")
        
        right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        right_box.append(self._terminal_toggle)
        right_box.append(self._theme_btn)
        self.widget.pack_end(right_box)

        event_bus.subscribe(StateUpdated, self._on_state_updated)

    def _on_state_updated(self, event: StateUpdated) -> None:
        GLib.idle_add(self._update_ui, event)

    def _update_ui(self, event: StateUpdated) -> bool:
        state = event.state
        if state.editor.open_file:
            filename = str(state.editor.open_file.path.name)
            self._title_label.set_text(f"oatbrain — {filename}")
        else:
            self._title_label.set_text("oatbrain")
        return bool(GLib.SOURCE_REMOVE)
