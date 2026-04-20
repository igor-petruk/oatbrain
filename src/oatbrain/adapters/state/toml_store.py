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
                "tree_expanded": state.tree_expanded,
                "tree_zoom": state.tree_zoom,
                "terminal_width": state.terminal_width,
                "terminal_visible": state.terminal_visible,
                "terminal_zoom": state.terminal_zoom,
            },
            "editor": {
                "read_mode": state.editor.read_mode,
                "mru": state.editor.mru,
                "zoom": state.editor.zoom,
            },
            "preview": {
                "zoom": state.editor.preview_zoom,
            },
            "theme": {
                "theme_id": state.theme_id,
            },
            "mermaid": {
                "dismissed": state.mermaid_dismissed,
            },
        }
        if state.editor.open_file:
            data["editor"]["open_file"] = str(state.editor.open_file)  # type: ignore

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
        preview_data = data.get("preview", {})
        theme_data = data.get("theme", {})
        mermaid_data = data.get("mermaid", {})

        open_file_str = editor_data.get("open_file")

        editor = EditorState(
            open_file=VaultPath.from_str(open_file_str) if open_file_str else None,
            read_mode=editor_data.get("read_mode", False),
            mru=editor_data.get("mru", []),
            zoom=editor_data.get("zoom", 1.0),
            preview_zoom=preview_data.get("zoom", 1.0),
        )

        return AppState(
            vault_root=Path(general.get("last_vault", ".")),
            window_width=window.get("width", 1200),
            window_height=window.get("height", 800),
            window_fullscreen=window.get("fullscreen", False),
            tree_width=panes.get("tree_width", 180),
            tree_visible=panes.get("tree_visible", True),
            tree_expanded=panes.get("tree_expanded", []),
            tree_zoom=panes.get("tree_zoom", 1.0),
            terminal_width=panes.get("terminal_width", 360),
            terminal_visible=panes.get("terminal_visible", True),
            terminal_zoom=panes.get("terminal_zoom", 1.0),
            editor=editor,
            theme_id=theme_data.get("theme_id", "solarized-light"),
            mermaid_dismissed=mermaid_data.get("dismissed", False),
        )
