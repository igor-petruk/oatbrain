import tomllib
import tomli_w
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from oatbrain.core.state import AppState, EditorAreaState, GroupState, TabState
from oatbrain.core.ports.filestore import VaultPath

log = logging.getLogger(__name__)


class TomlStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def save(self, state: AppState) -> None:
        try:
            data = self._state_to_dict(state)
            with open(self.path, "wb") as f:
                tomli_w.dump(data, f)
        except Exception as e:
            log.error(f"Error saving state to TOML: {e}")

    def _state_to_dict(self, state: AppState) -> Dict[str, Any]:
        groups = []
        for group in state.editor_area.groups:
            tabs = []
            for tab in group.tabs:
                tab_data: Dict[str, Any] = {
                    "tab_id": tab.tab_id,
                    "mode": tab.mode,
                    "zoom": tab.zoom,
                    "preview_zoom": tab.preview_zoom,
                }
                if tab.open_file is not None:
                    tab_data["open_file"] = str(tab.open_file)
                tabs.append(tab_data)
            groups.append(
                {
                    "group_id": group.group_id,
                    "active_tab": group.active_tab_index,
                    "tabs": tabs,
                }
            )

        return {
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
            "editor_area": {
                "focused_group": state.editor_area.focused_group_index,
                "divider_fractions": list(state.editor_area.divider_fractions),
                "groups": groups,
            },
            "theme": {
                "theme_id": state.theme_id,
            },
            "mermaid": {
                "dismissed": state.mermaid_dismissed,
            },
        }

    def load(self) -> AppState:
        if not self.path.exists():
            raise FileNotFoundError(f"State file not found: {self.path}")

        with open(self.path, "rb") as f:
            data = tomllib.load(f)

        general = data.get("general", {})
        panes = data.get("panes", {})
        theme_data = data.get("theme", {})
        mermaid_data = data.get("mermaid", {})
        editor_area_data = data.get("editor_area", {})

        vault_root_str = general.get("last_vault", ".")
        vault_root = Path(vault_root_str)

        editor_area = self._load_editor_area(editor_area_data, vault_root)

        return AppState(
            vault_root=vault_root,
            tree_width=panes.get("tree_width", 180),
            tree_visible=panes.get("tree_visible", True),
            tree_expanded=panes.get("tree_expanded", []),
            tree_zoom=panes.get("tree_zoom", 1.0),
            terminal_width=panes.get("terminal_width", 360),
            terminal_visible=panes.get("terminal_visible", True),
            terminal_zoom=panes.get("terminal_zoom", 1.0),
            editor_area=editor_area,
            theme_id=theme_data.get("theme_id", "solarized-light"),
            mermaid_dismissed=mermaid_data.get("dismissed", False),
        )

    @staticmethod
    def _sanitize_path(raw: str, vault_root_str: str) -> Optional[str]:
        """Strip accidental absolute prefixes; return None if path is invalid."""
        if not raw:
            return None
        if vault_root_str and raw.startswith(vault_root_str):
            raw = raw[len(vault_root_str) :].lstrip("/")
        elif Path(raw).is_absolute():
            # Absolute path that doesn't match vault root — discard.
            return None
        return raw or None

    def _load_editor_area(
        self, editor_area_data: Dict[str, Any], vault_root: Path
    ) -> EditorAreaState:
        raw_groups = editor_area_data.get("groups", [])
        vault_root_str = str(vault_root)

        loaded_groups: List[GroupState] = []
        for g in raw_groups:
            raw_tabs = g.get("tabs", [])
            loaded_tabs: List[TabState] = []
            for t in raw_tabs:
                raw_path = t.get("open_file")
                if raw_path:
                    # File-backed tab: validate and drop if stale.
                    clean_path = self._sanitize_path(raw_path, vault_root_str)
                    if clean_path is None:
                        log.info(f"Dropping tab with invalid path: {raw_path}")
                        continue  # invalid path — drop tab
                    if not (vault_root / clean_path).exists():
                        log.info(f"Dropping stale tab (file missing): {clean_path}")
                        continue  # file gone — drop tab
                    loaded_tabs.append(
                        TabState(
                            tab_id=t.get("tab_id", ""),
                            open_file=VaultPath.from_str(clean_path),
                            mode=t.get("mode", "editor"),
                            zoom=t.get("zoom", 1.0),
                            preview_zoom=t.get("preview_zoom", 1.0),
                        )
                    )
                else:
                    # Blank tab — keep as-is.
                    loaded_tabs.append(
                        TabState(
                            tab_id=t.get("tab_id", ""),
                            open_file=None,
                            mode=t.get("mode", "editor"),
                            zoom=t.get("zoom", 1.0),
                            preview_zoom=t.get("preview_zoom", 1.0),
                        )
                    )

            if not loaded_tabs:
                # Group is empty after cleanup — skip it (group auto-deleted).
                log.info(f"Dropping empty group: {g.get('group_id')}")
                continue

            active = g.get("active_tab", 0)
            active = max(0, min(active, len(loaded_tabs) - 1))
            loaded_groups.append(
                GroupState(
                    group_id=g.get("group_id", ""),
                    tabs=tuple(loaded_tabs),
                    active_tab_index=active,
                )
            )

        if not loaded_groups:
            log.info("No groups loaded from state; falling back to default.")
            # Fallback: one group with one blank tab.
            loaded_groups = [GroupState()]

        raw_fractions = editor_area_data.get("divider_fractions", [])
        # Clamp fractions list to match the actual number of dividers.
        expected_dividers = len(loaded_groups) - 1
        fractions = list(raw_fractions)[:expected_dividers]
        while len(fractions) < expected_dividers:
            fractions.append(0.5)

        focused = editor_area_data.get("focused_group", 0)
        focused = max(0, min(focused, len(loaded_groups) - 1))

        log.info(
            f"Loaded editor area with {len(loaded_groups)} groups "
            f"and {len(fractions)} dividers."
        )

        return EditorAreaState(
            groups=tuple(loaded_groups),
            divider_fractions=tuple(fractions),
            focused_group_index=focused,
        )
