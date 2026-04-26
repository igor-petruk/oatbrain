from dataclasses import dataclass
from oatbrain.core.ports.filestore import VaultPath
from .ui import (
    ToggleTree,
    ToggleTerminal,
    RestartTerminal,
    SendToTerminal,
    DismissMermaidWarning,
    SetTreeExpanded,
    Zoom,
)
from .editor import (
    ToggleMode,
    ToggleZen,
    RefreshFile,
    NewTab,
    CloseTab,
    SplitGroupRight,
)


@dataclass(frozen=True)
class OpenFile:
    path: VaultPath


@dataclass(frozen=True)
class CloseFile:
    """Internal: close the file in a specific tab (used by Editor internally)."""

    tab_id: str = ""


@dataclass(frozen=True)
class UpdateOpenFilePath:
    """Internal: update the path tracked by a specific tab (used by Editor)."""

    path: VaultPath
    tab_id: str = ""


__all__ = [
    "OpenFile",
    "CloseFile",
    "UpdateOpenFilePath",
    "ToggleTree",
    "ToggleTerminal",
    "RestartTerminal",
    "SendToTerminal",
    "DismissMermaidWarning",
    "SetTreeExpanded",
    "Zoom",
    "ToggleMode",
    "ToggleZen",
    "RefreshFile",
    "NewTab",
    "CloseTab",
    "SplitGroupRight",
]
