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
        
        self._status_label = Gtk.Label(label="Ready")
        
        self._word_count_label = Gtk.Label(label="0 words")

        self.widget.append(self._path_label)
        self.widget.append(self._status_label)
        self.widget.append(self._word_count_label)

        event_bus.subscribe(StateUpdated, self._on_state_updated)

    def _on_state_updated(self, event: StateUpdated) -> None:
        # Update UI on main thread
        GLib.idle_add(self._update_ui, event)

    def _update_ui(self, event: StateUpdated) -> bool:
        state = event.state
        
        # Update Path
        if state.editor.open_file:
            path_str = str(state.editor.open_file)
            if state.editor.is_dirty:
                path_str += " ●"
            self._path_label.set_text(path_str)
        else:
            self._path_label.set_text("No file open")

        # Update Status Message
        self._status_label.set_text(state.status_message)
        
        return bool(GLib.SOURCE_REMOVE)
