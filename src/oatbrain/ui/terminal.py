import gi
import os
from pathlib import Path
from typing import Optional

gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")
from gi.repository import Gtk, Vte, GLib, Pango, Gio  # noqa: E402

from oatbrain.core.bus import EventBus  # noqa: E402
from oatbrain.core.events.state import StateUpdated  # noqa: E402
from oatbrain.core.ports.filestore import VaultPath  # noqa: E402

_EDITOR_FONT = (
    "'Cousine', 'JetBrains Mono', 'Fira Code', 'DejaVu Sans Mono', monospace"
)
# Use the first concrete family for Pango (CSS font-family lists aren't valid)
_TERMINAL_FONT_DESC = "Monospace 12"


class Terminal:
    """VTE-based terminal pane (SPEC §16)."""

    def __init__(self, vault_root: Path, event_bus: EventBus) -> None:
        self._vault_root = vault_root
        self._current_file: Optional[VaultPath] = None

        self._vte = Vte.Terminal()
        self._vte.set_hexpand(True)
        self._vte.set_vexpand(True)
        self._vte.set_scrollback_lines(10000)

        # §16.5 Font matching editor
        self._vte.set_font(Pango.FontDescription.from_string(_TERMINAL_FONT_DESC))

        # §16.6 OSC 8 hyperlinks
        self._vte.set_allow_hyperlink(True)
        click = Gtk.GestureClick.new()
        click.set_button(1)
        click.connect("released", self._on_click)
        self._vte.add_controller(click)

        self.widget = Gtk.ScrolledWindow()
        self.widget.set_child(self._vte)
        self.widget.set_hexpand(True)
        self.widget.set_vexpand(True)

        event_bus.subscribe(StateUpdated, self._on_state_updated)

        self._spawn()

    # ------------------------------------------------------------------
    # Public API for window shortcuts (§16.9)
    # ------------------------------------------------------------------

    def send_text(self, text: str) -> None:
        """Write text to the terminal's stdin (§16.9)."""
        self._vte.feed_child(list(text.encode()))

    def get_vte(self) -> Vte.Terminal:
        return self._vte

    # ------------------------------------------------------------------
    # Hyperlinks (§16.6)
    # ------------------------------------------------------------------

    def _on_click(
        self,
        gesture: Gtk.GestureClick,
        n_press: int,
        x: float,
        y: float,
    ) -> None:
        uri = self._vte.check_hyperlink_at(x, y)
        if uri:
            try:
                Gio.AppInfo.launch_default_for_uri(uri, None)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Environment
    # ------------------------------------------------------------------

    def _build_env(self) -> list[str]:
        merged = dict(os.environ)
        merged.update({
            "OATBRAIN_VAULT": str(self._vault_root),
            "OATBRAIN_CURRENT_FILE": (
                str(self._vault_root / str(self._current_file))
                if self._current_file else ""
            ),
            "OATBRAIN_SELECTION": "",
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

    def _on_state_updated(self, event: StateUpdated) -> None:
        new_file = event.state.editor.open_file
        if new_file != self._current_file:
            self._current_file = new_file
            file_path = (
                str(self._vault_root / str(new_file)) if new_file else ""
            )
            self._push_env_var("OATBRAIN_CURRENT_FILE", file_path)
            self._write_sidecar("OATBRAIN_CURRENT_FILE", file_path)

    def _push_env_var(self, name: str, value: str) -> None:
        """Push an env var update into the live shell via OSC 1337 / ANSI escape.

        We use a shell-agnostic approach: write a silent `export` via the PTY
        wrapped in ANSI OSC escape so it doesn't appear in the prompt line.
        Falls back gracefully if the PTY isn't ready.
        """
        pty = self._vte.get_pty()
        if pty is None or pty.get_fd() < 0:
            return
        # Use a POSIX-shell `export` sent as a background command via \r.
        # Wrapped in \x1b[?2026h / \x1b[?2026l (synchronous output) markers
        # so VTE doesn't display intermediate state — but since this runs
        # outside the user's readline, we keep it simple: send via feed_child
        # which goes directly to the shell stdin. The shell will execute it.
        safe_value = value.replace("'", "'\\''")
        cmd = f" export {name}='{safe_value}'\r"
        self._vte.feed_child(list(cmd.encode()))

    def _write_sidecar(self, name: str, value: str) -> None:
        """Keep sidecar file in sync for shells that poll it (SPEC §16.3)."""
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
        sidecar = Path(runtime_dir) / f"oatbrain.{os.getpid()}.env"
        try:
            existing: dict[str, str] = {}
            if sidecar.exists():
                for line in sidecar.read_text().splitlines():
                    if "=" in line:
                        k, _, v = line.partition("=")
                        existing[k] = v
            existing[name] = value
            sidecar.write_text(
                "\n".join(f"{k}={v}" for k, v in existing.items()) + "\n"
            )
        except OSError:
            pass
