import gi
import urllib.request
import logging
from typing import Optional, Any, List
from pathlib import Path
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, Gdk, Gio, GLib  # noqa: E402

from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.state import (  # noqa: E402
    AppState,
    EditorAreaState,
    TabState,
    GroupState,
)
from oatbrain.core.events.state import StateUpdated  # noqa: E402
from oatbrain.core.events.ui import (  # noqa: E402
    StatusMessageRequested,
    WordCountChanged,
    DirtyStateChanged,
    FileChangedOnDisk,
    SaveAsRequested,
    TabPathChanged,
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
    ProcessFile,
)
from oatbrain.core.commands.editor import (  # noqa: E402
    ToggleMode,
    ToggleZen,
    RefreshFile,
    NewTab,
    NewNote,
    CloseTab,
    SplitGroupRight,
)
from oatbrain.core.commands.theme import SetTheme  # noqa: E402
from oatbrain.core.ports.renderer import Renderer  # noqa: E402
from oatbrain.core.ports.filestore import FileStore, VaultPath  # noqa: E402
from oatbrain.core.ports.state import StateStore  # noqa: E402
from oatbrain.core.ports.env import Env  # noqa: E402
from oatbrain.core.ports.watcher import FileWatcher  # noqa: E402
from oatbrain.core.wikilink import WikilinkResolver  # noqa: E402
from oatbrain.core.theme.engine import generate_gtk_css  # noqa: E402
from oatbrain.core.theme.models import ThemeData  # noqa: E402
from oatbrain.adapters.theme import load_theme  # noqa: E402
from oatbrain.core.events.mermaid import MermaidFetchResult  # noqa: E402
from oatbrain.core.ports.config import AppConfig  # noqa: E402
from oatbrain.ui.headerbar import HeaderBar  # noqa: E402
from oatbrain.ui.statusbar import StatusBar  # noqa: E402
from oatbrain.ui.tree import FileTree, COL_PATH, COL_IS_DIR  # noqa: E402
from oatbrain.ui.terminal import Terminal  # noqa: E402
from oatbrain.ui.editor_area import EditorArea  # noqa: E402


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
        self._logger = logging.getLogger("oatbrain.shell")
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

        self.editor_area: Optional[EditorArea] = None

        self._setup_commands()

        self._event_bus.subscribe(WordCountChanged, self._on_word_count_changed)
        self._event_bus.subscribe(DirtyStateChanged, self._on_dirty_state_changed)
        self._event_bus.subscribe(
            StatusMessageRequested, self._on_status_message_requested
        )
        self._event_bus.subscribe(FileChangedOnDisk, self._on_file_changed_on_disk)
        self._event_bus.subscribe(SaveAsRequested, self._on_save_as_requested)

        self._setup_initialization()

        self._zen_mode: bool = False
        self._pre_zen_tree_visible: bool = True
        self._pre_zen_terminal_visible: bool = True

    def _setup_commands(self) -> None:
        self._command_router.register(
            OpenFile, self._handle_open_file, "Open File", visible=False
        )
        self._command_router.register(
            ToggleMode, self._handle_toggle_mode, "Toggle Preview Mode"
        )
        self._command_router.register(NewTab, self._handle_new_tab, "New Tab")
        self._command_router.register(NewNote, self._handle_new_note_cmd, "New Note")
        self._command_router.register(CloseTab, self._handle_close_tab, "Close Tab")
        self._command_router.register(
            SplitGroupRight, self._handle_split_group_right, "Split Group Right"
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
            ProcessFile, self._handle_process_file, "Process File", visible=False
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
        """Updates state when a file is opened in the focused tab."""
        if self.editor_area:
            self.editor_area.handle_command(command)

    def _handle_toggle_mode(self, command: ToggleMode) -> None:
        tab_id = command.tab_id
        if not tab_id:
            tab = self._get_focused_tab_state()
            if tab is None:
                return
            tab_id = tab.tab_id
        else:
            # Find the tab state for this specific tab_id
            tab = None
            for g in self._state.editor_area.groups:
                for t in g.tabs:
                    if t.tab_id == tab_id:
                        tab = t
                        break
                if tab:
                    break
            if tab is None:
                return

        new_mode = "preview" if tab.mode == "editor" else "editor"
        ea = self._state.editor_area
        new_ea = self._replace_focused_tab(ea, tab_id, mode=new_mode)
        self._state = replace(self._state, editor_area=new_ea)
        self._event_bus.publish(StateUpdated(self._state))
        self._save_state()

    def _handle_new_tab(self, command: NewTab) -> None:
        if self.editor_area:
            self.editor_area.handle_command(command)

    def _handle_close_tab(self, command: CloseTab) -> None:
        if self.editor_area:
            self.editor_area.handle_command(command)

    def _handle_split_group_right(self, command: SplitGroupRight) -> None:
        if self.editor_area:
            self.editor_area.handle_command(command)

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
        if self.editor_area and self.editor_area.focused_editor:
            self.editor_area.focused_editor.refresh()

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
            tab = self._get_focused_tab_state()
            if tab is not None:
                new_ea = self._replace_focused_tab(
                    self._state.editor_area,
                    tab.tab_id,
                    zoom=self._calculate_zoom(tab.zoom, command),
                )
                self._state = replace(self._state, editor_area=new_ea)
        elif command.component == "preview":
            tab = self._get_focused_tab_state()
            if tab is not None:
                new_ea = self._replace_focused_tab(
                    self._state.editor_area,
                    tab.tab_id,
                    preview_zoom=self._calculate_zoom(tab.preview_zoom, command),
                )
                self._state = replace(self._state, editor_area=new_ea)

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

        if self.editor_area:
            for pane in self.editor_area.groups_panes.values():
                for ed in pane.editors.values():
                    ed.set_zen_mode(self._zen_mode)

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
        self._save_state()
        if self.editor_area:
            self.editor_area.destroy()

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
        self.editor_area = EditorArea(
            filestore=self._filestore,
            event_bus=self._event_bus,
            command_router=self._command_router,
            env=self._env,
            renderer=self._renderer,  # type: ignore
            resolver=self._resolver,  # type: ignore
            watcher=self._watcher,  # type: ignore
            on_state_change_requested=self._on_editor_area_state_change,
        )

        self.main_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.right_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)

        self.tree_pane = FileTree(
            self._filestore,
            self._event_bus,
            self._command_router,
            self._state.vault_root,
            watcher=self._watcher,
            config=self._config,
        )
        self.terminal_placeholder = Terminal(
            self._state.vault_root, self._event_bus, self._command_router
        )

        self.right_paned.set_start_child(self.editor_area.widget)
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

        self._sync_editor_to_state()
        self._event_bus.publish(StateUpdated(self._state))
        self._executor.submit(self._fetch_mermaid_library)
        self._event_bus.subscribe(StateUpdated, self._on_state_updated)

    def _on_state_updated(self, event: StateUpdated) -> None:
        GLib.idle_add(self._sync_editor_to_state)

    def _on_editor_area_state_change(self, ea_state: EditorAreaState) -> None:
        self._state = replace(self._state, editor_area=ea_state)
        self._event_bus.publish(StateUpdated(self._state))
        self._save_state()

    def _sync_editor_to_state(self) -> bool:
        """Syncs the editor area widget with AppState."""
        if self.editor_area:
            self.editor_area.update_from_state(self._state.editor_area, self._state)
        return False

    def _replace_focused_tab(
        self, ea: EditorAreaState, tab_id: str, **updates: Any
    ) -> EditorAreaState:
        new_groups = []
        for g in ea.groups:
            new_tabs = [
                replace(t, **updates) if t.tab_id == tab_id else t for t in g.tabs
            ]
            new_groups.append(replace(g, tabs=tuple(new_tabs)))
        return replace(ea, groups=tuple(new_groups))

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
            ("new_note_inbox", self._on_new_note_inbox),
            ("new_folder", self._on_new_folder),
            ("process_file", self._on_process_file),
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
        if self.editor_area:
            self.editor_area.apply_source_scheme(theme.source_scheme)
            self.editor_area.set_theme_css(css, theme_id=theme_id)
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

    def _handle_new_note_cmd(self, command: NewNote) -> None:
        if self.editor_area:
            self.editor_area.handle_command(command)

    def _handle_process_file(self, command: ProcessFile) -> None:
        path = command.path
        if path is None:
            # Find focused tab path
            tab = self._get_focused_tab_state()
            if tab and tab.open_file:
                path = str(tab.open_file)

        if path:
            prefix = self._config.inbox.process_prefix
            # Use ./ prefix as requested in QUESTIONAIRE
            cmd_str = f"{prefix} ./{path}"
            self._command_router.dispatch(SendToTerminal(text=cmd_str, execute=False))

    def _on_save_as_requested(self, event: SaveAsRequested) -> None:
        import datetime

        # Slugify heading for default filename
        base_slug = self._slugify(event.suggested_filename)
        if not base_slug or base_slug == "untitled":
            # Add timestamp for untitled to avoid collisions (§10.3)
            now = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
            base_slug = f"untitled-{now}"

        target_dir = event.target_dir or self._config.inbox.folder

        # Ensure unique filename (§10.3)
        slug = f"{base_slug}.md"
        path = VaultPath.from_str(f"{target_dir}/{slug}")
        counter = 1
        while self._filestore.exists(path):
            slug = f"{base_slug}-{counter}.md"
            path = VaultPath.from_str(f"{target_dir}/{slug}")
            counter += 1

        # Show a simple dialog to get the filename
        dialog = Adw.MessageDialog(
            transient_for=self.main_window,
            heading="Save New Note",
            body=f"Target directory: {target_dir}",
        )
        entry = Gtk.Entry(text=slug)
        entry.set_margin_top(12)
        entry.set_hexpand(True)
        entry.set_activates_default(True)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        content_box.append(Gtk.Label(label="Filename:", xalign=0))
        content_box.append(entry)
        dialog.set_extra_child(content_box)

        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Save")
        dialog.set_default_response("save")
        dialog.set_close_response("cancel")

        def on_response(d: Adw.MessageDialog, response: str) -> None:
            if response == "save":
                filename = entry.get_text()
                if not filename:
                    return
                if not filename.endswith(".md"):
                    filename += ".md"

                target_dir = event.target_dir or self._config.inbox.folder
                path = VaultPath.from_str(f"{target_dir}/{filename}")

                try:
                    # Create directory if it doesn't exist
                    target_abs = self._state.vault_root / target_dir
                    target_abs.mkdir(parents=True, exist_ok=True)

                    self._filestore.write_text(path, event.content)
                    # Update tab path and mark as not new
                    self._event_bus.publish(
                        TabPathChanged(tab_id=event.tab_id, new_path=path)
                    )
                    self._update_tab_new_state(event.tab_id, False)
                except Exception as e:
                    self._event_bus.publish(
                        StatusMessageRequested(f"Error saving: {e}", 5000)
                    )

        dialog.connect("response", on_response)
        dialog.present()

    def _update_tab_new_state(self, tab_id: str, is_new: bool) -> None:
        if not self._state:
            return
        new_groups = []
        for g in self._state.editor_area.groups:
            new_tabs = []
            for t in g.tabs:
                if t.tab_id == tab_id:
                    new_tabs.append(
                        TabState(
                            tab_id=t.tab_id,
                            open_file=t.open_file,
                            is_new=is_new,
                            title=t.title,
                            target_dir=t.target_dir,
                            mode=t.mode,
                            zoom=t.zoom,
                            preview_zoom=t.preview_zoom,
                        )
                    )
                else:
                    new_tabs.append(t)
            new_groups.append(
                GroupState(
                    group_id=g.group_id,
                    tabs=tuple(new_tabs),
                    active_tab_index=g.active_tab_index,
                )
            )
        ea_state = EditorAreaState(
            groups=tuple(new_groups),
            divider_fractions=self._state.editor_area.divider_fractions,
            focused_group_index=self._state.editor_area.focused_group_index,
        )
        self._on_editor_area_state_change(ea_state)

    def _slugify(self, text: str) -> str:
        import re

        text = text.lower()
        text = re.sub(r"[^a-z0-9]+", "-", text)
        return text.strip("-")

    def _on_process_file(self, *args: Any) -> None:
        selection = self.tree_pane.tree_view.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter:
            path_str = model.get_value(tree_iter, COL_PATH)
            if path_str:
                self._command_router.dispatch(ProcessFile(path=path_str))

    def _on_new_note_inbox(self, *args: Any) -> None:
        target_dir = self._config.inbox.folder
        self._command_router.dispatch(NewNote(target_dir=target_dir))

    def _on_new_note(self, *args: Any) -> None:
        selection = self.tree_pane.tree_view.get_selection()
        model, tree_iter = selection.get_selected()
        target_dir = None
        if tree_iter:
            path_str = model.get_value(tree_iter, COL_PATH)
            is_dir = model.get_value(tree_iter, COL_IS_DIR)
            if is_dir:
                target_dir = path_str
            else:
                # Use parent
                target_dir = str(VaultPath.from_str(path_str).parent)

        if target_dir is None or target_dir == ".":
            target_dir = self._config.inbox.folder

        self._command_router.dispatch(NewNote(target_dir=target_dir))

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
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control><Shift>Return"),
                action=Gtk.CallbackAction.new(self._shortcut_process_file),
            )
        )
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
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>n"),
                action=Gtk.NamedAction.new("app.new_note_inbox"),
            )
        )
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>t"),
                action=Gtk.CallbackAction.new(self._shortcut_new_tab),
            )
        )
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>w"),
                action=Gtk.CallbackAction.new(self._shortcut_close_tab),
            )
        )
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>backslash"),
                action=Gtk.CallbackAction.new(self._shortcut_split_group),
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
        if self.editor_area and self.editor_area.focused_editor:
            self.editor_area.focused_editor.view.grab_focus()
            return True
        return False

    def _shortcut_new_tab(self, *_: Any) -> bool:
        self._command_router.dispatch(NewTab())
        return True

    def _shortcut_close_tab(self, *_: Any) -> bool:
        self._command_router.dispatch(CloseTab())
        return True

    def _shortcut_split_group(self, *_: Any) -> bool:
        self._command_router.dispatch(SplitGroupRight())
        return True

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
            ts = self._get_focused_tab_state()
            if ts and ts.mode == "preview":
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
        if self.editor_area and self.editor_area.focused_editor:
            self.editor_area.focused_editor._save()
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

    def _shortcut_process_file(self, *_: Any) -> bool:
        self._command_router.dispatch(ProcessFile())
        return True

    def _shortcut_send_file_to_terminal(self, *_: Any) -> bool:
        ts = self._get_focused_tab_state()
        if ts and ts.open_file:
            full = str(self._state.vault_root / str(ts.open_file))
            self.terminal_placeholder.send_text(full)
        return True

    def _shortcut_send_selection_to_terminal(self, *_: Any) -> bool:
        if self.editor_area and self.editor_area.focused_editor:
            buf = self.editor_area.focused_editor.buffer
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
        ed = self.editor_area.focused_editor if self.editor_area else None
        editor_view = ed.view if ed else None
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

    def _get_focused_tab_state(self) -> Optional[TabState]:
        ea = self._state.editor_area
        if not ea.groups:
            return None
        group = ea.groups[ea.focused_group_index]
        if not group.tabs:
            return None
        return group.tabs[group.active_tab_index]
