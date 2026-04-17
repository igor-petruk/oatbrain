from pathlib import Path
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gio  # noqa: E402

from oatbrain.ui.window import AdwAppShell  # noqa: E402
from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.state.app_state import AppState  # noqa: E402

def build_app(argv: list[str]) -> Adw.Application:
    # Basic initialization
    # In a real app, this would load the state from disk
    initial_state = AppState(vault_root=Path.home()) 
    
    event_bus = EventBus()
    command_router = CommandRouter()
    
    app = AdwAppShell(
        application_id="app.oatbrain.App", 
        flags=Gio.ApplicationFlags.FLAGS_NONE,
        event_bus=event_bus,
        command_router=command_router,
        initial_state=initial_state
    )
    return app
