import gi
from typing import Optional

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
from gi.repository import Gtk, GtkSource, GLib  # noqa: E402

from oatbrain.core.bus import EventBus  # noqa: E402
from oatbrain.core.events.state import StateUpdated  # noqa: E402
from oatbrain.core.ports.filestore import FileStore, VaultPath  # noqa: E402


class Editor:
    """Markdown editor wrapping GtkSourceView."""

    def __init__(self, filestore: FileStore, event_bus: EventBus) -> None:
        self._filestore = filestore
        self._current_path: Optional[VaultPath] = None

        self.buffer = GtkSource.Buffer()
        lm = GtkSource.LanguageManager.get_default()
        lang = lm.get_language("markdown")
        if lang:
            self.buffer.set_language(lang)

        self.view = GtkSource.View.new_with_buffer(self.buffer)
        self.view.set_show_line_numbers(True)
        self.view.set_monospace(True)
        self.view.set_wrap_mode(Gtk.WrapMode.WORD)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_child(self.view)
        self.scrolled.set_hexpand(True)
        self.scrolled.set_vexpand(True)

        self.widget = self.scrolled

        event_bus.subscribe(StateUpdated, self._on_state_updated)

    def _on_state_updated(self, event: StateUpdated) -> None:
        GLib.idle_add(self._update_ui, event)

    def _update_ui(self, event: StateUpdated) -> bool:
        new_path = event.state.editor.open_file
        if new_path != self._current_path:
            self._current_path = new_path
            if new_path:
                try:
                    content = self._filestore.read_text(new_path)
                    self.buffer.set_text(content)
                except Exception as e:
                    self.buffer.set_text(f"Error loading file: {e}")
            else:
                self.buffer.set_text("")
        return bool(GLib.SOURCE_REMOVE)
