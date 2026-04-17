from pathlib import Path
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gio  # noqa: E402

from oatbrain.ui.window import AdwAppShell  # noqa: E402
from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.state.app_state import AppState  # noqa: E402
from oatbrain.adapters.filestore.local import LocalFileStore  # noqa: E402

def build_app(argv: list[str]) -> Adw.Application:
    # Basic initialization
    # TODO: In a real app, this MUST be resolved from config or CLI args.
    # WARNING: Do not leave this hardcoded to home().
    initial_state = AppState(vault_root=Path.cwd()) 
    
    event_bus = EventBus()
    command_router = CommandRouter()
    filestore = LocalFileStore(initial_state.vault_root)
    
    app = AdwAppShell(
        application_id="app.oatbrain.App", 
        flags=Gio.ApplicationFlags.FLAGS_NONE,
        event_bus=event_bus,
        command_router=command_router,
        initial_state=initial_state,
        filestore=filestore,
    )
    return app
