from typing import Any, List, Optional
from dataclasses import replace
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, Gdk, Gio, GLib  # noqa: E402

from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.state.app_state import AppState  # noqa: E402
from oatbrain.core.events.state import StateUpdated  # noqa: E402
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
    UpdateWordCount,
    SetDirty,
    ToggleMode,
    ToggleZen,
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
from oatbrain.core.ports.config import AppConfig  # noqa: E402
from oatbrain.ui.headerbar import HeaderBar  # noqa: E402
from oatbrain.ui.statusbar import StatusBar  # noqa: E402
from oatbrain.ui.tree import FileTree  # noqa: E402
from oatbrain.ui.editor import Editor  # noqa: E402
from oatbrain.ui.terminal import Terminal  # noqa: E402


from concurrent.futures import ThreadPoolExecutor  # noqa: E402
import urllib.request  # noqa: E402
from oatbrain.core.events.mermaid import MermaidFetchResult  # noqa: E402


class AdwAppShell(Adw.Application):  # type: ignore[misc]
    """Main application shell using Libadwaita."""

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
        watcher: Optional[FileWatcher] = None,
        renderer: Optional[Renderer] = None,
        resolver: Optional[WikilinkResolver] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._event_bus = event_bus
        self._command_router = command_router
        self._state = initial_state
        self._filestore = filestore
        self._state_store = state_store
        self._config = config
        self._env = env
        self._renderer = renderer
        self._resolver = resolver
        self._watcher = watcher  # Store watcher
        self._active_theme: Optional[ThemeData] = None
        self._theme_css_provider = Gtk.CssProvider()
        self._executor = ThreadPoolExecutor(max_workers=2)

        self._command_router.register(
            OpenFile, self._handle_open_file, "Open File", visible=False
        )
        self._command_router.register(
            UpdateWordCount, self._handle_update_word_count, visible=False
        )
        self._command_router.register(SetDirty, self._handle_set_dirty, visible=False)
        self._command_router.register(
            ToggleMode, self._handle_toggle_mode, "Toggle Read Mode"
        )
        self._command_router.register(
            ToggleZen, self._handle_toggle_zen, "Toggle Zen Mode"
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

        self._zen_mode: bool = False
        self._pre_zen_tree_visible: bool = True
        self._pre_zen_terminal_visible: bool = True

        self._mermaid_banner: Optional[Adw.Banner] = None
        self._event_bus.subscribe(MermaidFetchResult, self._on_mermaid_fetch_result)
        self._event_bus.subscribe(FileDeleted, self._on_file_deleted)
        self._event_bus.subscribe(FileRenamed, self._on_file_renamed)

        self.connect("startup", self._on_startup)
        self.connect("activate", self.on_activate)
        self.connect("shutdown", self._on_shutdown)

    def _on_startup(self, app: Adw.Application) -> None:
        """Called once when the application starts."""
        self._setup_global_styles()
        self._load_and_apply_theme(self._state.theme_id)

    def _setup_global_styles(self) -> None:
        """Loads mandatory CSS styles for the application (SPEC §19)."""
        display = Gdk.Display.get_default()
        if display:
            # Register theme CSS provider every time (instance-level, no guard).
            Gtk.StyleContext.add_provider_for_display(
                display,
                self._theme_css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1,
            )

        if AdwAppShell._css_provider is not None:
            return  # Font CSS is process-global; only load once.

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
        new_editor = replace(self._state.editor, open_file=command.path, word_count=0)
        self._state = replace(
            self._state, editor=new_editor, status_message=f"Opened {command.path}"
        )
        self._event_bus.publish(StateUpdated(self._state))
        self._save_state()

    def _handle_update_word_count(self, command: UpdateWordCount) -> None:
        new_editor = replace(self._state.editor, word_count=command.count)
        self._state = replace(self._state, editor=new_editor)
        self._event_bus.publish(StateUpdated(self._state))

    def _handle_set_dirty(self, command: SetDirty) -> None:
        new_editor = replace(self._state.editor, is_dirty=command.dirty)
        self._state = replace(self._state, editor=new_editor)
        self._event_bus.publish(StateUpdated(self._state))

    def _handle_toggle_mode(self, _command: ToggleMode) -> None:
        new_read_mode = not self._state.editor.read_mode
        new_editor = replace(self._state.editor, read_mode=new_read_mode)
        self._state = replace(self._state, editor=new_editor)
        self._event_bus.publish(StateUpdated(self._state))

    def _handle_set_tree_expanded(self, command: SetTreeExpanded) -> None:
        expanded = list(self._state.tree_expanded)
        if command.is_expanded and command.path not in expanded:
            expanded.append(command.path)
        elif not command.is_expanded and command.path in expanded:
            # Prune exact path and all its descendants
            prefix = command.path + "/"
            expanded = [
                p for p in expanded if p != command.path and not p.startswith(prefix)
            ]

        self._state = replace(self._state, tree_expanded=expanded)
        self._event_bus.publish(StateUpdated(self._state))
        self._save_state()

    def _on_file_deleted(self, event: FileDeleted) -> None:
        """Prune deleted paths from tree_expanded and persist."""
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
        if len(expanded) != len(self._state.tree_expanded):
            self._state = replace(self._state, tree_expanded=expanded)
            self._event_bus.publish(StateUpdated(self._state))
            self._save_state()

    def _on_file_renamed(self, event: FileRenamed) -> None:
        """Update tree_expanded paths when a file/directory is renamed."""
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

        expanded = [remap(p) for p in self._state.tree_expanded]
        if expanded != self._state.tree_expanded:
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
            # Sync the toggle button in the header bar
            self.header_bar.terminal_toggle.set_active(True)

        def _do_send() -> bool:
            self.terminal_placeholder.grab_focus()
            text = command.text

            # Ensure a space before return if execution requested.
            # Workaround for some CLI prompt-submission bugs.
            if command.execute:
                # Strip existing \r or \n to clean up
                clean_text = text.rstrip("\r\n")
                if not clean_text.endswith(" "):
                    text = clean_text + " \r"
                elif not text.endswith("\r"):
                    text = clean_text + "\r"
            elif not (text.endswith("\r") or text.endswith("\n")):
                # For non-execute, we still might want to ensure a \r if intended
                # but let's stick to literal for now as per user instruction.
                pass

            # Send Ctrl+U (\x15) to clear the line before typing.
            self.terminal_placeholder.send_text_throttled("\x15" + text)
            return False

        # Run on idle to ensure the palette dialog has closed and
        # focus restoration has finished before we steal it.
        GLib.idle_add(_do_send)

    def _handle_dismiss_mermaid(self, _command: DismissMermaidWarning) -> None:
        """Persistently dismiss the Mermaid warning."""
        self._state = replace(self._state, mermaid_dismissed=True)
        if self._mermaid_banner:
            self._mermaid_banner.set_revealed(False)
        self._save_state()

    def _on_mermaid_fetch_result(self, event: MermaidFetchResult) -> None:
        """Show a banner if the Mermaid library fetch failed (SPEC §15.1)."""
        if event.success or self._state.mermaid_dismissed:
            return

        # Check if we have it in cache already
        cache_dir = self._env.get_xdg_cache_home() / "oatbrain"
        if (cache_dir / "mermaid.min.js").exists():
            return

        if not self._mermaid_banner:
            self._mermaid_banner = Adw.Banner.new(
                "Mermaid support requires an internet connection to download "
                "its library once. Diagrams will not render."
            )
            self._mermaid_banner.set_button_label("Dismiss")
            self._mermaid_banner.connect(
                "button-clicked",
                lambda *_: self._command_router.dispatch(DismissMermaidWarning()),
            )
            # Add to the top of ToolbarView if it exists
            if hasattr(self, "toolbar_view"):
                self.toolbar_view.add_top_bar(self._mermaid_banner)

        self._mermaid_banner.set_revealed(True)

    def _handle_toggle_zen(self, _command: ToggleZen) -> None:
        GLib.idle_add(self._apply_zen_toggle)

    def _calculate_zoom(self, current: float, command: Zoom) -> float:
        """Calculate new zoom level with clamping (§19)."""
        new_zoom = 1.0 if command.reset else current + command.delta
        return max(0.5, min(3.0, new_zoom))

    def _handle_zoom(self, command: Zoom) -> None:
        """Handle zoom command for different components."""
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
            new_editor = replace(
                self._state.editor,
                zoom=self._calculate_zoom(self._state.editor.zoom, command),
            )
            self._state = replace(self._state, editor=new_editor)
        elif command.component == "preview":
            new_editor = replace(
                self._state.editor,
                preview_zoom=self._calculate_zoom(
                    self._state.editor.preview_zoom, command
                ),
            )
            self._state = replace(self._state, editor=new_editor)

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
        self.editor.set_zen_mode(self._zen_mode)
        self.header_bar.zen_toggle.handler_block_by_func(self._on_zen_toggled)
        self.header_bar.zen_toggle.set_active(self._zen_mode)
        self.header_bar.zen_toggle.handler_unblock_by_func(self._on_zen_toggled)
        return False

    def _on_mouse_motion(
        self, ctrl: Gtk.EventControllerMotion, x: float, y: float
    ) -> None:
        """Reveal top bar in Zen mode when mouse is near top edge."""
        if self._zen_mode:
            if self.toolbar_view.get_reveal_top_bars():
                if y > 60:
                    self.toolbar_view.set_reveal_top_bars(False)
            else:
                if y < 5:
                    self.toolbar_view.set_reveal_top_bars(True)

    def _save_state(self) -> None:
        """Collects current UI state and persists it via StateStore."""
        if not hasattr(self, "main_window") or not self.main_window.get_realized():
            return

        # Get current dimensions
        width = self.main_window.get_width()
        height = self.main_window.get_height()

        # Get pane visibility
        tree_visible = self.tree_pane.get_visible()
        terminal_visible = self.terminal_placeholder.widget.get_visible()

        # Get pane positions (only update if visible and reasonable)
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
        """Ensures state is saved and watcher is stopped on application exit."""
        if self._watcher:  # Ensure watcher is stopped
            self._watcher.stop()
        self._save_state()

    def on_activate(self, app: Adw.Application) -> None:
        # 1. Build window
        self.main_window = Adw.ApplicationWindow(application=app)
        self.main_window.set_title("oatbrain")
        self.main_window.set_default_size(
            self._state.window_width, self._state.window_height
        )

        # 2. Build layout components
        self.toolbar_view = Adw.ToolbarView()
        self.header_bar = HeaderBar(self._event_bus)
        self.toolbar_view.add_top_bar(self.header_bar.widget)

        self.main_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.right_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)

        self.tree_pane = FileTree(
            self._filestore,
            self._event_bus,
            self._command_router,
            self._state.vault_root,
        )
        self.editor = Editor(
            self._filestore,
            self._event_bus,
            self._command_router,
            self._env,
            vault_root=self._state.vault_root,
            renderer=self._renderer,
            resolver=self._resolver,
        )
        self.terminal_placeholder = Terminal(
            self._state.vault_root, self._event_bus, self._command_router
        )

        # 3. Assemble hierarchy (Bottom-Up)
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

        self.main_window.set_content(self.toolbar_view)

        # 4. Initial layout from state
        self.tree_pane.set_visible(self._state.tree_visible)
        self.header_bar.tree_toggle.set_active(self._state.tree_visible)
        self.terminal_placeholder.widget.set_visible(self._state.terminal_visible)
        self.header_bar.terminal_toggle.set_active(self._state.terminal_visible)
        self.main_paned.set_position(self._state.tree_width)
        self._update_right_paned_position()

        # 5. Wire non-critical signals
        self.header_bar.tree_toggle.connect("toggled", self._on_tree_toggled)
        self.header_bar.terminal_toggle.connect("toggled", self._on_terminal_toggled)
        self.header_bar.terminal_restart.connect(
            "clicked", self._on_terminal_restart_clicked
        )
        self.header_bar.zen_toggle.connect("toggled", self._on_zen_toggled)
        # Window blur → autosave (§10.3)
        self.main_window.connect("notify::is-active", self._on_window_active_changed)
        self._setup_actions()
        self._setup_shortcuts()

        self.motion_ctrl = Gtk.EventControllerMotion.new()
        self.motion_ctrl.connect("motion", self._on_mouse_motion)
        self.main_window.add_controller(self.motion_ctrl)

        # 6. Finalize
        self.main_window.present()

        # 7. Apply theme now that all sub-widgets (editor, terminal) exist.
        # _on_startup applied AdwStyleManager early, but editor/terminal are
        # only wired up after activate, so we must call this again here.
        self._load_and_apply_theme(self._state.theme_id)

        # 8. Wire proactive saving LATE to avoid construction noise
        GLib.idle_add(self._connect_late_signals)

        # 9. Start file watcher
        if self._watcher:
            self._watcher.subscribe(lambda e: self._event_bus.publish(e))
            self._watcher.start(self._state.vault_root)

        # Emit initial state
        self._event_bus.publish(StateUpdated(self._state))

        # Start Mermaid fetch in background
        self._executor.submit(self._fetch_mermaid_library)

    def _fetch_mermaid_library(self) -> None:
        """Downloads mermaid.js to the cache directory (SPEC §15.1)."""
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
            err = str(e)
            GLib.idle_add(
                lambda: self._event_bus.publish(
                    MermaidFetchResult(success=False, error=err)
                )
            )

    def _connect_late_signals(self) -> bool:
        """Connects signals that trigger state saving."""
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
        """Calculates and sets the right paned position."""
        # Use state width as a proxy before realization.
        total_width = self._state.window_width
        tree_width = self._state.tree_width
        terminal_width = self._state.terminal_width

        editor_target_width = total_width - tree_width - terminal_width
        if editor_target_width > 0:
            self.right_paned.set_position(editor_target_width)

    def _setup_actions(self) -> None:
        """Sets up GActions for the menu items."""
        actions = [
            ("open_config", self._on_open_config),
            ("set_theme_light", lambda *_: self._on_set_theme("Light")),
            ("set_theme_dark", lambda *_: self._on_set_theme("Dark")),
            ("set_theme_high_contrast", lambda *_: self._on_set_theme("HighContrast")),
            ("new_note", self._on_new_note),
            ("new_folder", self._on_new_folder),
            ("rename_file", self._on_rename_file),
            ("delete_file", self._on_delete_file),
        ]
        for name, callback in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

    def _load_and_apply_theme(self, theme_id: str) -> None:
        """Load theme TOML and push to AdwStyleManager + all sub-widgets."""
        try:
            theme = load_theme(theme_id)
        except Exception:
            return
        self._active_theme = theme

        # Drive AdwStyleManager so the ENTIRE window (header, menus, tree, etc.)
        # switches light/dark — this is the idiomatic Libadwaita approach (§20.5).
        style_manager = Adw.StyleManager.get_default()
        if theme.kind in ("dark", "high-contrast-dark"):
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else:
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)

        # Inject CSS custom-property tokens for our own widgets (preview, etc.)
        css = generate_gtk_css(theme)
        self._theme_css_provider.load_from_string(css)

        # GtkSourceView style scheme (§20.9)
        if hasattr(self, "editor"):
            self.editor.apply_source_scheme(theme.source_scheme)
            self.editor.set_theme_css(css, theme_id=theme_id)

        # VTE terminal colors from ansi palette (§16.5, §20.2)
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

    def _on_window_active_changed(
        self, window: Adw.ApplicationWindow, _pspec: object
    ) -> None:
        if not window.is_active():
            self.editor._save()

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

        # Ctrl+P: Palette (files) (§17.2)
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>p"),
                action=Gtk.CallbackAction.new(self._shortcut_open_palette),
            )
        )

        # Ctrl+Shift+P: Palette (commands) (§17.2)
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control><Shift>p"),
                action=Gtk.CallbackAction.new(self._shortcut_open_palette_commands),
            )
        )

        # F1: Palette (help) (§17.2)
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("F1"),
                action=Gtk.CallbackAction.new(self._shortcut_open_palette_help),
            )
        )

        # Ctrl+B: Toggle Tree
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>b"),
                action=Gtk.CallbackAction.new(self._shortcut_toggle_tree),
            )
        )

        # Ctrl+`: Toggle Terminal
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>grave"),
                action=Gtk.CallbackAction.new(self._shortcut_toggle_terminal),
            )
        )

        # Ctrl+1: Focus Tree
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>1"),
                action=Gtk.CallbackAction.new(
                    lambda *_: self.tree_pane.grab_focus() or True
                ),
            )
        )

        # Ctrl+2: Focus Editor
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>2"),
                action=Gtk.CallbackAction.new(
                    lambda *_: self.editor.view.grab_focus() or True
                ),
            )
        )

        # Ctrl+3: Focus Terminal
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>3"),
                action=Gtk.CallbackAction.new(
                    lambda *_: self.terminal_placeholder.widget.grab_focus() or True
                ),
            )
        )

        # Ctrl+Tab: Cycle focus (§18.2)
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>Tab"),
                action=Gtk.CallbackAction.new(self._shortcut_cycle_focus),
            )
        )

        # Ctrl+S: Explicit save (§10.3, §10.4)
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>s"),
                action=Gtk.CallbackAction.new(self._shortcut_save),
            )
        )

        # Ctrl+E: Toggle edit/read mode (§10.2, §18.2)
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>e"),
                action=Gtk.CallbackAction.new(self._shortcut_toggle_mode),
            )
        )

        # Ctrl+Shift+Z: Toggle Zen mode (§7.5)
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control><Shift>z"),
                action=Gtk.CallbackAction.new(self._shortcut_toggle_zen),
            )
        )

        # Ctrl+Shift+Y: Send current file path to terminal stdin (§16.9)
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control><Shift>y"),
                action=Gtk.CallbackAction.new(self._shortcut_send_file_to_terminal),
            )
        )

        # Ctrl+Shift+U: Send editor selection to terminal stdin (§16.9)
        controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control><Shift>u"),
                action=Gtk.CallbackAction.new(
                    self._shortcut_send_selection_to_terminal
                ),
            )
        )

        # Zoom shortcuts (§19)
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

    def _shortcut_zoom(self, delta: float, reset: bool = False) -> bool:
        current = self.main_window.get_focus()
        if not current:
            return False

        if current == self.tree_pane or current.is_ancestor(self.tree_pane):
            self._command_router.dispatch(Zoom("tree", delta, reset))
        elif current == self.editor.widget or current.is_ancestor(self.editor.widget):
            # Decide between editor and preview based on read_mode
            if self._state.editor.read_mode:
                self._command_router.dispatch(Zoom("preview", delta, reset))
            else:
                self._command_router.dispatch(Zoom("editor", delta, reset))
        elif current == self.terminal_placeholder.widget or current.is_ancestor(
            self.terminal_placeholder.widget
        ):
            self._command_router.dispatch(Zoom("terminal", delta, reset))
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
        self.editor._save()
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
        targets: List[Gtk.Widget] = [
            self.tree_pane,
            self.editor.view,
            self.terminal_placeholder.widget,
        ]

        current = self.main_window.get_focus()

        start_idx = 0
        if current:
            for i in range(len(targets)):
                t = targets[i]
                if current == t or current.is_ancestor(t):
                    start_idx = (i + 1) % len(targets)
                    break

        for j in range(len(targets)):
            idx = (start_idx + j) % len(targets)
            target = targets[idx]
            if target.get_visible():
                target.grab_focus()
                return True

        return True

        for j in range(len(targets)):
            idx = (start_idx + j) % len(targets)
            target = targets[idx]
            if target.get_visible():
                target.grab_focus()
                return True

        return True
