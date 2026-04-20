import gi
import os
import time
import signal
import base64
from pathlib import Path
from typing import Optional

gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, Gdk, Vte, GLib, Pango, PangoCairo, Gio  # noqa: E402

from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.events.state import StateUpdated  # noqa: E402
from oatbrain.core.commands.ui import Zoom  # noqa: E402

# Same priority list as the editor CSS font-family stack (§19).
# Pick the first family actually installed on this system.
_PREFERRED_FONTS = [
    "Cousine",
    "JetBrains Mono",
    "Fira Code",
    "DejaVu Sans Mono",
]
_FALLBACK_FONT = "Monospace"


def _resolve_terminal_font(size_pt: int = 13) -> Pango.FontDescription:
    installed = {f.get_name() for f in PangoCairo.FontMap.get_default().list_families()}
    family = next((f for f in _PREFERRED_FONTS if f in installed), _FALLBACK_FONT)
    return Pango.FontDescription.from_string(f"{family} {size_pt}")


class Terminal:
    """VTE-based terminal pane (SPEC §16)."""

    def __init__(
        self,
        vault_root: Path,
        event_bus: Optional[EventBus] = None,
        command_router: Optional[CommandRouter] = None,
    ) -> None:
        self._vault_root = vault_root
        self._event_bus = event_bus
        self._command_router = command_router
        self._current_zoom = 1.0
        self._child_pid: Optional[int] = None
        self._last_spawn_time = 0.0

        self._vte = Vte.Terminal()
        self._vte.set_hexpand(True)
        self._vte.set_vexpand(True)
        self._vte.set_scrollback_lines(10000)

        _vte_padding = Gtk.CssProvider()
        _vte_padding.load_from_string("vte-terminal { padding: 6px 10px; }")
        self._vte.get_style_context().add_provider(
            _vte_padding, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # §16.5 Font: first available from the editor's preferred font list (§19)
        self._vte.set_font(_resolve_terminal_font())

        # §16.12 Lifecycle: Auto-restart on exit
        self._vte.connect("child-exited", self._on_child_exited)

        # §16.4 Remote Clipboard (OSC 52)
        # VTE 0.74+ handles OSC 52 by updating the 'clipboard' termprop.
        # It requires the 'copy-clipboard' action to be enabled.
        self._vte.action_set_enabled("copy-clipboard", True)
        self._vte.connect("termprop-changed", self._on_termprop_changed)

        # Ctrl+MouseScroll zooming (§19)
        scroll_ctrl = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL
        )
        scroll_ctrl.connect("scroll", self._on_scroll)
        self._vte.add_controller(scroll_ctrl)

        # §16.6 Hyperlinks: OSC 8 (app-emitted) + plain URL regex detection
        self._vte.set_allow_hyperlink(True)
        # PCRE2_MULTILINE is required by VTE's match_add_regex
        _PCRE2_MULTILINE = 0x00000400
        url_re = Vte.Regex.new_for_match(
            r"https?://[^\s\]>\"')\}]+", -1, _PCRE2_MULTILINE
        )
        self._url_tag = self._vte.match_add_regex(url_re, 0)
        self._vte.match_set_cursor_name(self._url_tag, "pointer")

        # Ctrl+click opens URLs (plain click is reserved for text selection)
        click = Gtk.GestureClick.new()
        click.set_button(1)
        click.connect("released", self._on_click)
        self._vte.add_controller(click)

        self._scrolled = Gtk.ScrolledWindow()
        self._scrolled.set_child(self._vte)
        self._scrolled.set_hexpand(True)
        self._scrolled.set_vexpand(True)

        self.widget = self._scrolled

        if self._event_bus:
            self._event_bus.subscribe(StateUpdated, self._on_state_updated)

        self._spawn()

    def restart(self) -> None:
        """Manually kill current shell, clear buffer and spawn a new one (§16.12)."""
        if self._child_pid:
            try:
                os.kill(self._child_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        # Clear the buffer and reset terminal state
        self._vte.reset(True, True)
        self._spawn()

    def _on_child_exited(self, _vte: Vte.Terminal, _status: int) -> None:
        """Restart shell after a delay when it exits (§16.12)."""
        # Clear the buffer on auto-exit as well
        self._vte.reset(True, True)

        now = time.time()
        # Flood protection: if crashed immediately, wait longer
        if now - self._last_spawn_time < 2.0:
            delay = 5000  # 5 seconds
        else:
            delay = 1000  # 1 second

        GLib.timeout_add(delay, self._spawn_if_needed)

    def _on_termprop_changed(self, vte: Vte.Terminal, prop_name: str) -> None:
        """Handle OSC 52 remote clipboard updates (§16.4)."""
        if prop_name == "clipboard":
            # The 'clipboard' termprop contains base64 encoded data from OSC 52.
            # Format is typically 'c;<base64>' or 'p;<base64>'.
            payload = vte.get_termprop_string(prop_name)
            if not payload:
                return

            try:
                display = Gdk.Display.get_default()
                if not display:
                    return

                if payload.startswith("c;"):
                    b64_data = payload[2:]
                    clipboard = display.get_clipboard()
                elif payload.startswith("p;"):
                    b64_data = payload[2:]
                    clipboard = display.get_primary_clipboard()
                else:
                    # Fallback to default clipboard
                    b64_data = payload
                    clipboard = display.get_clipboard()

                decoded = base64.b64decode(b64_data).decode("utf-8")
                clipboard.set_text(decoded)
            except Exception as e:
                # Log error but don't crash
                print(f"OSC 52 clipboard error: {e}")

    def _spawn_if_needed(self) -> bool:
        # Check if we already restarted manually or via another signal
        # VTE clears child-pid when it exits.
        self._spawn()
        return False

    def _on_state_updated(self, event: StateUpdated) -> None:
        GLib.idle_add(self._update_zoom, event.state.terminal_zoom)

    def _update_zoom(self, zoom: float) -> bool:
        if zoom != self._current_zoom:
            self._current_zoom = zoom
            base_size = 13
            new_size = int(base_size * zoom)
            self._vte.set_font(_resolve_terminal_font(new_size))
        return False

    def _on_scroll(self, ctrl: Gtk.EventControllerScroll, dx: float, dy: float) -> bool:
        """Handle Ctrl+MouseScroll to zoom terminal (§19)."""
        event = ctrl.get_current_event()
        if not event:
            return False
        modifiers = event.get_modifier_state()
        if modifiers & Gdk.ModifierType.CONTROL_MASK:
            if self._command_router:
                # dy is positive for scroll down, negative for scroll up
                delta = -0.1 if dy > 0 else 0.1
                self._command_router.dispatch(Zoom("terminal", delta))
                return True
        return False

    # ------------------------------------------------------------------
    # Public API for window shortcuts (§16.9)
    # ------------------------------------------------------------------

    def _feed(self, data: str) -> None:
        # Use explicit byte list as per GObject Introspection guidance for feed_child
        encoded = list(data.encode("utf-8"))
        self._vte.feed_child(encoded)

    def send_text(self, text: str) -> None:
        """Write text directly to the terminal's stdin (§16.9)."""
        self._feed(text)

    def send_text_throttled(self, text: str, delay_ms: int = 60) -> None:
        """Write text to the terminal, batching characters but throttling Enter keys.

        Sends all non-return characters immediately, but waits for delay_ms before
        each '\r' to bypass fast-paste detection in CLIs (e.g. Gemini CLI's 30ms limit).
        """
        self.grab_focus()
        chars = list(text)

        def _send_next() -> None:
            if not chars:
                return

            # Batch and send all leading non-return characters immediately
            batch = ""
            while chars and chars[0] != "\r":
                batch += chars.pop(0)
            if batch:
                self._feed(batch)

            # If the next character is a return, wait then send it
            if chars and chars[0] == "\r":
                chars.pop(0)
                GLib.timeout_add(delay_ms, _trigger_return)

        def _trigger_return() -> bool:
            self._feed("\r")
            _send_next()
            return False

        _send_next()

    def grab_focus(self) -> bool:
        """Focus the terminal widget."""
        return bool(self._vte.grab_focus())

    def apply_theme(self, theme: object) -> None:
        """Apply VTE colors from theme ansi palette (SPEC §16.5, §20.2)."""
        from oatbrain.core.theme.models import ThemeData

        if not isinstance(theme, ThemeData):
            return
        fg_hex = theme.ansi.get("fg", "#ffffff")
        bg_hex = theme.ansi.get("bg", "#000000")
        fg = Gdk.RGBA()
        bg = Gdk.RGBA()
        fg.parse(fg_hex)
        bg.parse(bg_hex)
        palette: list[Gdk.RGBA] = []
        for i in range(16):
            c = Gdk.RGBA()
            c.parse(theme.ansi.get(str(i), "#000000"))
            palette.append(c)
        self._vte.set_colors(fg, bg, palette)

    # ------------------------------------------------------------------
    # Hyperlinks (§16.6)
    # ------------------------------------------------------------------

    def _on_click(
        self,
        gesture: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> None:
        # Only open URLs on Ctrl+click to avoid conflicting with text selection
        state = gesture.get_current_event_state()
        if not (state & Gdk.ModifierType.CONTROL_MASK):
            return
        # OSC 8 hyperlink (app-emitted, e.g. from ls --hyperlink)
        uri = self._vte.check_hyperlink_at(x, y)
        # Plain URL detected by regex
        if not uri:
            matched, _tag = self._vte.check_match_at(x, y)
            uri = matched
        if uri:
            try:
                Gio.AppInfo.launch_default_for_uri(uri, None)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Spawn
    # ------------------------------------------------------------------

    def _build_env(self) -> list[str]:
        merged = dict(os.environ)
        merged.update(
            {
                "OATBRAIN_VAULT": str(self._vault_root),
                "TERM": "xterm-256color",
            }
        )
        return [f"{k}={v}" for k, v in merged.items()]

    def _spawn(self) -> None:
        self._last_spawn_time = time.time()
        shell = os.environ.get("SHELL", "/bin/sh")

        def _on_spawned(
            _vte: Vte.Terminal,
            pid: int,
            error: Optional[GLib.Error],
            _user_data: object,
        ) -> None:
            if error:
                print(f"Terminal spawn error: {error}")
                return
            self._child_pid = pid

        self._vte.spawn_async(
            pty_flags=Vte.PtyFlags.DEFAULT,
            working_directory=str(self._vault_root),
            argv=[shell],
            envv=self._build_env(),
            spawn_flags=GLib.SpawnFlags.DEFAULT,
            child_setup=None,
            timeout=-1,
            cancellable=None,
            callback=_on_spawned,
            user_data=None,
        )
