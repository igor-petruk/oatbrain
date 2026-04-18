import gi
import os
from pathlib import Path

gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, Gdk, Vte, GLib, Pango, PangoCairo, Gio  # noqa: E402

# Same priority list as the editor CSS font-family stack (§19).
# Pick the first family actually installed on this system.
_PREFERRED_FONTS = [
    "Cousine",
    "JetBrains Mono",
    "Fira Code",
    "DejaVu Sans Mono",
]
_FALLBACK_FONT = "Monospace"


def _resolve_terminal_font(size_pt: int = 12) -> Pango.FontDescription:
    installed = {
        f.get_name()
        for f in PangoCairo.FontMap.get_default().list_families()
    }
    family = next((f for f in _PREFERRED_FONTS if f in installed), _FALLBACK_FONT)
    return Pango.FontDescription.from_string(f"{family} {size_pt}")


class Terminal:
    """VTE-based terminal pane (SPEC §16)."""

    def __init__(self, vault_root: Path) -> None:
        self._vault_root = vault_root

        self._vte = Vte.Terminal()
        self._vte.set_hexpand(True)
        self._vte.set_vexpand(True)
        self._vte.set_scrollback_lines(10000)

        # §16.5 Font: first available from the editor's preferred font list (§19)
        self._vte.set_font(_resolve_terminal_font())

        # §16.6 Hyperlinks: OSC 8 (app-emitted) + plain URL regex detection
        self._vte.set_allow_hyperlink(True)
        url_re = Vte.Regex.new_for_match(
            r"https?://[^\s\]>\"')\}]+", -1, 0
        )
        self._url_tag = self._vte.match_add_regex(url_re, 0)
        self._vte.match_set_cursor_name(self._url_tag, "pointer")

        # Ctrl+click opens URLs (plain click is reserved for text selection)
        click = Gtk.GestureClick.new()
        click.set_button(1)
        click.connect("released", self._on_click)
        self._vte.add_controller(click)

        self.widget = Gtk.ScrolledWindow()
        self.widget.set_child(self._vte)
        self.widget.set_hexpand(True)
        self.widget.set_vexpand(True)

        self._spawn()

    # ------------------------------------------------------------------
    # Public API for window shortcuts (§16.9)
    # ------------------------------------------------------------------

    def send_text(self, text: str) -> None:
        """Write text directly to the terminal's stdin (§16.9)."""
        self._vte.feed_child(list(text.encode()))

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
        merged.update({
            "OATBRAIN_VAULT": str(self._vault_root),
            "TERM": "xterm-256color",
        })
        return [f"{k}={v}" for k, v in merged.items()]

    def _spawn(self) -> None:
        shell = os.environ.get("SHELL", "/bin/sh")
        self._vte.spawn_async(
            pty_flags=Vte.PtyFlags.DEFAULT,
            working_directory=str(self._vault_root),
            argv=[shell],
            envv=self._build_env(),
            spawn_flags=GLib.SpawnFlags.DEFAULT,
            child_setup=None,
            timeout=-1,
            cancellable=None,
            callback=lambda _t, _pid, _err, _ud: None,
            user_data=None,
        )
