from pathlib import Path
from oatbrain.core.state.app_state import AppState, EditorState
from oatbrain.core.ports.filestore import VaultPath
from oatbrain.adapters.state.yaml_store import YamlStateStore

def test_yaml_store_roundtrip(tmp_path: Path):
    state_file = tmp_path / "state.yaml"
    store = YamlStateStore(state_file)
    
    original_state = AppState(
        vault_root=Path("/my/vault"),
        editor=EditorState(
            open_file=VaultPath.from_str("note.md"),
            is_dirty=True,
            read_mode=True
        ),
        status_message="Testing..."
    )
    
    store.save(original_state)
    loaded_state = store.load()
    
    # Transient fields should be reset
    assert not loaded_state.editor.is_dirty
    assert loaded_state.status_message == "Ready"
    
    # Persistent fields should match
    assert loaded_state.vault_root == original_state.vault_root
    assert loaded_state.editor.open_file == original_state.editor.open_file
    assert loaded_state.editor.read_mode == original_state.editor.read_mode

def test_yaml_store_load_missing_file(tmp_path: Path):
    store = YamlStateStore(tmp_path / "missing.yaml")
    import pytest
    with pytest.raises(FileNotFoundError):
        store.load()
