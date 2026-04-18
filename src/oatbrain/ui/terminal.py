import gi
import os
from pathlib import Path
from typing import Optional

gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")
from gi.repository import Gtk, Vte, GLib  # noqa: E402

from oatbrain.core.bus import EventBus  # noqa: E402
from oatbrain.core.events.state import StateUpdated  # noqa: E402
from oatbrain.core.ports.filestore import VaultPath  # noqa: E402


class Terminal:
    """VTE-based terminal pane (SPEC §16)."""

    def __init__(self, vault_root: Path, event_bus: EventBus) -> None:
        self._vault_root = vault_root
        self._current_file: Optional[VaultPath] = None

        self._vte = Vte.Terminal()
        self._vte.set_hexpand(True)
        self._vte.set_vexpand(True)
        self._vte.set_scrollback_lines(10000)

        self.widget = Gtk.ScrolledWindow()
        self.widget.set_child(self._vte)
        self.widget.set_hexpand(True)
        self.widget.set_vexpand(True)

        event_bus.subscribe(StateUpdated, self._on_state_updated)

        self._spawn()

    def _build_env(self) -> list[str]:
        env = list(os.environ.items())
        overrides = {
            "OATBRAIN_VAULT": str(self._vault_root),
            "OATBRAIN_CURRENT_FILE": (
                str(self._vault_root / str(self._current_file))
                if self._current_file else ""
            ),
            "OATBRAIN_SELECTION": "",
            "TERM": "xterm-256color",
        }
        merged = {k: v for k, v in env}
        merged.update(overrides)
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
            self._update_env_var(
                "OATBRAIN_CURRENT_FILE",
                str(self._vault_root / str(new_file)) if new_file else "",
            )

    def _update_env_var(self, name: str, value: str) -> None:
        pty = self._vte.get_pty()
        if pty is None:
            return
        fd = pty.get_fd()
        if fd < 0:
            return
        # Write variable update via shell sidecar file (SPEC §16.3)
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
