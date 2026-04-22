import gi
import urllib.request
from typing import Optional, Any, List
from pathlib import Path
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, Gdk, Gio, GLib  # noqa: E402

from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.state.app_state import AppState  # noqa: E402
from oatbrain.core.events.state import StateUpdated  # noqa: E402
from oatbrain.core.events.ui import (  # noqa: E402
    StatusMessageRequested,
    WordCountChanged,
    DirtyStateChanged,
    FileChangedOnDisk,
)
from oatbrain.core.commands import (  # noqa: E402
    OpenFile,
    ToggleTree,
    ToggleTerminal,
    RestartTerminal,
    SendToTerminal,
    DismissMermaidWarning,
    SetTreeExpanded,
    Zoom,
)
from oatbrain.core.commands.editor import (  # noqa: E402
    ToggleMode,
    ToggleSplit,
    ToggleZen,
    RefreshFile,
)
from oatbrain.core.commands.theme import SetTheme  # noqa: E402
from oatbrain.core.ports.renderer import Renderer  # noqa: E402
from oatbrain.core.ports.filestore import FileStore  # noqa: E402
from oatbrain.core.ports.state import StateStore  # noqa: E402
from oatbrain.core.ports.env import Env  # noqa: E402
from oatbrain.core.ports.watcher import FileWatcher  # noqa: E402
from oatbrain.core.events.watcher import FileDeleted, FileRenamed  # noqa: E402
from oatbrain.core.wikilink.resolver import WikilinkResolver  # noqa: E402
from oatbrain.core.theme.engine import generate_gtk_css  # noqa: E402
from oatbrain.core.theme.models import ThemeData  # noqa: E402
from oatbrain.adapters.theme.loader import load_theme  # noqa: E402
from oatbrain.core.events.mermaid import MermaidFetchResult  # noqa: E402
from oatbrain.core.ports.config import AppConfig  # noqa: E402
from oatbrain.ui.headerbar import HeaderBar  # noqa: E402
from oatbrain.ui.statusbar import StatusBar  # noqa: E402
from oatbrain.ui.tree import FileTree  # noqa: E402
from oatbrain.ui.terminal import Terminal  # noqa: E402
from oatbrain.ui.editor import Editor  # noqa: E402


