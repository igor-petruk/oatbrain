import gi
import logging
from typing import Optional, Callable
from pathlib import Path

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GtkSource", "5")
from gi.repository import Gtk, Gdk, GtkSource, GLib  # noqa: E402

from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.events.ui import (  # noqa: E402
    WordCountChanged,
    DirtyStateChanged,
    FileChangedOnDisk,
)
from oatbrain.core.ports.filestore import FileStore, VaultPath  # noqa: E402
from oatbrain.core.ports.renderer import Renderer  # noqa: E402
from oatbrain.core.ports.watcher import FileWatcher, Unsubscribe  # noqa: E402
from oatbrain.core.ports.env import Env  # noqa: E402
from oatbrain.core.wikilink import WikilinkResolver  # noqa: E402
from oatbrain.core.state import AppState, TabState  # noqa: E402
from oatbrain.core.commands import OpenFile, Zoom  # noqa: E402
from oatbrain.core.commands.editor import ToggleMode  # noqa: E402
from oatbrain.ui.preview import Preview  # noqa: E402


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}


class Editor:
    """Markdown editor/preview pane with Vim mode (SPEC §10, §11)."""

    def __init__(
        self,
        filestore: FileStore,
        event_bus: EventBus,
        command_router: CommandRouter,
        env: Env,
        vault_root: Optional[Path] = None,
        renderer: Optional[Renderer] = None,
        resolver: Optional[WikilinkResolver] = None,
        vim_enabled: bool = True,
        watcher: Optional[FileWatcher] = None,
        tab_id: str = "",
    ) -> None:
        self._filestore = filestore
        self._event_bus = event_bus
        self._command_router = command_router
        self._env = env
        self._vault_root = vault_root
        self._renderer = renderer
        self._resolver = resolver
        self._watcher = watcher
        self._file_unsubscribe: Optional[Unsubscribe] = None
        self._current_path: Optional[VaultPath] = None
        self._vim_key_ctrl: Optional[Gtk.EventControllerKey] = None
        self._logger = logging.getLogger("oatbrain.editor")
        self.tab_id = tab_id
        self._loading = False
        self._read_mode = False
        self._current_content: str = ""
        self._scroll_fraction: float = 0.0
        self._theme_css: str = ""
        self._theme_id: str = "solarized-light"
        self._stats_timeout_id: Optional[int] = None
        self._scrolling_locked = False
        self._is_dirty = False
        self._word_count = 0

        # Callbacks
        self.on_focused: Optional[Callable[["Editor"], None]] = None
        self.on_path_changed: Optional[Callable[[VaultPath], None]] = None

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

        # Zoom provider for Source view (§19)
        self._zoom_provider = Gtk.CssProvider()
        self.view.get_style_context().add_provider(
            self._zoom_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Ctrl+MouseScroll zooming (§19)
        scroll_ctrl = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL
        )
        scroll_ctrl.connect("scroll", self._on_scroll)
        self.view.add_controller(scroll_ctrl)

        focus_ctrl = Gtk.EventControllerFocus.new()
        focus_ctrl.connect("enter", lambda *_: self._on_focus_entered())
        self.view.add_controller(focus_ctrl)

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
            self._preview.on_scroll = self._apply_fraction_to_source
            self._preview.on_zoom = lambda delta: self._command_router.dispatch(
                Zoom("preview", delta)
            )

            # Focus tracking for preview
            preview_focus_ctrl = Gtk.EventControllerFocus.new()
            preview_focus_ctrl.connect("enter", lambda *_: self._on_focus_entered())
            self._preview.widget.add_controller(preview_focus_ctrl)
        else:
            self._preview = None

        # Containers for easy reparenting
        self._source_container = Gtk.Box()
        self._source_container.append(self._source_scroll)

        self._preview_container = Gtk.Box()
        if self._preview:
            self._preview_container.append(self._preview.widget)

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
        self._stack.add_named(self._source_container, "source")
        if self._preview is not None:
            self._stack.add_named(self._preview_container, "preview")

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

        self._btn_source.connect("toggled", self._on_source_toggled)
        self._btn_read.connect("toggled", self._on_read_toggled)

        # Synchronized scrolling
        self._source_scroll.get_vadjustment().connect(
            "value-changed", self._on_source_scrolled
        )

    def _on_source_scrolled(self, adj: Gtk.Adjustment) -> None:
        if self._scrolling_locked:
            return
        if self._read_mode:
            upper = adj.get_upper() - adj.get_page_size()
            if upper > 0:
                fraction = adj.get_value() / upper
                self._scroll_fraction = fraction
                if self._preview:
                    self._preview._apply_scroll(self._preview._wv, fraction)

    def _on_scroll(self, ctrl: Gtk.EventControllerScroll, dx: float, dy: float) -> bool:
        """Handle Ctrl+MouseScroll to zoom editor (§19)."""
        event = ctrl.get_current_event()
        if not event:
            return False
        modifiers = event.get_modifier_state()
        if modifiers & Gdk.ModifierType.CONTROL_MASK:
            # dy is positive for scroll down, negative for scroll up
            delta = -0.1 if dy > 0 else 0.1
            self._command_router.dispatch(Zoom("editor", delta))
            return True
        return False

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
        self._command_router.dispatch(ToggleMode(tab_id=self.tab_id))

    def _apply_fraction_to_source(self, fraction: float) -> None:
        """Apply scroll fraction to the source view (called async from preview)."""
        self._scroll_fraction = fraction
        self._scrolling_locked = True
        adj = self._source_scroll.get_vadjustment()
        upper = adj.get_upper() - adj.get_page_size()
        if upper > 0:
            adj.set_value(fraction * upper)
        self._scrolling_locked = False

    def _on_source_toggled(self, btn: Gtk.ToggleButton) -> None:
        if btn.get_active():
            if self._read_mode:
                self._command_router.dispatch(ToggleMode(tab_id=self.tab_id))

    def _on_read_toggled(self, btn: Gtk.ToggleButton) -> None:
        if btn.get_active():
            if not self._read_mode:
                self._command_router.dispatch(ToggleMode(tab_id=self.tab_id))

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
        return False

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

        if not self._is_dirty:
            self._is_dirty = True
            self._event_bus.publish(DirtyStateChanged(dirty=True, sender_id=id(self)))

        if self._stats_timeout_id:
            GLib.source_remove(self._stats_timeout_id)
        self._stats_timeout_id = GLib.timeout_add(500, self._update_stats)

    def _update_stats(self) -> bool:
        self._stats_timeout_id = None
        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()
        current_text = self.buffer.get_text(start, end, True)
        self._word_count = len(current_text.split()) if current_text.strip() else 0
        self._event_bus.publish(
            WordCountChanged(count=self._word_count, sender_id=id(self))
        )
        return False

    def _do_render(self) -> bool:
        if self._preview and self._current_path:
            self._preview.render(
                self._current_content,
                self._current_path,
                scroll_to=self._scroll_fraction,
                theme_css=self._theme_css,
                theme_id=self._theme_id,
            )
        return False

    def _on_focus_entered(self) -> None:
        if self.on_focused:
            self.on_focused(self)

    # ------------------------------------------------------------------
    # Save logic
    # ------------------------------------------------------------------

    def _save(self) -> None:
        if self._current_path is None:
            return
        # Never save binary files as text (§10)
        is_image = any(
            str(self._current_path).lower().endswith(ext) for ext in IMAGE_EXTS
        )
        if is_image:
            return

        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()
        content = self.buffer.get_text(start, end, True)
        try:
            self._filestore.write_text(self._current_path, content)
            self._current_content = content
            self._is_dirty = False
            self._event_bus.publish(DirtyStateChanged(dirty=False, sender_id=id(self)))
            if self._read_mode:
                self._do_render()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # State update
    # ------------------------------------------------------------------

    def destroy(self) -> None:
        if self._file_unsubscribe:
            self._file_unsubscribe()
            self._file_unsubscribe = None

    def _on_file_watched_event(
        self, action: str, path: Path, new_path: Optional[Path]
    ) -> None:
        if action == "MODIFIED":
            GLib.idle_add(self._reload_if_clean, str(path))
        elif action == "RENAMED" and new_path:
            # Determine which file is "ours" by resolving the current open
            # path to absolute.
            open_abs: Optional[Path] = None
            if self._current_path and self._vault_root:
                try:
                    open_abs = (self._vault_root / str(self._current_path)).resolve()
                except Exception:
                    pass

            try:
                dest_rel = (
                    new_path.relative_to(self._vault_root) if self._vault_root else None
                )
            except ValueError:
                dest_rel = None

            src_is_open = open_abs is not None and path.resolve() == open_abs
            dst_is_open = (
                open_abs is not None
                and dest_rel is not None
                and new_path.resolve() == open_abs
            )

            if src_is_open and dest_rel is not None:
                # Case 1: our file was renamed/moved — update the tracked path.
                if self.on_path_changed:
                    GLib.idle_add(self.on_path_changed, dest_rel)
            elif dst_is_open:
                # Case 2: something else was renamed *onto* our file — the content
                # at our path has silently changed, so reload.
                self._logger.debug("moved onto open file → reload  %s", new_path)
                GLib.idle_add(self._reload_if_clean, str(new_path))
        elif action == "DELETED":

            def handle_delete() -> None:
                if not self._is_dirty:
                    # In multi-tab, EditorArea handles closing the tab.
                    # We just inform being empty if needed?
                    # For now, we clear the path.
                    self._current_path = None
                    self._stack.set_visible_child_name("placeholder")
                else:
                    from oatbrain.core.events.ui import StatusMessageRequested

                    self._event_bus.publish(
                        StatusMessageRequested(
                            "File deleted externally. "
                            "Buffer is dirty, save to recreate.",
                            5000,
                        )
                    )

            GLib.idle_add(handle_delete)

    def refresh(self) -> None:
        """Manually reload current file from disk."""
        self._logger.debug("refresh  %s", self._current_path)
        if self._current_path is None:
            return
        try:
            content = self._filestore.read_text(self._current_path)
            self._logger.debug("refresh: read %d chars from disk", len(content))
            self._loading = True
            self.buffer.set_text(content)
            self._current_content = content
            self._loading = False
            self._is_dirty = False
            self._word_count = self._count_words()
            self._event_bus.publish(
                WordCountChanged(count=self._word_count, sender_id=id(self))
            )
            self._event_bus.publish(DirtyStateChanged(dirty=False, sender_id=id(self)))
            if self._read_mode:
                self._do_render()
        except Exception as e:
            self._logger.error("refresh error  %s", e)

    def _reload_if_clean(self, abs_path: str) -> bool:
        self._logger.debug("checking reload  %s", abs_path)
        if self._current_path is None or self._vault_root is None:
            self._logger.debug("reload skipped: no open file")
            return False

        target_abs = str(self._vault_root / str(self._current_path))
        self._logger.debug("reload target=%s  event=%s", target_abs, abs_path)
        if abs_path != target_abs:
            return False
        if self._loading:
            self._logger.debug("reload skipped: currently loading")
            return False
        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()
        current_text = self.buffer.get_text(start, end, True)
        try:
            content = self._filestore.read_text(self._current_path)
        except Exception as e:
            self._logger.error("disk read error: %s", e)
            return False
        if content == current_text:
            self._logger.debug("reload skipped: content unchanged")
            return False

        # Only reload if the buffer is clean (matches what was last saved).
        if current_text != self._current_content:
            self._logger.debug("reload skipped: unsaved edits — notifying")
            self._event_bus.publish(FileChangedOnDisk(abs_path))
            return False

        self._logger.info("reloading clean buffer from disk")
        self._loading = True
        self.buffer.set_text(content)
        self._current_content = content
        self._loading = False
        self._word_count = self._count_words()
        self._event_bus.publish(
            WordCountChanged(count=self._word_count, sender_id=id(self))
        )
        if self._read_mode:
            self._do_render()
        return False

    def update_from_state(self, tab_state: TabState, app_state: AppState) -> None:
        """Update UI from specific tab state and global app state."""
        self._update_ui_impl(tab_state, app_state)

    def _update_language(self, path: VaultPath) -> None:
        lang = self._language_manager.guess_language(str(path), None)
        self.buffer.set_language(lang)

    def _update_ui_impl(self, tab_state: TabState, app_state: AppState) -> None:
        new_path = tab_state.open_file

        # Apply zoom (§19)
        base_size = 13.0
        new_size = base_size * tab_state.zoom
        css = f".oatbrain-editor {{ font-size: {new_size:.1f}pt; }}"
        self._zoom_provider.load_from_string(css)

        if self._preview:
            self._preview.set_zoom(tab_state.preview_zoom)

        self.placeholder.set_visible(new_path is None)
        is_markdown = new_path is not None and str(new_path).endswith(
            (".md", ".markdown")
        )
        is_image = new_path is not None and any(
            str(new_path).lower().endswith(ext) for ext in IMAGE_EXTS
        )

        effective_read_mode = (
            (tab_state.mode == "preview") if (is_markdown or is_image) else False
        )

        self._toggle_box.set_visible(is_markdown and self._preview is not None)

        if new_path != self._current_path:
            old_path = self._current_path
            if self._file_unsubscribe:
                self._file_unsubscribe()
                self._file_unsubscribe = None

            self._current_path = new_path

            if new_path and self._watcher:
                try:
                    abs_path = Path(self._filestore.get_path(new_path))
                    self._file_unsubscribe = self._watcher.subscribe_file(
                        abs_path, self._on_file_watched_event
                    )
                except Exception as e:
                    self._logger.error("Could not watch file: %s", e)

            if new_path:
                if is_image:
                    self._loading = False
                    self._current_content = ""
                    self.buffer.set_text("")
                    self._word_count = 0
                    self._is_dirty = False
                    self._event_bus.publish(
                        WordCountChanged(count=0, sender_id=id(self))
                    )
                    self._event_bus.publish(
                        DirtyStateChanged(dirty=False, sender_id=id(self))
                    )
                else:
                    try:
                        self._update_language(new_path)
                        self._loading = True
                        content = self._filestore.read_text(new_path)

                        if content == self._current_content and old_path is not None:
                            self._loading = False
                        else:
                            self._current_content = content
                            self.buffer.set_text(content)
                            self._loading = False
                            self._word_count = self._count_words()
                            self._is_dirty = False
                            self._event_bus.publish(
                                WordCountChanged(
                                    count=self._word_count, sender_id=id(self)
                                )
                            )
                            self._event_bus.publish(
                                DirtyStateChanged(dirty=False, sender_id=id(self))
                            )
                    except Exception as e:
                        self._logger.error("Error loading %s: %s", new_path, e)
                        self._loading = False
                        self._current_content = ""
                        self.buffer.set_text(f"Error loading file: {e}")
            else:
                self._current_content = ""
                self.buffer.set_text("")
                self.buffer.set_language(None)
                self._word_count = 0
                self._event_bus.publish(WordCountChanged(count=0, sender_id=id(self)))

        # Mode logic
        self._read_mode = effective_read_mode

        # Sync buttons
        self._btn_read.handler_block_by_func(self._on_read_toggled)
        self._btn_source.handler_block_by_func(self._on_source_toggled)

        self._btn_read.set_active(effective_read_mode)
        self._btn_source.set_active(not effective_read_mode)

        self._btn_read.handler_unblock_by_func(self._on_read_toggled)
        self._btn_source.handler_unblock_by_func(self._on_source_toggled)

        # Reparenting logic: ensure children are in the right places
        if is_image or effective_read_mode:
            if self._preview:
                if self._preview.widget.get_parent() != self._preview_container:
                    if self._preview.widget.get_parent():
                        self._preview.widget.unparent()
                    self._preview_container.append(self._preview.widget)
            if self._source_scroll.get_parent() != self._source_container:
                if self._source_scroll.get_parent():
                    self._source_scroll.unparent()
                self._source_container.append(self._source_scroll)
            self._stack.set_visible_child_name("preview")
        else:
            if self._source_scroll.get_parent() != self._source_container:
                if self._source_scroll.get_parent():
                    self._source_scroll.unparent()
                self._source_container.append(self._source_scroll)
            if self._preview and self._preview.widget.get_parent():
                if self._preview.widget.get_parent() != self._preview_container:
                    if self._preview.widget.get_parent():
                        self._preview.widget.unparent()
                    self._preview_container.append(self._preview.widget)
            self._stack.set_visible_child_name("source")

        # Perform render if needed
        if effective_read_mode and self._preview and new_path and not is_image:
            self._preview.render(
                self._current_content,
                new_path,
                scroll_to=self._scroll_fraction,
                theme_css=self._theme_css,
                theme_id=app_state.theme_id,
            )
        elif is_image and self._preview and new_path:
            abs_path_str = self._filestore.get_path(new_path)
            self._preview.render_image(
                abs_path_str,
                theme_css=self._theme_css,
                theme_id=app_state.theme_id,
            )
