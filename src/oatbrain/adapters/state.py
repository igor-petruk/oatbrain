import tomllib
import tomli_w
from pathlib import Path
from oatbrain.core.state import AppState, EditorState
from oatbrain.core.ports.filestore import VaultPath


class TomlStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def save(self, state: AppState) -> None:
        data = {
            "general": {
                "last_vault": str(state.vault_root),
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
                **(
                    {"open_file": str(state.editor.open_file)}
                    if state.editor.open_file
                    else {}
                ),
                "read_mode": state.editor.read_mode,
                "split_mode": state.editor.split_mode,
                "zoom": state.editor.zoom,
                "preview_zoom": state.editor.preview_zoom,
            },
            "theme": {
                "theme_id": state.theme_id,
            },
            "mermaid": {
                "dismissed": state.mermaid_dismissed,
            },
        }
        with open(self.path, "wb") as f:
            tomli_w.dump(data, f)

    def load(self) -> AppState:
        if not self.path.exists():
            # State file missing: bootstrap.py will catch this
            # and provide a default AppState with the correct vault root.
            raise FileNotFoundError(f"State file not found: {self.path}")

        with open(self.path, "rb") as f:
            data = tomllib.load(f)

        general = data.get("general", {})
        panes = data.get("panes", {})
        editor_data = data.get("editor", {})
        theme_data = data.get("theme", {})
        mermaid_data = data.get("mermaid", {})

        open_file_str = editor_data.get("open_file")

        editor = EditorState(
            open_file=VaultPath.from_str(open_file_str) if open_file_str else None,
            read_mode=editor_data.get("read_mode", False),
            split_mode=editor_data.get("split_mode", False),
            zoom=editor_data.get("zoom", 1.0),
            preview_zoom=editor_data.get("preview_zoom", 1.0),
        )

        return AppState(
            vault_root=Path(general.get("last_vault", ".")),
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
