import tomllib
import tomli_w
from pathlib import Path
from oatbrain.core.state.app_state import AppState, EditorState
from oatbrain.core.ports.filestore import VaultPath

class TomlStateStore:
    """Persistent storage for AppState using TOML (SPEC §27)."""

    def __init__(self, path: Path):
        self._path = path

    def save(self, state: AppState) -> None:
        data = {
            "general": {
                "last_vault": str(state.vault_root),
            },
            "window": {
                "width": state.window_width,
                "height": state.window_height,
                "fullscreen": state.window_fullscreen,
            },
            "panes": {
                "tree_width": state.tree_width,
                "tree_visible": state.tree_visible,
                "terminal_width": state.terminal_width,
                "terminal_visible": state.terminal_visible,
            },
            "editor": {
                "read_mode": state.editor.read_mode,
                "mru": state.editor.mru,
            },
            "theme": {
                "theme_id": state.theme_id,
            },
        }
        if state.editor.open_file:
            data["editor"]["open_file"] = str(state.editor.open_file) # type: ignore
        
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "wb") as f:
            tomli_w.dump(data, f)

    def load(self) -> AppState:
        if not self._path.exists():
            raise FileNotFoundError(f"State file not found: {self._path}")
        
        with open(self._path, "rb") as f:
            data = tomllib.load(f)
            
        general = data.get("general", {})
        window = data.get("window", {})
        panes = data.get("panes", {})
        editor_data = data.get("editor", {})
        theme_data = data.get("theme", {})
        
        open_file_str = editor_data.get("open_file")
        
        editor = EditorState(
            open_file=VaultPath.from_str(open_file_str) if open_file_str else None,
            read_mode=editor_data.get("read_mode", False),
            mru=editor_data.get("mru", []),
        )
        
        return AppState(
            vault_root=Path(general.get("last_vault", ".")),
            window_width=window.get("width", 1200),
            window_height=window.get("height", 800),
            window_fullscreen=window.get("fullscreen", False),
            tree_width=panes.get("tree_width", 180),
            tree_visible=panes.get("tree_visible", True),
            terminal_width=panes.get("terminal_width", 360),
            terminal_visible=panes.get("terminal_visible", True),
            editor=editor,
            theme_id=theme_data.get("theme_id", "solarized-light"),
        )
