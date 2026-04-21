from gi.repository import Gtk, GLib
from oatbrain.core.events.state import StateUpdated
from oatbrain.core.events.ui import (
    WordCountChanged,
    DirtyStateChanged,
    StatusMessageRequested,
)
from oatbrain.core.bus import EventBus


class StatusBar:
    """Status bar widget that reflects AppState."""

    def __init__(self, event_bus: EventBus) -> None:
        self.widget = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.widget.add_css_class("oatbrain-statusbar")
        # Margins are removed here and handled via CSS padding/margins
        # to avoid parent bleed
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
        event_bus.subscribe(WordCountChanged, self._on_word_count_changed)
        event_bus.subscribe(DirtyStateChanged, self._on_dirty_state_changed)
        event_bus.subscribe(StatusMessageRequested, self._on_status_message_requested)

    def _on_word_count_changed(self, event: WordCountChanged) -> None:
        GLib.idle_add(lambda: self._word_count_label.set_text(f"{event.count} words"))

    def _on_dirty_state_changed(self, event: DirtyStateChanged) -> None:
        GLib.idle_add(lambda: self._unsaved_dot.set_visible(event.dirty))

    def _on_status_message_requested(self, event: StatusMessageRequested) -> None:
        # For now, just show it in the path label or similar
        # Real status message support could be a separate label
        pass

    def _on_state_updated(self, event: StateUpdated) -> None:
        # Update UI on main thread
        GLib.idle_add(self._update_ui, event)

    def _update_ui(self, event: StateUpdated) -> bool:
        state = event.state
        editor = state.editor

        if editor.open_file:
            self._path_label.set_text(str(editor.open_file))
        else:
            self._path_label.set_text("No file open")
            self._unsaved_dot.set_visible(False)
            self._readonly_lock.set_visible(False)

        self._theme_label.set_text(state.theme_name)

        return False
