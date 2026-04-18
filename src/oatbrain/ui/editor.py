import gi
from typing import Optional

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GtkSource", "5")
from gi.repository import Gtk, Gdk, GtkSource, GLib  # noqa: E402

from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.events.state import StateUpdated  # noqa: E402
from oatbrain.core.ports.filestore import FileStore, VaultPath  # noqa: E402
from oatbrain.core.commands.editor import UpdateWordCount  # noqa: E402


class Editor:
    """Markdown editor wrapping GtkSourceView."""

    def __init__(
        self,
        filestore: FileStore,
        event_bus: EventBus,
        command_router: CommandRouter
    ) -> None:
        self._filestore = filestore
        self._event_bus = event_bus
        self._command_router = command_router
        self._current_path: Optional[VaultPath] = None

        self.buffer = GtkSource.Buffer()
        self._language_manager = GtkSource.LanguageManager.get_default()

        self.view = GtkSource.View.new_with_buffer(self.buffer)
        self.view.set_show_line_numbers(True)
        self.view.set_monospace(True)
        self.view.set_wrap_mode(Gtk.WrapMode.WORD)

        # Typography (§19) - Set via CSS in GTK 4
        self._setup_styling()

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_child(self.view)
        self.scrolled.set_hexpand(True)
        self.scrolled.set_vexpand(True)

        # Empty-pane placeholder (§7.4)
        self.placeholder = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12
        )
        self.placeholder.set_valign(Gtk.Align.CENTER)
        self.placeholder.set_halign(Gtk.Align.CENTER)

        hint_label = Gtk.Label()
        hint_label.set_markup(
            "<span size='large' weight='bold'>oatbrain</span>\n\n"
            "<span size='medium' color='#888'>"
            "Ctrl+P — find file\n"
            "Ctrl+N — new note"
            "</span>"
        )
        hint_label.set_justify(Gtk.Justification.CENTER)
        self.placeholder.append(hint_label)

        self.overlay = Gtk.Overlay()
        self.overlay.set_child(self.scrolled)
        self.overlay.add_overlay(self.placeholder)

        self.widget = self.overlay

        self.buffer.connect("changed", self._on_buffer_changed)

        event_bus.subscribe(StateUpdated, self._on_state_updated)

    def _on_buffer_changed(self, buffer: GtkSource.Buffer) -> None:
        """Calculate word count on change."""
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        text = buffer.get_text(start, end, True)
        words = len(text.split())
        self._command_router.dispatch(UpdateWordCount(count=words))

    def _setup_styling(self) -> None:
        """Apply typography defaults from SPEC §19."""
        fonts = "'JetBrains Mono', 'Fira Code', 'DejaVu Sans Mono', monospace"
        css = f"""
            textview {{
                font-family: {fonts};
                font-size: 13pt;
            }}
        """
        provider = Gtk.CssProvider()
        css_bytes = css.encode("utf-8")
        provider.load_from_data(css_bytes, len(css_bytes))

        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    def _on_state_updated(self, event: StateUpdated) -> None:
        GLib.idle_add(self._update_ui, event)

    def _update_language(self, path: VaultPath) -> None:
        """Detect and set language based on filename."""
        lang = self._language_manager.guess_language(str(path), None)
        self.buffer.set_language(lang)

    def _update_ui(self, event: StateUpdated) -> bool:
        new_path = event.state.editor.open_file
        self.placeholder.set_visible(new_path is None)
        self.scrolled.set_visible(new_path is not None)

        if new_path != self._current_path:
            self._current_path = new_path
            if new_path:
                try:
                    self._update_language(new_path)
                    content = self._filestore.read_text(new_path)
                    self.buffer.set_text(content)
                except Exception as e:
                    self.buffer.set_text(f"Error loading file: {e}")
            else:
                self.buffer.set_text("")
                self.buffer.set_language(None)
        return bool(GLib.SOURCE_REMOVE)
