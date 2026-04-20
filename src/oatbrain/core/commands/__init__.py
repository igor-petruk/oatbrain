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


@dataclass(frozen=True)
class OpenFile:
    path: VaultPath
    new_tab: bool = False


__all__ = [
    "OpenFile",
    "ToggleTree",
    "ToggleTerminal",
    "RestartTerminal",
    "SendToTerminal",
    "DismissMermaidWarning",
    "SetTreeExpanded",
    "Zoom",
]
