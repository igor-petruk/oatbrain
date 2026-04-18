import gi
from typing import Optional

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
from gi.repository import Gtk, GtkSource, GLib  # noqa: E402

from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.events.state import StateUpdated  # noqa: E402
from oatbrain.core.ports.filestore import FileStore, VaultPath  # noqa: E402
from oatbrain.core.commands.editor import (  # noqa: E402
    UpdateWordCount,
    SetDirty,
    UpdateVimMode,
)

_AUTOSAVE_DELAY_MS = 5000


class Editor:
    """Markdown editor wrapping GtkSourceView with Vim mode and autosave."""

    def __init__(
        self,
        filestore: FileStore,
        event_bus: EventBus,
        command_router: CommandRouter,
        vim_enabled: bool = True,
    ) -> None:
        self._filestore = filestore
        self._event_bus = event_bus
        self._command_router = command_router
        self._current_path: Optional[VaultPath] = None
        self._autosave_timer: Optional[int] = None
        self._loading = False

        self.buffer = GtkSource.Buffer()
        self._language_manager = GtkSource.LanguageManager.get_default()

        self.view = GtkSource.View.new_with_buffer(self.buffer)
        self.view.set_show_line_numbers(True)
        self.view.set_monospace(True)
        self.view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.view.add_css_class("oatbrain-editor")

        if vim_enabled:
            self._vim_context: Optional[GtkSource.VimIMContext] = (
                GtkSource.VimIMContext.new()
            )
            self._vim_context.set_client_widget(self.view)
            self._vim_context.connect("write", self._on_vim_write)
            self._vim_context.connect(
                "notify::command-text", self._on_vim_command_text
            )
        else:
            self._vim_context = None

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

        # Focus-out triggers autosave (§10.3)
        focus_ctrl = Gtk.EventControllerFocus.new()
        focus_ctrl.connect("leave", self._on_focus_leave)
        self.view.add_controller(focus_ctrl)

        event_bus.subscribe(StateUpdated, self._on_state_updated)

    # ------------------------------------------------------------------
    # Vim IM context callbacks
    # ------------------------------------------------------------------

    def _on_vim_write(
        self, _ctx: GtkSource.VimIMContext, _view: GtkSource.View, _path: str
    ) -> None:
        self._save()

    def _on_vim_command_text(self, ctx: GtkSource.VimIMContext, _pspec: object) -> None:
        raw = ctx.get_property("command-text") or ""
        if "INSERT" in raw:
            mode = "INSERT"
        elif "VISUAL" in raw:
            mode = "VISUAL"
        elif "REPLACE" in raw:
            mode = "REPLACE"
        elif "COMMAND" in raw or raw.startswith(":"):
            mode = "COMMAND"
        else:
            mode = "NORMAL"
        self._command_router.dispatch(UpdateVimMode(mode=mode))

    # ------------------------------------------------------------------
    # Buffer & focus callbacks
    # ------------------------------------------------------------------

    def _on_buffer_changed(self, _buffer: GtkSource.Buffer) -> None:
        if self._loading:
            return
        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()
        text = self.buffer.get_text(start, end, True)
        words = len(text.split()) if text.strip() else 0
        self._command_router.dispatch(UpdateWordCount(count=words))
        self._command_router.dispatch(SetDirty(dirty=True))
        self._schedule_autosave()

    def _on_focus_leave(self, _ctrl: Gtk.EventControllerFocus) -> None:
        self._save()

    # ------------------------------------------------------------------
    # Save logic
    # ------------------------------------------------------------------

    def _schedule_autosave(self) -> None:
        if self._autosave_timer is not None:
            GLib.source_remove(self._autosave_timer)
        self._autosave_timer = GLib.timeout_add(
            _AUTOSAVE_DELAY_MS, self._autosave_fire
        )

    def _autosave_fire(self) -> bool:
        self._autosave_timer = None
        self._save()
        return bool(GLib.SOURCE_REMOVE)

    def _cancel_autosave(self) -> None:
        if self._autosave_timer is not None:
            GLib.source_remove(self._autosave_timer)
            self._autosave_timer = None

    def _save(self) -> None:
        if self._current_path is None:
            return
        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()
        content = self.buffer.get_text(start, end, True)
        try:
            self._filestore.write_text(self._current_path, content)
            self._command_router.dispatch(SetDirty(dirty=False))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # State update
    # ------------------------------------------------------------------

    def _on_state_updated(self, event: StateUpdated) -> None:
        GLib.idle_add(self._update_ui, event)

    def _update_language(self, path: VaultPath) -> None:
        lang = self._language_manager.guess_language(str(path), None)
        self.buffer.set_language(lang)

    def _update_ui(self, event: StateUpdated) -> bool:
        new_path = event.state.editor.open_file
        self.placeholder.set_visible(new_path is None)
        self.scrolled.set_visible(new_path is not None)

        if new_path != self._current_path:
            self._cancel_autosave()
            self._current_path = new_path
            if new_path:
                try:
                    self._update_language(new_path)
                    self._loading = True
                    content = self._filestore.read_text(new_path)
                    self.buffer.set_text(content)
                    self._loading = False
                    self._command_router.dispatch(SetDirty(dirty=False))
                except Exception as e:
                    self._loading = False
                    self.buffer.set_text(f"Error loading file: {e}")
            else:
                self.buffer.set_text("")
                self.buffer.set_language(None)
        return bool(GLib.SOURCE_REMOVE)
