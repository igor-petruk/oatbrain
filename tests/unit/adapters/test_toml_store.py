import pytest
from pathlib import Path
from oatbrain.adapters.state.toml_store import TomlStateStore
from oatbrain.core.state.app_state import AppState, EditorState
from oatbrain.core.ports.filestore import VaultPath


def test_toml_store_roundtrip(tmp_path: Path) -> None:
    state_file = tmp_path / "state.toml"
    store = TomlStateStore(state_file)

    editor = EditorState(
        open_file=VaultPath.from_str("note.md"),
        read_mode=True,
        mru=["a.md", "b.md"],
        zoom=1.5,
        preview_zoom=0.9,
    )
    state = AppState(
        vault_root=Path("/vault"),
        window_width=1000,
        window_height=600,
        window_fullscreen=True,
        tree_width=200,
        tree_zoom=1.2,
        terminal_width=300,
        terminal_zoom=0.8,
        editor=editor,
        theme_name="Dark",
    )

    store.save(state)
    assert state_file.exists()

    loaded = store.load()
    assert loaded.vault_root == Path("/vault")
    assert loaded.window_width == 1000
    assert loaded.window_height == 600
    assert loaded.window_fullscreen is True
    assert loaded.tree_width == 200
    assert loaded.tree_zoom == 1.2
    assert loaded.terminal_width == 300
    assert loaded.terminal_zoom == 0.8
    assert loaded.editor.open_file == VaultPath.from_str("note.md")
    assert loaded.editor.read_mode is True
    assert loaded.editor.mru == ["a.md", "b.md"]
    assert loaded.editor.zoom == 1.5
    assert loaded.editor.preview_zoom == 0.9


def test_toml_store_load_missing_file(tmp_path: Path) -> None:
    state_file = tmp_path / "missing.toml"
    store = TomlStateStore(state_file)
    with pytest.raises(FileNotFoundError):
        store.load()


def test_toml_store_roundtrip_no_file(tmp_path: Path) -> None:
    state_file = tmp_path / "state_no_file.toml"
    store = TomlStateStore(state_file)

    state = AppState(vault_root=Path("/vault"), editor=EditorState(open_file=None))

    store.save(state)
    loaded = store.load()
    assert loaded.editor.open_file is None
