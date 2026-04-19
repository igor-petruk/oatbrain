import unittest.mock as mock
from pathlib import Path
from gi.repository import GLib
from oatbrain.core.bus import EventBus, CommandRouter
from oatbrain.core.state.app_state import AppState
from oatbrain.core.ports.filestore import FileStore
from oatbrain.core.ports.state import StateStore
from oatbrain.core.ports.env import Env
from oatbrain.core.ports.config import AppConfig
from oatbrain.core.events.mermaid import MermaidFetchResult
from oatbrain.ui.window import AdwAppShell


def test_mermaid_fetch_failure_emits_event() -> None:
    """Verifies that a network failure during Mermaid fetch emits a failure event."""
    event_bus = EventBus()
    command_router = CommandRouter()
    state = AppState(vault_root=Path("/tmp"))
    filestore = mock.MagicMock(spec=FileStore)
    state_store = mock.MagicMock(spec=StateStore)
    env = mock.MagicMock(spec=Env)
    env.get_xdg_cache_home.return_value = Path("/tmp/cache")
    env.get_xdg_config_home.return_value = Path("/tmp/config")
    env.get_xdg_state_home.return_value = Path("/tmp/state")
    env.get_xdg_data_home.return_value = Path("/tmp/data")

    # Mock the cache file to not exist
    with mock.patch("pathlib.Path.exists", return_value=False):
        # Mock urllib.request.urlopen to fail
        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = Exception("Network Down")

            received_events: list[MermaidFetchResult] = []
            event_bus.subscribe(MermaidFetchResult, received_events.append)

            app = AdwAppShell(
                event_bus=event_bus,
                command_router=command_router,
                initial_state=state,
                filestore=filestore,
                state_store=state_store,
                config=mock.MagicMock(spec=AppConfig),
                env=env,
                application_id="org.oatbrain.TestMermaid",
            )

            # Trigger the fetch
            app._fetch_mermaid_library()

            # Process GLib idle loop to run the lambda
            ctx = GLib.MainContext.default()
            while ctx.pending():
                ctx.iteration(False)

            assert len(received_events) == 1
            assert not received_events[0].success
            assert received_events[0].error == "Network Down"
