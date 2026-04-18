from gi.repository import Gtk, GLib
from oatbrain.core.events.state import StateUpdated
from oatbrain.core.bus import EventBus


class StatusBar:
    """Status bar widget that reflects AppState."""

    def __init__(self, event_bus: EventBus) -> None:
        self.widget = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.widget.set_margin_start(12)
        self.widget.set_margin_end(12)
        self.widget.set_margin_top(6)
        self.widget.set_margin_bottom(6)
        self.widget.set_spacing(12)

        self._path_label = Gtk.Label(label="No file open")
        self._path_label.set_hexpand(True)
        self._path_label.set_halign(Gtk.Align.START)

        self._unsaved_dot = Gtk.Label(label="●")
        self._unsaved_dot.set_visible(False)

        self._readonly_lock = Gtk.Image.new_from_icon_name("changes-prevent-symbolic")
        self._readonly_lock.set_visible(False)

        self._word_count_label = Gtk.Label(label="0 words")

        self._theme_label = Gtk.Label(label="Solarized Light")
        self._theme_label.add_css_class("dim-label")

        self.widget.append(self._path_label)
        self.widget.append(self._unsaved_dot)
        self.widget.append(self._readonly_lock)
        self.widget.append(self._word_count_label)
        self.widget.append(self._theme_label)

        event_bus.subscribe(StateUpdated, self._on_state_updated)

    def _on_state_updated(self, event: StateUpdated) -> None:
        # Update UI on main thread
        GLib.idle_add(self._update_ui, event)

    def _update_ui(self, event: StateUpdated) -> bool:
        state = event.state

        if state.editor.open_file:
            self._path_label.set_text(str(state.editor.open_file))
            self._unsaved_dot.set_visible(state.editor.is_dirty)
        else:
            self._path_label.set_text("No file open")
            self._unsaved_dot.set_visible(False)
            self._readonly_lock.set_visible(False)

        self._word_count_label.set_text(f"{state.editor.word_count} words")

        return bool(GLib.SOURCE_REMOVE)
