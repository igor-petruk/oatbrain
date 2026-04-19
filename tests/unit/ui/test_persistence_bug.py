from unittest.mock import MagicMock
from dataclasses import replace
from oatbrain.ui.editor import Editor
from oatbrain.core.events.state import StateUpdated
from oatbrain.core.state.app_state import AppState
from pathlib import Path
from oatbrain.core.ports.filestore import VaultPath


def test_editor_mode_recovers_to_preview_when_returning_to_markdown() -> None:
    # Setup
    filestore = MagicMock()
    event_bus = MagicMock()
    command_router = MagicMock()
    renderer = MagicMock()
    env = MagicMock()

    editor = Editor(filestore, event_bus, command_router, env, renderer)
    state = AppState(vault_root=Path("/tmp"))

    # 1. Open MD file in Preview mode
    md_path = VaultPath("test.md")
    state = replace(
        state, editor=replace(state.editor, open_file=md_path, read_mode=True)
    )
    editor._update_ui(StateUpdated(state))
    assert editor._read_mode is True

    # 2. Click on TOML file (switch to non-MD file)
    toml_path = VaultPath("config.toml")
    state = replace(
        state,
        editor=replace(state.editor, open_file=toml_path, read_mode=True),
    )
    editor._update_ui(StateUpdated(state))
    # Editor should have forced read_mode=False internally
    assert editor._read_mode is False

    # 3. Switch back to MD file (should recover to Preview mode)
    # The application state still thinks read_mode is True because
    # we didn't update it in step 2 to match the forced state.
    state = replace(
        state,
        editor=replace(state.editor, open_file=md_path, read_mode=True),
    )
    editor._update_ui(StateUpdated(state))

    # Assert recovery
    assert editor._read_mode is True
