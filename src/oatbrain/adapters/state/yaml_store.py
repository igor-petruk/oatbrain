from pathlib import Path
import yaml
from oatbrain.core.state.app_state import AppState, EditorState
from oatbrain.core.ports.filestore import VaultPath

class YamlStateStore:
    """Persistent storage for AppState using YAML (compatible with SPEC §27)."""

    def __init__(self, path: Path):
        self._path = path

    def save(self, state: AppState) -> None:
        data = {
            "vault_root": str(state.vault_root),
            "editor": {
                "open_file": str(state.editor.open_file) if state.editor.open_file else None,
                "is_dirty": state.editor.is_dirty,
                "read_mode": state.editor.read_mode,
            },
            "status_message": state.status_message,
        }
        with open(self._path, "w") as f:
            yaml.safe_dump(data, f)

    def load(self) -> AppState:
        if not self._path.exists():
            raise FileNotFoundError(f"State file not found: {self._path}")
        
        with open(self._path, "r") as f:
            data = yaml.safe_load(f)
            
        editor_data = data.get("editor", {})
        open_file_str = editor_data.get("open_file")
        
        editor = EditorState(
            open_file=VaultPath.from_str(open_file_str) if open_file_str else None,
            is_dirty=editor_data.get("is_dirty", False),
            read_mode=editor_data.get("read_mode", False),
        )
        
        return AppState(
            vault_root=Path(data["vault_root"]),
            editor=editor,
            status_message=data.get("status_message", "Ready"),
        )
