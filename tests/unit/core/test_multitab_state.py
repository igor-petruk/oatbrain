import pytest
from pathlib import Path
from oatbrain.core.state.app_state import AppState
from oatbrain.core.ports.filestore import VaultPath
from oatbrain.core.bus import EventBus, CommandRouter
from oatbrain.ui.window import AdwAppShell
from oatbrain.core.commands import OpenFile
from oatbrain.core.commands.editor import CloseTab, SwitchTab, ToggleMode, ToggleSplit
from unittest.mock import MagicMock


@pytest.fixture
def initial_state() -> AppState:
    return AppState(vault_root=Path("/tmp/vault"))


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def router() -> CommandRouter:
    return CommandRouter()


def test_open_file_current_empty(initial_state, bus, router):
    shell = AdwAppShell(
        bus,
        router,
        initial_state,
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )
    path = VaultPath.from_str("note1.md")
    router.dispatch(OpenFile(path=path))

    assert len(shell._state.tabs) == 1
    assert shell._state.tabs[0].open_file == path
    assert shell._state.active_tab_index == 0


def test_open_file_replace_current(initial_state, bus, router):
    path1 = VaultPath.from_str("note1.md")
    state = initial_state
    shell = AdwAppShell(
        bus,
        router,
        state,
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )
    router.dispatch(OpenFile(path=path1))

    path2 = VaultPath.from_str("note2.md")
    router.dispatch(OpenFile(path=path2))

    assert len(shell._state.tabs) == 1
    assert shell._state.tabs[0].open_file == path2


def test_open_file_new_tab(initial_state, bus, router):
    path1 = VaultPath.from_str("note1.md")
    shell = AdwAppShell(
        bus,
        router,
        initial_state,
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )
    router.dispatch(OpenFile(path=path1))

    path2 = VaultPath.from_str("note2.md")
    router.dispatch(OpenFile(path=path2, new_tab=True))

    assert len(shell._state.tabs) == 2
    assert shell._state.tabs[0].open_file == path1
    assert shell._state.tabs[1].open_file == path2
    assert shell._state.active_tab_index == 1


def test_open_already_open_file(initial_state, bus, router):
    path1 = VaultPath.from_str("note1.md")
    path2 = VaultPath.from_str("note2.md")
    shell = AdwAppShell(
        bus,
        router,
        initial_state,
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )
    router.dispatch(OpenFile(path=path1))
    router.dispatch(OpenFile(path=path2, new_tab=True))
    router.dispatch(SwitchTab(index=0))

    assert shell._state.active_tab_index == 0

    # Open path2 again (it's in tab 1)
    router.dispatch(OpenFile(path=path2))

    assert len(shell._state.tabs) == 2
    assert shell._state.active_tab_index == 1


def test_close_tab(initial_state, bus, router):
    path1 = VaultPath.from_str("note1.md")
    path2 = VaultPath.from_str("note2.md")
    shell = AdwAppShell(
        bus,
        router,
        initial_state,
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )
    router.dispatch(OpenFile(path=path1))
    router.dispatch(OpenFile(path=path2, new_tab=True))

    assert len(shell._state.tabs) == 2

    router.dispatch(CloseTab(index=0))

    assert len(shell._state.tabs) == 1
    assert shell._state.tabs[0].open_file == path2
    assert shell._state.active_tab_index == 0


def test_close_last_tab(initial_state, bus, router):
    path1 = VaultPath.from_str("note1.md")
    shell = AdwAppShell(
        bus,
        router,
        initial_state,
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )
    router.dispatch(OpenFile(path=path1))

    router.dispatch(CloseTab(index=0))

    assert len(shell._state.tabs) == 1
    assert shell._state.tabs[0].open_file is None


def test_toggle_modes(initial_state, bus, router):
    path1 = VaultPath.from_str("note1.md")
    shell = AdwAppShell(
        bus,
        router,
        initial_state,
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )
    router.dispatch(OpenFile(path=path1))

    assert not shell._state.tabs[0].read_mode
    router.dispatch(ToggleMode())
    assert shell._state.tabs[0].read_mode

    assert not shell._state.tabs[0].split_mode
    router.dispatch(ToggleSplit())
    assert shell._state.tabs[0].split_mode
