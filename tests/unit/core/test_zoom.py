from pathlib import Path
from oatbrain.core.state.app_state import AppState
from oatbrain.core.commands.ui import Zoom
from oatbrain.ui.window import AdwAppShell
from oatbrain.core.bus import EventBus, CommandRouter
from unittest.mock import MagicMock


def test_zoom_command_updates_state():
    """Verify that Zoom commands correctly update the AppState."""
    initial_state = AppState(vault_root=Path("/vault"))
    event_bus = EventBus()
    command_router = CommandRouter()
    
    # Mock dependencies
    filestore = MagicMock()
    state_store = MagicMock()
    config = MagicMock()
    env = MagicMock()

    app = AdwAppShell(
        event_bus=event_bus,
        command_router=command_router,
        initial_state=initial_state,
        filestore=filestore,
        state_store=state_store,
        config=config,
        env=env,
    )

    # 1. Zoom Tree
    command_router.dispatch(Zoom(component="tree", delta=0.1))
    assert app._state.tree_zoom == 1.1

    # 2. Zoom Terminal
    command_router.dispatch(Zoom(component="terminal", delta=-0.2))
    assert app._state.terminal_zoom == 0.8

    # 3. Zoom Editor
    command_router.dispatch(Zoom(component="editor", delta=0.5))
    assert app._state.editor.zoom == 1.5

    # 4. Zoom Preview
    command_router.dispatch(Zoom(component="preview", delta=-0.1))
    assert app._state.editor.preview_zoom == 0.9

    # 5. Reset Zoom
    command_router.dispatch(Zoom(component="tree", reset=True))
    assert app._state.tree_zoom == 1.0

    # 6. Clamping
    command_router.dispatch(Zoom(component="tree", delta=10.0))
    assert app._state.tree_zoom == 3.0
    
    command_router.dispatch(Zoom(component="tree", delta=-10.0))
    assert app._state.tree_zoom == 0.5
