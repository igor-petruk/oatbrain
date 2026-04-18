from dataclasses import dataclass
from oatbrain.core.ports.filestore import VaultPath

@dataclass(frozen=True)
class OpenFile:
    path: VaultPath
