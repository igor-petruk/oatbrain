from dataclasses import dataclass
from oatbrain.core.ports.filestore import VaultPath

@dataclass(frozen=True)
class UpdateWordCount:
    """Command to update word count in state."""
    count: int
