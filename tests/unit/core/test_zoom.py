import pytest
from pathlib import Path
from oatbrain.core.state import AppState
from oatbrain.core.commands.ui import Zoom
from oatbrain.core.bus import EventBus, CommandRouter
from oatbrain.ui.window import AdwAppShell
from unittest.mock import MagicMock


def _focused_tab_zoom(app: AdwAppShell) -> float:
    tab = app._state.editor_area.groups[0].tabs[0]
    return tab.zoom


def _focused_tab_preview_zoom(app: AdwAppShell) -> float:
    tab = app._state.editor_area.groups[0].tabs[0]
    return tab.preview_zoom


def test_zoom_command_updates_state() -> None:
    event_bus = EventBus()
    command_router = CommandRouter()
    initial_state = AppState(vault_root=Path("/vault"))

    app = AdwAppShell(
        event_bus=event_bus,
        command_router=command_router,
        initial_state=initial_state,
        filestore=MagicMock(),
        state_store=MagicMock(),
        config=MagicMock(),
        env=MagicMock(),
    )

    # 1. Zoom Tree
    command_router.dispatch(Zoom(component="tree", delta=0.2))
    assert app._state.tree_zoom == pytest.approx(1.2)

    # 2. Zoom Terminal
    command_router.dispatch(Zoom(component="terminal", delta=-0.2))
    assert app._state.terminal_zoom == pytest.approx(0.8)

    # 3. Zoom Editor (focused tab zoom)
    command_router.dispatch(Zoom(component="editor", delta=0.5))
    assert _focused_tab_zoom(app) == pytest.approx(1.5)

    # 4. Zoom Preview (focused tab preview_zoom)
    command_router.dispatch(Zoom(component="preview", delta=-0.1))
    assert _focused_tab_preview_zoom(app) == pytest.approx(0.9)

    # 5. Reset Zoom (tree)
    command_router.dispatch(Zoom(component="tree", reset=True))
    assert app._state.tree_zoom == pytest.approx(1.0)