class AdwAppShell(Adw.Application):  # type: ignore[misc]
    """Main application shell using Libadwaita (SPEC §7)."""

    _css_provider: Optional[Gtk.CssProvider] = None

    def __init__(
        self,
        event_bus: EventBus,
        command_router: CommandRouter,
        initial_state: AppState,
        filestore: FileStore,
        state_store: StateStore,
        config: AppConfig,
        env: Env,
        renderer: Optional[Renderer] = None,
        resolver: Optional[WikilinkResolver] = None,
        watcher: Optional[FileWatcher] = None,
        application_id: str = "org.oatbrain.Oatbar",
        flags: Gio.ApplicationFlags = Gio.ApplicationFlags.FLAGS_NONE,
    ) -> None:
        super().__init__(application_id=application_id, flags=flags)
        self._event_bus = event_bus
        self._command_router = command_router
        self._state = initial_state
        self._filestore = filestore
        self._state_store = state_store
        self._config = config
        self._env = env
        self._renderer = renderer
        self._resolver = resolver
        self._watcher = watcher
        self._active_theme: Optional[ThemeData] = None
        self._theme_css_provider = Gtk.CssProvider()
        self._executor = ThreadPoolExecutor(max_workers=2)

        self.editor: Optional[Editor] = None

        self._setup_commands()

        self._event_bus.subscribe(WordCountChanged, self._on_word_count_changed)
        self._event_bus.subscribe(DirtyStateChanged, self._on_dirty_state_changed)
        self._event_bus.subscribe(
            StatusMessageRequested, self._on_status_message_requested
        )
        self._event_bus.subscribe(FileChangedOnDisk, self._on_file_changed_on_disk)

        self._setup_initialization()

        self._zen_mode: bool = False
        self._pre_zen_tree_visible: bool = True
        self._pre_zen_terminal_visible: bool = True

    def _setup_commands(self) -> None:
        self._command_router.register(
            OpenFile, self._handle_open_file, "Open File", visible=False
        )
        self._command_router.register(
            ToggleMode, self._handle_toggle_mode, "Toggle Read Mode"
        )
        self._command_router.register(
            ToggleSplit, self._handle_toggle_split, "Toggle Split Mode"
        )
        self._command_router.register(
            ToggleZen, self._handle_toggle_zen, "Toggle Zen Mode"
        )
        self._command_router.register(
            RefreshFile, self._handle_refresh_file, "Refresh Current File"
        )
        self._command_router.register(SetTheme, self._handle_set_theme, "Set Theme")
        self._command_router.register(
            ToggleTree, self._handle_toggle_tree, "Toggle File Tree"
        )
        self._command_router.register(
            ToggleTerminal, self._handle_toggle_terminal, "Toggle Terminal"
        )
        self._command_router.register(
            RestartTerminal, self._handle_restart_terminal, "Restart Terminal"
        )
        self._command_router.register(
            SendToTerminal, self._handle_send_to_terminal, visible=False
        )
        self._command_router.register(
            DismissMermaidWarning, self._handle_dismiss_mermaid, visible=False
        )
        self._command_router.register(
            SetTreeExpanded, self._handle_set_tree_expanded, visible=False
        )
        self._command_router.register(Zoom, self._handle_zoom, visible=False)

    def _on_word_count_changed(self, event: WordCountChanged) -> None:
        pass

    def _on_dirty_state_changed(self, event: DirtyStateChanged) -> None:
        pass

    def _on_status_message_requested(self, event: StatusMessageRequested) -> None:
        pass

    def _on_file_changed_on_disk(self, event: FileChangedOnDisk) -> None:
        GLib.idle_add(self._show_refresh_toast, event.path)

    def _show_refresh_toast(self, path: str) -> bool:
        filename = Path(path).name
        toast = Adw.Toast.new(f"File '{filename}' changed on disk.")
        toast.set_button_label("Refresh")
        toast.set_action_name("app.refresh_file")
        self.toast_overlay.add_toast(toast)
        return False

    def _setup_initialization(self) -> None:
        self._mermaid_banner: Optional[Adw.Banner] = None
        self._event_bus.subscribe(MermaidFetchResult, self._on_mermaid_fetch_result)
        self._event_bus.subscribe(FileDeleted, self._on_file_deleted)
        self._event_bus.subscribe(FileRenamed, self._on_file_renamed)

        self.connect("startup", self._on_startup)
        self.connect("activate", self.on_activate)
        self.connect("shutdown", self._on_shutdown)

    def _on_startup(self, app: Adw.Application) -> None:
        self._setup_global_styles()
        self._load_and_apply_theme(self._state.theme_id)

    def _setup_global_styles(self) -> None:
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                self._theme_css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1,
            )

        if AdwAppShell._css_provider is not None:
            return

        css = """
            .oatbrain-editor {
                font-family: var(
                    --font-mono, 'Cousine', 'JetBrains Mono', 'Fira Code', monospace
                );
                font-size: 12pt;
            }
        """
        AdwAppShell._css_provider = Gtk.CssProvider()
        AdwAppShell._css_provider.load_from_string(css)

        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                AdwAppShell._css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

    def _handle_open_file(self, command: OpenFile) -> None:
        """Updates state when a file is opened."""
        self._state = replace(
            self._state,
            editor=replace(self._state.editor, open_file=command.path),
        )
        self._event_bus.publish(StatusMessageRequested(f"Opened {command.path}"))
        self._event_bus.publish(StateUpdated(self._state))
        self._save_state()

    def _handle_toggle_mode(self, _command: ToggleMode) -> None:
        new_read_mode = not self._state.editor.read_mode
        self._state = replace(
            self._state,
            editor=replace(self._state.editor, read_mode=new_read_mode),
        )
        self._event_bus.publish(StateUpdated(self._state))

    def _handle_toggle_split(self, _command: ToggleSplit) -> None:
        new_split_mode = not self._state.editor.split_mode
        self._state = replace(
            self._state,
            editor=replace(self._state.editor, split_mode=new_split_mode),
        )
        self._event_bus.publish(StateUpdated(self._state))

    def _handle_set_tree_expanded(self, command: SetTreeExpanded) -> None:
        expanded = list(self._state.tree_expanded)
        if command.is_expanded and command.path not in expanded:
            expanded.append(command.path)
        elif not command.is_expanded and command.path in expanded:
            prefix = command.path + "/"
            expanded = [
                p for p in expanded if p != command.path and not p.startswith(prefix)
            ]

        self._state = replace(self._state, tree_expanded=expanded)
        self._event_bus.publish(StateUpdated(self._state))
        self._save_state()

    def _on_file_deleted(self, event: FileDeleted) -> None:
        vault_prefix = str(self._state.vault_root) + "/"
        rel = (
            event.path[len(vault_prefix) :]
            if event.path.startswith(vault_prefix)
            else event.path
        )
        expanded = [
            p
            for p in self._state.tree_expanded
            if p != rel and not p.startswith(rel + "/")
        ]
        state_changed = False
        if len(expanded) != len(self._state.tree_expanded):
            self._state = replace(self._state, tree_expanded=expanded)
            state_changed = True

        if state_changed:
            self._event_bus.publish(StateUpdated(self._state))
            self._save_state()

    def _on_file_renamed(self, event: FileRenamed) -> None:
        vault_prefix = str(self._state.vault_root) + "/"

        def to_rel(p: str) -> str:
            return p[len(vault_prefix) :] if p.startswith(vault_prefix) else p

        old_rel = to_rel(event.old_path)
        new_rel = to_rel(event.new_path)

        def remap(p: str) -> str:
            if p == old_rel:
                return new_rel
            if p.startswith(old_rel + "/"):
                return new_rel + p[len(old_rel) :]
            return p

        state_changed = False
        expanded = [remap(p) for p in self._state.tree_expanded]
        if expanded != self._state.tree_expanded:
            self._state = replace(self._state, tree_expanded=expanded)
            state_changed = True

        # Update editor for renamed file
        from oatbrain.core.ports.filestore import VaultPath as VP

        if (
            self._state.editor.open_file
            and str(self._state.editor.open_file) == old_rel
        ):
            self._state = replace(
                self._state,
                editor=replace(self._state.editor, open_file=VP.from_str(new_rel)),
            )
            state_changed = True

        if state_changed:
            self._event_bus.publish(StateUpdated(self._state))
            self._save_state()

    def _handle_toggle_tree(self, _command: ToggleTree) -> None:
        visible = not self.tree_pane.get_visible()
        self.tree_pane.set_visible(visible)
        self._state = replace(self._state, tree_visible=visible)
        self._save_state()

    def _handle_toggle_terminal(self, _command: ToggleTerminal) -> None:
        visible = not self.terminal_placeholder.widget.get_visible()
        self.terminal_placeholder.widget.set_visible(visible)
        self._state = replace(self._state, terminal_visible=visible)
        self._save_state()

    def _handle_restart_terminal(self, _command: RestartTerminal) -> None:
        self.terminal_placeholder.restart()

    def _handle_send_to_terminal(self, command: SendToTerminal) -> None:
        if not self.terminal_placeholder.widget.get_visible():
            self.terminal_placeholder.widget.set_visible(True)
            self._state = replace(self._state, terminal_visible=True)
            self._save_state()
            self.header_bar.terminal_toggle.set_active(True)

        def _do_send() -> bool:
            self.terminal_placeholder.grab_focus()
            text = command.text
            if command.execute:
                clean_text = text.rstrip("\r\n")
                if not clean_text.endswith(" "):
                    text = clean_text + " \r"
                elif not text.endswith("\r"):
                    text = clean_text + "\r"
            self.terminal_placeholder.send_text_throttled("\x15" + text)
            return False

        GLib.idle_add(_do_send)

    def _handle_dismiss_mermaid(self, _command: DismissMermaidWarning) -> None:
        self._state = replace(self._state, mermaid_dismissed=True)
        if self._mermaid_banner:
            self._mermaid_banner.set_revealed(False)
        self._save_state()

    def _on_mermaid_fetch_result(self, event: MermaidFetchResult) -> None:
        if event.success or self._state.mermaid_dismissed:
            return
        cache_dir = self._env.get_xdg_cache_home() / "oatbrain"
        if (cache_dir / "mermaid.min.js").exists():
            return
        if not self._mermaid_banner:
            self._mermaid_banner = Adw.Banner.new(
                "Mermaid support requires a one-time library download."
            )
            self._mermaid_banner.set_button_label("Dismiss")
            self._mermaid_banner.connect(
                "button-clicked",
                lambda *_: self._command_router.dispatch(DismissMermaidWarning()),
            )
            if hasattr(self, "toolbar_view"):
                self.toolbar_view.add_top_bar(self._mermaid_banner)
        self._mermaid_banner.set_revealed(True)

    def _handle_toggle_zen(self, _command: ToggleZen) -> None:
        GLib.idle_add(self._apply_zen_toggle)

    def _handle_refresh_file(self, _command: RefreshFile) -> None:
        if self.editor:
            self.editor.refresh()

    def _calculate_zoom(self, current: float, command: Zoom) -> float:
        new_zoom = 1.0 if command.reset else current + command.delta
        return max(0.5, min(3.0, new_zoom))

    def _handle_zoom(self, command: Zoom) -> None:
        if command.component == "tree":
            self._state = replace(
                self._state,
                tree_zoom=self._calculate_zoom(self._state.tree_zoom, command),
            )
        elif command.component == "terminal":
            self._state = replace(
                self._state,
                terminal_zoom=self._calculate_zoom(self._state.terminal_zoom, command),
            )
        elif command.component == "editor":
            self._state = replace(
                self._state,
                editor=replace(
                    self._state.editor,
                    zoom=self._calculate_zoom(self._state.editor.zoom, command),
                ),
            )
        elif command.component == "preview":
            self._state = replace(
                self._state,
                editor=replace(
                    self._state.editor,
                    preview_zoom=self._calculate_zoom(
                        self._state.editor.preview_zoom, command
                    ),
                ),
            )

        self._event_bus.publish(StateUpdated(self._state))
        self._save_state()

    def _apply_zen_toggle(self) -> bool:
        self._zen_mode = not self._zen_mode
        if self._zen_mode:
            self._pre_zen_tree_visible = self.tree_pane.get_visible()
            self._pre_zen_terminal_visible = (
                self.terminal_placeholder.widget.get_visible()
            )
            self.tree_pane.set_visible(False)
            self.terminal_placeholder.widget.set_visible(False)
            self.toolbar_view.set_reveal_top_bars(False)
            self.status_bar.widget.set_visible(False)
            self.toolbar_view.set_extend_content_to_top_edge(True)
        else:
            self.tree_pane.set_visible(self._pre_zen_tree_visible)
            self.terminal_placeholder.widget.set_visible(self._pre_zen_terminal_visible)
            self.toolbar_view.set_reveal_top_bars(True)
            self.status_bar.widget.set_visible(True)
            self.toolbar_view.set_extend_content_to_top_edge(False)

        if self.editor:
            self.editor.set_zen_mode(self._zen_mode)

        self.header_bar.zen_toggle.handler_block_by_func(self._on_zen_toggled)
        self.header_bar.zen_toggle.set_active(self._zen_mode)
        self.header_bar.zen_toggle.handler_unblock_by_func(self._on_zen_toggled)
        return False

    def _on_mouse_motion(
        self, ctrl: Gtk.EventControllerMotion, x: float, y: float
    ) -> None:
        if self._zen_mode:
            if self.toolbar_view.get_reveal_top_bars():
                if y > 60:
                    self.toolbar_view.set_reveal_top_bars(False)
            else:
                if y < 5:
                    self.toolbar_view.set_reveal_top_bars(True)

    def _save_state(self) -> None:
        if not hasattr(self, "main_window") or not self.main_window.get_realized():
            return
        width = self.main_window.get_width()
        height = self.main_window.get_height()
        tree_visible = self.tree_pane.get_visible()
        terminal_visible = self.terminal_placeholder.widget.get_visible()
        tree_width = self._state.tree_width
        if tree_visible:
            pos = self.main_paned.get_position()
            if pos > 0:
                tree_width = pos
        terminal_width = self._state.terminal_width
        if terminal_visible:
            total_right = self.right_paned.get_width()
            pos = self.right_paned.get_position()
            if total_right > 0 and pos > 0:
                terminal_width = total_right - pos

        self._state = replace(
            self._state,
            window_width=width,
            window_height=height,
            tree_width=tree_width,
            tree_visible=tree_visible,
            terminal_width=terminal_width,
            terminal_visible=terminal_visible,
        )
        self._state_store.save(self._state)

    def _on_shutdown(self, *args: Any) -> None:
        if self._watcher:
            self._watcher.stop()
        self._save_state()

    def on_activate(self, app: Adw.Application) -> None:
        self.main_window = Adw.ApplicationWindow(application=app)
        self.main_window.set_title("oatbrain")
        self.main_window.set_default_size(
            self._state.window_width, self._state.window_height
        )

        self.toast_overlay = Adw.ToastOverlay()
        self.toolbar_view = Adw.ToolbarView()
        self.header_bar = HeaderBar(self._event_bus, self._command_router)
        self.toolbar_view.add_top_bar(self.header_bar.widget)

        # Editor area
        self.editor = Editor(
            self._filestore,
            self._event_bus,
            self._command_router,
            self._env,
            vault_root=self._state.vault_root,
            renderer=self._renderer,
            resolver=self._resolver,
        )

        self.main_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.right_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)

        self.tree_pane = FileTree(
            self._filestore,
            self._event_bus,
            self._command_router,
            self._state.vault_root,
        )
        self.terminal_placeholder = Terminal(
            self._state.vault_root, self._event_bus, self._command_router
        )

        self.right_paned.set_start_child(self.editor.widget)
        self.right_paned.set_end_child(self.terminal_placeholder.widget)
        self.right_paned.set_resize_start_child(True)
        self.right_paned.set_resize_end_child(False)

        self.main_paned.set_start_child(self.tree_pane)
        self.main_paned.set_end_child(self.right_paned)
        self.main_paned.set_resize_start_child(False)
        self.main_paned.set_resize_end_child(True)

        self.toolbar_view.set_content(self.main_paned)
        self.status_bar = StatusBar(self._event_bus)
        self.toolbar_view.add_bottom_bar(self.status_bar.widget)

        self.toast_overlay.set_child(self.toolbar_view)
        self.main_window.set_content(self.toast_overlay)

        self.tree_pane.set_visible(self._state.tree_visible)
        self.header_bar.tree_toggle.set_active(self._state.tree_visible)
        self.terminal_placeholder.widget.set_visible(self._state.terminal_visible)
        self.header_bar.terminal_toggle.set_active(self._state.terminal_visible)
        self.main_paned.set_position(self._state.tree_width)
        self._update_right_paned_position()

        self.header_bar.tree_toggle.connect("toggled", self._on_tree_toggled)
        self.header_bar.terminal_toggle.connect("toggled", self._on_terminal_toggled)
        self.header_bar.terminal_restart.connect(
            "clicked", self._on_terminal_restart_clicked
        )
        self.header_bar.zen_toggle.connect("toggled", self._on_zen_toggled)
        self.main_window.connect("notify::is-active", self._on_window_active_changed)

        self._setup_actions()
        self._setup_shortcuts()

        self.motion_ctrl = Gtk.EventControllerMotion.new()
        self.motion_ctrl.connect("motion", self._on_mouse_motion)
        self.main_window.add_controller(self.motion_ctrl)

        self.main_window.present()
        self._load_and_apply_theme(self._state.theme_id)
        GLib.idle_add(self._connect_late_signals)

        if self._watcher:
            self._watcher.subscribe(lambda e: self._event_bus.publish(e))
            self._watcher.start(self._state.vault_root)

        self._sync_editor_to_state()
        self._event_bus.publish(StateUpdated(self._state))
        self._executor.submit(self._fetch_mermaid_library)
        self._event_bus.subscribe(StateUpdated, self._on_state_updated)

    def _on_state_updated(self, event: StateUpdated) -> None:
        GLib.idle_add(self._sync_editor_to_state)

    def _sync_editor_to_state(self) -> bool:
        """Syncs the editor widget with AppState."""
        if self.editor:
            self.editor.update_from_state(self._state.editor, self._state)
        return False

    def _fetch_mermaid_library(self) -> None:
        cache_dir = self._env.get_xdg_cache_home() / "oatbrain"
        target = cache_dir / "mermaid.min.js"
        if target.exists():
            return
        url = "https://cdn.jsdelivr.net/npm/mermaid@latest/dist/mermaid.min.js"
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(url, timeout=10) as response:
                content = response.read()
                target.write_bytes(content)
            GLib.idle_add(
                lambda: self._event_bus.publish(MermaidFetchResult(success=True))
            )
        except Exception as e:
            error_str = str(e)
            GLib.idle_add(
                lambda: self._event_bus.publish(
                    MermaidFetchResult(success=False, error=error_str)
                )
            )

    def _connect_late_signals(self) -> bool:
        if not hasattr(self, "main_window") or not self.main_window.get_realized():
            return bool(GLib.SOURCE_CONTINUE)
        self.main_paned.connect("notify::position", lambda *_: self._save_state())
        self.right_paned.connect("notify::position", lambda *_: self._save_state())
        self.main_window.connect("notify::default-width", lambda *_: self._save_state())
        self.main_window.connect(
            "notify::default-height", lambda *_: self._save_state()
        )
        return False

    def _update_right_paned_position(self) -> None:
        total_width = self._state.window_width
        tree_width = self._state.tree_width
        terminal_width = self._state.terminal_width
        editor_target_width = total_width - tree_width - terminal_width
        if editor_target_width > 0:
            self.right_paned.set_position(editor_target_width)

    def _setup_actions(self) -> None:
        actions = [
            ("open_config", self._on_open_config),
            ("set_theme_light", lambda *_: self._on_set_theme("Light")),
            ("set_theme_dark", lambda *_: self._on_set_theme("Dark")),
            ("set_theme_high_contrast", lambda *_: self._on_set_theme("HighContrast")),
            ("new_note", self._on_new_note),
            ("new_folder", self._on_new_folder),
            ("rename_file", self._on_rename_file),
            ("delete_file", self._on_delete_file),
            ("refresh_file", self._on_refresh_file),
        ]
        for name, callback in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

    def _load_and_apply_theme(self, theme_id: str) -> None:
        try:
            theme = load_theme(theme_id)
        except Exception:
            return
        self._active_theme = theme
        style_manager = Adw.StyleManager.get_default()
        if theme.kind in ("dark", "high-contrast-dark"):
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else:
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        css = generate_gtk_css(theme)
        self._theme_css_provider.load_from_string(css)
        if self.editor:
            self.editor.apply_source_scheme(theme.source_scheme)
            self.editor.set_theme_css(css, theme_id=theme_id)
        if hasattr(self, "terminal_placeholder"):
            self.terminal_placeholder.apply_theme(theme)

    def _handle_set_theme(self, command: SetTheme) -> None:
        new_state = replace(
            self._state,
            theme_id=command.theme_id,
            theme_name=command.theme_id.replace("-", " ").title(),
        )
        self._state = new_state
        self._load_and_apply_theme(command.theme_id)
        self._event_bus.publish(StateUpdated(self._state))
        self._save_state()

    def _on_open_config(self, *args: Any) -> None:
        print("Action: Open config file")

    def _on_set_theme(self, theme: str) -> None:
        if theme == "Light":
            self._command_router.dispatch(SetTheme(theme_id="solarized-light"))
        elif theme == "HighContrast":
            self._command_router.dispatch(SetTheme(theme_id="high-contrast-dark"))
        else:
            self._command_router.dispatch(SetTheme(theme_id="monokai-dark"))

    def _on_new_note(self, *args: Any) -> None:
        print("Action: New Note")

    def _on_new_folder(self, *args: Any) -> None:
        print("Action: New Folder")

    def _on_rename_file(self, *args: Any) -> None:
        print("Action: Rename File")

    def _on_delete_file(self, *args: Any) -> None:
        print("Action: Delete File")

    def _on_refresh_file(self, *args: Any) -> None:
        self._command_router.dispatch(RefreshFile())

    def _on_window_active_changed(
        self, window: Adw.ApplicationWindow, _pspec: object
    ) -> None:
        pass

    def _on_tree_toggled(self, btn: Gtk.ToggleButton) -> None:
        visible = btn.get_active()
        self.tree_pane.set_visible(visible)
        self._save_state()

    def _on_terminal_toggled(self, btn: Gtk.ToggleButton) -> None:
        visible = btn.get_active()
        self.terminal_placeholder.widget.set_visible(visible)
        self._save_state()

    def _on_terminal_restart_clicked(self, _btn: Gtk.Button) -> None:
        self._command_router.dispatch(RestartTerminal())

    def _on_zen_toggled(self, _btn: Gtk.ToggleButton) -> None:
        self._command_router.dispatch(ToggleZen())

    def _setup_shortcuts(self) -> None:
        controller = Gtk.ShortcutController.new()
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.main_window.add_controller(controller)
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>p"),
                action=Gtk.CallbackAction.new(self._shortcut_open_palette),
            )
        )
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control><Shift>p"),
                action=Gtk.CallbackAction.new(self._shortcut_open_palette_commands),
            )
        )
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("F1"),
                action=Gtk.CallbackAction.new(self._shortcut_open_palette_help),
            )
        )
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>grave"),
                action=Gtk.CallbackAction.new(self._shortcut_toggle_terminal),
            )
        )
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>1"),
                action=Gtk.CallbackAction.new(
                    lambda *_: self.tree_pane.grab_focus() or True
                ),
            )
        )
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>2"),
                action=Gtk.CallbackAction.new(self._shortcut_focus_editor),
            )
        )
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>3"),
                action=Gtk.CallbackAction.new(
                    lambda *_: self.terminal_placeholder.widget.grab_focus() or True
                ),
            )
        )
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>Tab"),
                action=Gtk.CallbackAction.new(self._shortcut_cycle_focus),
            )
        )
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>s"),
                action=Gtk.CallbackAction.new(self._shortcut_save),
            )
        )
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("F5"),
                action=Gtk.CallbackAction.new(self._shortcut_refresh),
            )
        )
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>e"),
                action=Gtk.CallbackAction.new(self._shortcut_toggle_mode),
            )
        )
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control><Shift>z"),
                action=Gtk.CallbackAction.new(self._shortcut_toggle_zen),
            )
        )
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control><Shift>y"),
                action=Gtk.CallbackAction.new(self._shortcut_send_file_to_terminal),
            )
        )
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control><Shift>u"),
                action=Gtk.CallbackAction.new(
                    self._shortcut_send_selection_to_terminal
                ),
            )
        )
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>plus"),
                action=Gtk.CallbackAction.new(lambda *_: self._shortcut_zoom(0.1)),
            )
        )
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>minus"),
                action=Gtk.CallbackAction.new(lambda *_: self._shortcut_zoom(-0.1)),
            )
        )

    def _shortcut_focus_editor(self, *_: Any) -> bool:
        if self.editor:
            self.editor.view.grab_focus()
            return True
        return False

    def _shortcut_zoom(self, delta: float, reset: bool = False) -> bool:
        current = self.main_window.get_focus()
        if not current:
            return False
        if current == self.tree_pane or current.is_ancestor(self.tree_pane):
            self._command_router.dispatch(Zoom("tree", delta, reset))
        elif current == self.terminal_placeholder.widget or current.is_ancestor(
            self.terminal_placeholder.widget
        ):
            self._command_router.dispatch(Zoom("terminal", delta, reset))
        else:
            if self._state.editor.read_mode:
                self._command_router.dispatch(Zoom("preview", delta, reset))
            else:
                self._command_router.dispatch(Zoom("editor", delta, reset))
        return True

    def _shortcut_open_palette(self, *_: Any) -> bool:
        from oatbrain.ui.palette import Palette

        palette = Palette(
            self._state, self._config, self._filestore, self._command_router
        )
        palette.present(self.main_window)
        return True

    def _shortcut_open_palette_commands(self, *_: Any) -> bool:
        from oatbrain.ui.palette import Palette

        palette = Palette(
            self._state, self._config, self._filestore, self._command_router, ">"
        )
        palette.present(self.main_window)
        return True

    def _shortcut_open_palette_help(self, *_: Any) -> bool:
        from oatbrain.ui.palette import Palette

        palette = Palette(
            self._state, self._config, self._filestore, self._command_router, "?"
        )
        palette.present(self.main_window)
        return True

    def _shortcut_save(self, *_: Any) -> bool:
        if self.editor:
            self.editor._save()
        return True

    def _shortcut_refresh(self, *_: Any) -> bool:
        self._command_router.dispatch(RefreshFile())
        return True

    def _shortcut_toggle_mode(self, *_: Any) -> bool:
        self._command_router.dispatch(ToggleMode())
        return True

    def _shortcut_toggle_zen(self, *_: Any) -> bool:
        self._command_router.dispatch(ToggleZen())
        return True

    def _shortcut_send_file_to_terminal(self, *_: Any) -> bool:
        path = self._state.editor.open_file
        if path:
            full = str(self._state.vault_root / str(path))
            self.terminal_placeholder.send_text(full)
        return True

    def _shortcut_send_selection_to_terminal(self, *_: Any) -> bool:
        if self.editor:
            buf = self.editor.buffer
            if buf.get_has_selection():
                start, end = buf.get_selection_bounds()
                text = buf.get_text(start, end, True)
                heredoc = f"<<'__OATBRAIN__'\n{text}\n__OATBRAIN__\n"
                self.terminal_placeholder.send_text(heredoc)
        return True

    def _shortcut_toggle_tree(self, *_: Any) -> bool:
        self.header_bar.tree_toggle.set_active(
            not self.header_bar.tree_toggle.get_active()
        )
        return True

    def _shortcut_toggle_terminal(self, *_: Any) -> bool:
        self.header_bar.terminal_toggle.set_active(
            not self.header_bar.terminal_toggle.get_active()
        )
        return True

    def _shortcut_cycle_focus(self, *_: Any) -> bool:
        editor_view = self.editor.view if self.editor else None
        targets: List[Optional[Gtk.Widget]] = [
            self.tree_pane,
            editor_view,
            self.terminal_placeholder.widget,
        ]
        targets = [t for t in targets if t is not None]
        current = self.main_window.get_focus()
        start_idx = 0
        if current:
            for i in range(len(targets)):
                t = targets[i]
                if t and (current == t or current.is_ancestor(t)):
                    start_idx = (i + 1) % len(targets)
                    break
        for j in range(len(targets)):
            idx = (start_idx + j) % len(targets)
            target = targets[idx]
            if target and target.get_visible():
                target.grab_focus()
                return True
        return True
