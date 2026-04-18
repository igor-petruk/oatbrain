from pathlib import Path
from dataclasses import replace
import os
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gio  # noqa: E402

from oatbrain.ui.window import AdwAppShell  # noqa: E402
from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.state.app_state import AppState  # noqa: E402
from oatbrain.adapters.filestore.local import LocalFileStore  # noqa: E402
from oatbrain.adapters.state.toml_store import TomlStateStore  # noqa: E402


def get_state_path() -> Path:
    state_home = os.environ.get("XDG_STATE_HOME")
    if state_home:
        base = Path(state_home)
    else:
        base = Path.home() / ".local" / "state"
    return base / "oatbrain" / "state.toml"


def build_app(argv: list[str]) -> Adw.Application:
    state_path = get_state_path()
    state_store = TomlStateStore(state_path)

    try:
        initial_state = state_store.load()
    except Exception:
        # Fallback if no state file exists
        initial_state = AppState(vault_root=Path.cwd())

    # Override vault root if provided via CLI
    if len(argv) > 1:
        provided_path = Path(argv[1]).resolve()
        if provided_path.is_dir():
            initial_state = replace(initial_state, vault_root=provided_path)

    event_bus = EventBus()
    command_router = CommandRouter()
    filestore = LocalFileStore(initial_state.vault_root)

    app = AdwAppShell(
        application_id="app.oatbrain.App",
        flags=Gio.ApplicationFlags.FLAGS_NONE | Gio.ApplicationFlags.NON_UNIQUE,
        event_bus=event_bus,
        command_router=command_router,
        initial_state=initial_state,
        filestore=filestore,
        state_store=state_store,
    )
    return app
