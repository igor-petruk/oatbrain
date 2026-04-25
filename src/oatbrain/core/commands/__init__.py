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


@dataclass(frozen=True)
class CloseFile:
    pass


@dataclass(frozen=True)
class UpdateOpenFilePath:
    path: VaultPath


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
]
