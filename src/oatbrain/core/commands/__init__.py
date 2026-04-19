from dataclasses import dataclass
from oatbrain.core.ports.filestore import VaultPath
from .ui import ToggleTree, ToggleTerminal, SendToTerminal


@dataclass(frozen=True)
class OpenFile:
    path: VaultPath


__all__ = ["OpenFile", "ToggleTree", "ToggleTerminal", "SendToTerminal"]
