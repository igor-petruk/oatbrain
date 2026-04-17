from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable
from oatbrain.core.ports.filestore import FileStore

@dataclass(frozen=True)
class Vault:
    root: Path
    store: FileStore

class VaultResolver:
    """Handles vault discovery and initialization."""

    def __init__(self, store_factory: Callable[[Path], FileStore]):
        self._store_factory = store_factory

    def resolve(self, path: Path) -> Vault:
        """
        Find the vault root by walking up from path until a .oatbrain/ 
        directory or the filesystem root is reached.
        """
        curr = path.resolve()
        while curr != curr.parent:
            if (curr / ".oatbrain").is_dir():
                return Vault(root=curr, store=self._store_factory(curr))
            curr = curr.parent
        
        # If no .oatbrain found, the provided path IS the root (default behavior)
        return Vault(root=path.resolve(), store=self._store_factory(path.resolve()))
