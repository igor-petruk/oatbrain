from typing import Protocol, Iterable
from dataclasses import dataclass
from pathlib import PurePosixPath

@dataclass(frozen=True)
class VaultPath:
    """Vault-relative, forward-slash normalised."""
    path: PurePosixPath

    @classmethod
    def from_str(cls, path_str: str) -> "VaultPath":
        return cls(PurePosixPath(path_str))

    def __str__(self) -> str:
        return str(self.path)

    @property
    def parent(self) -> "VaultPath":
        return VaultPath(self.path.parent)

@dataclass(frozen=True)
class FileEntry:
    path: VaultPath
    is_dir: bool
    is_readonly: bool
    size: int
    mtime: float

class FileStore(Protocol):
    def exists(self, p: VaultPath) -> bool: ...
    def stat(self, p: VaultPath) -> FileEntry: ...
    def read_text(self, p: VaultPath) -> str: ...
    def write_text(self, p: VaultPath, content: str) -> None: ...
    def list_dir(self, p: VaultPath) -> list[FileEntry]: ...
    def rename(self, src: VaultPath, dst: VaultPath) -> None: ...
    def delete(self, p: VaultPath) -> None: ...
    def walk(self, root: VaultPath) -> Iterable[FileEntry]: ...
