import gi
from typing import Optional

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
from gi.repository import Gtk, GtkSource, GLib  # noqa: E402

from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.events.state import StateUpdated  # noqa: E402
from oatbrain.core.ports.filestore import FileStore, VaultPath  # noqa: E402
from oatbrain.core.ports.renderer import Renderer  # noqa: E402
from oatbrain.core.ports.env import Env  # noqa: E402
from oatbrain.core.wikilink.resolver import WikilinkResolver  # noqa: E402
from oatbrain.core.commands import (  # noqa: E402
    OpenFile,
)
from oatbrain.core.commands.editor import (  # noqa: E402
    UpdateWordCount,
    SetDirty,
    ToggleMode,
)


class Editor:
    """Markdown editor/preview pane with Vim mode and autosave (SPEC §10, §11)."""

    def __init__(
        self,
        filestore: FileStore,
        event_bus: EventBus,
        command_router: CommandRouter,
        env: Env,
        renderer: Optional[Renderer] = None,
        resolver: Optional[WikilinkResolver] = None,
        vim_enabled: bool = True,
    ) -> None:
        self._filestore = filestore
        self._event_bus = event_bus
        self._command_router = command_router
        self._env = env
        self._renderer = renderer
        self._resolver = resolver
        self._current_path: Optional[VaultPath] = None
        self._autosave_timer: Optional[int] = None
        self._vim_key_ctrl: Optional[Gtk.EventControllerKey] = None
        self._loading = False
        self._read_mode = False
        self._current_content: str = ""
        self._scroll_fraction: float = 0.0
        self._theme_css: str = ""
        self._theme_id: str = "solarized-light"

        # --- Source view ---
        self.buffer = GtkSource.Buffer()
        self._language_manager = GtkSource.LanguageManager.get_default()

        self.view = GtkSource.View.new_with_buffer(self.buffer)
        self.view.set_show_line_numbers(True)
        self.view.set_monospace(True)
        self.view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.view.set_left_margin(12)
        self.view.set_right_margin(12)
        self.view.set_top_margin(8)
        self.view.add_css_class("oatbrain-editor")

        if vim_enabled:
            self._vim_context: Optional[
                GtkSource.VimIMContext
            ] = GtkSource.VimIMContext.new()
            self._vim_key_ctrl = Gtk.EventControllerKey.new()
            self._vim_key_ctrl.set_im_context(self._vim_context)
            self._vim_key_ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            self.view.add_controller(self._vim_key_ctrl)
            self._vim_context.set_client_widget(self.view)
            self._vim_context.connect("write", self._on_vim_write)
            self._vim_context.connect(
                "notify::command-text", self._on_vim_label_changed
            )
            self._vim_context.connect(
                "notify::command-bar-text", self._on_vim_label_changed
            )
        else:
            self._vim_context = None
            self._vim_key_ctrl = None

        self._source_scroll = Gtk.ScrolledWindow()
        self._source_scroll.set_child(self.view)
        self._source_scroll.set_hexpand(True)
        self._source_scroll.set_vexpand(True)

        # --- Preview view ---
        if renderer is not None:
            from oatbrain.ui.preview import Preview  # local import avoids circular dep

            self._preview: Optional["Preview"] = Preview(renderer, self._env)
            self._preview.on_wikilink_clicked = self._on_wikilink_clicked
        else:
            self._preview = None

        # --- Empty-pane placeholder (§7.4) ---
        self.placeholder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
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

        # --- Content stack: placeholder / source / preview ---
        self._stack = Gtk.Stack()
        self._stack.set_hexpand(True)
        self._stack.set_vexpand(True)
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_transition_duration(120)
        self._stack.add_named(self.placeholder, "placeholder")
        self._stack.add_named(self._source_scroll, "source")
        if self._preview is not None:
            self._stack.add_named(self._preview.widget, "preview")

        # --- Mode toggle buttons (SPEC §8.1: float in pane top-right) ---
        self._btn_source = Gtk.ToggleButton()
        self._btn_source.set_icon_name("text-editor-symbolic")
        self._btn_source.set_tooltip_text("Edit (source)")
        self._btn_source.set_active(True)

        self._btn_read = Gtk.ToggleButton()
        self._btn_read.set_icon_name("accessories-dictionary-symbolic")
        self._btn_read.set_tooltip_text("Read (preview)")
        self._btn_read.set_group(self._btn_source)

        self._toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self._toggle_box.append(self._btn_source)
        self._toggle_box.append(self._btn_read)
        self._toggle_box.set_halign(Gtk.Align.END)
        self._toggle_box.set_valign(Gtk.Align.START)
        self._toggle_box.set_margin_top(8)
        self._toggle_box.set_margin_end(8)
        self._toggle_box.add_css_class("linked")
        self._toggle_box.set_visible(False)

        self.overlay = Gtk.Overlay()
        self.overlay.set_child(self._stack)
        self.overlay.add_overlay(self._toggle_box)
        self.overlay.set_clip_overlay(self._toggle_box, True)

        # --- Vim command-line bar ---
        self._cmd_bar_label = Gtk.Label(label="")
        self._cmd_bar_label.set_halign(Gtk.Align.START)
        self._cmd_bar_label.set_hexpand(True)
        self._cmd_bar_label.add_css_class("monospace")
        self._cmd_bar_label.set_margin_start(6)
        self._cmd_bar_label.set_margin_end(6)
        self._cmd_bar_label.set_margin_top(2)
        self._cmd_bar_label.set_margin_bottom(2)
        self._cmd_bar_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._cmd_bar_row.append(self._cmd_bar_label)
        self._cmd_bar_row.set_visible(False)

        self._main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._main_box.append(self.overlay)
        self._main_box.append(self._cmd_bar_row)

        self.widget = self._main_box

        # --- Signals ---
        self.buffer.connect("changed", self._on_buffer_changed)

        focus_ctrl = Gtk.EventControllerFocus.new()
        focus_ctrl.connect("leave", self._on_focus_leave)
        self.view.add_controller(focus_ctrl)

        self._btn_source.connect("toggled", self._on_source_toggled)
        self._btn_read.connect("toggled", self._on_read_toggled)

        event_bus.subscribe(StateUpdated, self._on_state_updated)

    def _on_wikilink_clicked(self, target_full: str) -> None:
        if self._resolver is None or self._current_path is None:
            return

        target = target_full.split("#")[0] if "#" in target_full else target_full
        resolved = self._resolver.resolve(target, self._current_path)

        if resolved:
            self._command_router.dispatch(OpenFile(resolved))
        else:
            # Simple rule: create next to current note
            new_filename = target if target.endswith(".md") else f"{target}.md"

            # If target has folders, it might be path-bearing
            if "/" in new_filename:
                # Vault-relative creation
                new_path = VaultPath.from_str(new_filename)
            else:
                # File-relative creation
                parent = self._current_path.parent
                if str(parent):
                    new_path = VaultPath.from_str(f"{parent}/{new_filename}")
                else:
                    new_path = VaultPath.from_str(new_filename)

            # Create the file
            try:
                self._filestore.write_text(new_path, f"# {target}\n")
                self._command_router.dispatch(OpenFile(new_path))
            except Exception as e:
                print(f"Error creating file for wikilink: {e}")

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def apply_source_scheme(self, scheme_id: str) -> None:
        """Apply a GtkSourceView style scheme by ID (SPEC §20.9)."""
        sm = GtkSource.StyleSchemeManager.get_default()
        scheme = sm.get_scheme(scheme_id)
        if scheme is not None:
            self.buffer.set_style_scheme(scheme)

    def set_theme_css(self, css: str, theme_id: str = "solarized-light") -> None:
        """Update the CSS injected into the WebKit preview (§11.3)."""
        self._theme_css = css
        self._theme_id = theme_id
        if (
            self._read_mode
            and self._preview is not None
            and self._current_path is not None
        ):
            self._preview.render(
                self._current_content,
                self._current_path,
                scroll_to=self._scroll_fraction,
                theme_css=css,
                theme_id=theme_id,
            )

    def set_zen_mode(self, enabled: bool) -> None:
        """Adjust editor margins and line numbers for Zen mode (SPEC §7.5)."""
        if enabled:
            self.view.set_left_margin(80)
            self.view.set_right_margin(80)
            self.view.set_show_line_numbers(False)
        else:
            self.view.set_left_margin(12)
            self.view.set_right_margin(12)
            self.view.set_show_line_numbers(True)

    # ------------------------------------------------------------------
    # Mode toggle
    # ------------------------------------------------------------------

    def toggle_mode(self) -> None:
        """Flip between source and read mode (Ctrl+E / SPEC §10.2)."""
        self._command_router.dispatch(ToggleMode())

    def _apply_fraction_to_source(self, fraction: float) -> None:
        """Apply scroll fraction to the source view (called async from preview)."""
        self._scroll_fraction = fraction
        adj = self._source_scroll.get_vadjustment()
        upper = adj.get_upper() - adj.get_page_size()
        if upper > 0:
            adj.set_value(fraction * upper)

    def _set_read_mode(self, read: bool) -> None:
        self._read_mode = read
        if self._current_path is None:
            return
        if read:
            if self._preview is not None:
                self._preview.render(
                    self._current_content, self._current_path, theme_css=self._theme_css
                )
                self._stack.set_visible_child_name("preview")
        else:
            self._stack.set_visible_child_name("source")

    def _on_source_toggled(self, btn: Gtk.ToggleButton) -> None:
        if btn.get_active():
            self._command_router.dispatch(ToggleMode())

    def _on_read_toggled(self, btn: Gtk.ToggleButton) -> None:
        if btn.get_active():
            self._command_router.dispatch(ToggleMode())

    # ------------------------------------------------------------------
    # Vim IM context callbacks
    # ------------------------------------------------------------------

    def _on_vim_write(
        self, _ctx: GtkSource.VimIMContext, _view: GtkSource.View, _path: str
    ) -> None:
        self._save()

    def _on_vim_label_changed(self, *_: object) -> None:
        if self._vim_context is None:
            return
        bar = self._vim_context.get_property("command-bar-text") or ""
        cmd = self._vim_context.get_property("command-text") or ""
        display = bar if bar else cmd
        GLib.idle_add(self._apply_cmd_bar_label, display)

    def _apply_cmd_bar_label(self, text: str) -> bool:
        self._cmd_bar_label.set_text(text)
        self._cmd_bar_row.set_visible(bool(text))
        return bool(GLib.SOURCE_REMOVE)

    # ------------------------------------------------------------------
    # Buffer & focus callbacks
    # ------------------------------------------------------------------

    def _count_words(self) -> int:
        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()
        text = self.buffer.get_text(start, end, True)
        return len(text.split()) if text.strip() else 0

    def _on_buffer_changed(self, _buffer: GtkSource.Buffer) -> None:
        if self._loading:
            return
        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()
        self._current_content = self.buffer.get_text(start, end, True)
        self._command_router.dispatch(UpdateWordCount(count=self._count_words()))
        self._command_router.dispatch(SetDirty(dirty=True))

    def _on_focus_leave(self, _ctrl: Gtk.EventControllerFocus) -> None:
        self._save()

    # ------------------------------------------------------------------
    # Save logic
    # ------------------------------------------------------------------

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
        new_read_mode = event.state.editor.read_mode

        self.placeholder.set_visible(new_path is None)
        is_markdown = new_path is not None and str(new_path).endswith(
            (".md", ".markdown")
        )
        self._toggle_box.set_visible(is_markdown and self._preview is not None)

        if new_path != self._current_path:
            self._cancel_autosave()
            self._current_path = new_path
            if new_path:
                try:
                    self._update_language(new_path)
                    self._loading = True
                    content = self._filestore.read_text(new_path)
                    self._current_content = content
                    self.buffer.set_text(content)
                    self._loading = False
                    self._command_router.dispatch(
                        UpdateWordCount(count=self._count_words())
                    )
                    self._command_router.dispatch(SetDirty(dirty=False))
                except Exception as e:
                    self._loading = False
                    self._current_content = ""
                    self.buffer.set_text(f"Error loading file: {e}")
            else:
                self._current_content = ""
                self.buffer.set_text("")
                self.buffer.set_language(None)
                self._command_router.dispatch(UpdateWordCount(count=0))

        # If the new file isn't Markdown, drop out of read mode
        if not is_markdown and self._read_mode:
            self._read_mode = False
            new_read_mode = False
            self._command_router.dispatch(ToggleMode())

        # Sync mode (may change independently of file)
        mode_changed = new_read_mode != self._read_mode
        if mode_changed:
            if self._read_mode:
                # Leaving preview → capture scroll fraction asynchronously;
                # apply it to the source view once the value arrives.
                if self._preview is not None:
                    self._preview.get_scroll_fraction(self._apply_fraction_to_source)
            else:
                # Leaving source → capture fraction synchronously from vadjustment.
                adj = self._source_scroll.get_vadjustment()
                upper = adj.get_upper() - adj.get_page_size()
                self._scroll_fraction = adj.get_value() / upper if upper > 0 else 0.0

            self._read_mode = new_read_mode
            self._btn_read.handler_block_by_func(self._on_read_toggled)
            self._btn_source.handler_block_by_func(self._on_source_toggled)
            self._btn_read.set_active(new_read_mode)
            self._btn_source.set_active(not new_read_mode)
            self._btn_read.handler_unblock_by_func(self._on_read_toggled)
            self._btn_source.handler_unblock_by_func(self._on_source_toggled)

        # Switch view
        self._stack.set_visible_child_name("preview" if new_read_mode else "source")
        if new_path is None:
            self._stack.set_visible_child_name("placeholder")
        elif new_read_mode:
            if self._preview is not None and new_path is not None:
                self._preview.render(
                    self._current_content,
                    new_path,
                    scroll_to=self._scroll_fraction,
                    theme_css=self._theme_css,
                    theme_id=event.state.theme_id,
                )

                self._stack.set_visible_child_name("preview")
            else:
                self._stack.set_visible_child_name("source")
        else:
            self._stack.set_visible_child_name("source")

        return bool(GLib.SOURCE_REMOVE)
