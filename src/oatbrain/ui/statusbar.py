from gi.repository import Gtk, GLib
from oatbrain.core.events.state import StateUpdated
from oatbrain.core.events.ui import (
    FocusedTabStats,
    StatusMessageRequested,
)
from oatbrain.core.bus import EventBus


class StatusBar:
    """Status bar widget that reflects AppState and focused tab stats."""

    def __init__(self, event_bus: EventBus) -> None:
        self.widget = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.widget.add_css_class("oatbrain-statusbar")
        self.widget.set_spacing(12)

        self._path_label = Gtk.Label(label="No file open")
        self._path_label.set_hexpand(True)
        self._path_label.set_halign(Gtk.Align.START)

        self._unsaved_dot = Gtk.Label(label="●")
        self._unsaved_dot.set_visible(False)
        # Style the dot to be orange/warning color
        self._unsaved_dot.add_css_class("dirty-dot")

        self._word_count_label = Gtk.Label(label="0 words")

        self._theme_label = Gtk.Label(label="")
        self._theme_label.add_css_class("dim-label")

        self.widget.append(self._path_label)
        self.widget.append(self._unsaved_dot)
        self.widget.append(self._word_count_label)
        self.widget.append(self._theme_label)

        event_bus.subscribe(StateUpdated, self._on_state_updated)
        event_bus.subscribe(FocusedTabStats, self._on_focused_stats_changed)
        event_bus.subscribe(StatusMessageRequested, self._on_status_message_requested)

    def _on_focused_stats_changed(self, event: FocusedTabStats) -> None:
        GLib.idle_add(lambda: self._update_stats_ui(event))

    def _update_stats_ui(self, event: FocusedTabStats) -> None:
        if event.path:
            self._path_label.set_text(str(event.path))
            self._word_count_label.set_text(f"{event.word_count} words")
            self._unsaved_dot.set_visible(event.is_dirty)
            self._word_count_label.set_visible(True)
        else:
            self._path_label.set_text("No file open")
            self._word_count_label.set_visible(False)
            self._unsaved_dot.set_visible(False)

    def _on_status_message_requested(self, event: StatusMessageRequested) -> None:
        # Temporary status message in the path label?
        # For now, let's just ignore or use a toast
        pass

    def _on_state_updated(self, event: StateUpdated) -> None:
        GLib.idle_add(self._update_state_ui, event)

    def _update_state_ui(self, event: StateUpdated) -> bool:
        state = event.state
        self._theme_label.set_text(state.theme_name)
        return False
