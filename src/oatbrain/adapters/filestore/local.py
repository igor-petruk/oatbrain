import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Iterable
from oatbrain.core.ports.filestore import FileStore, VaultPath, FileEntry


class LocalFileStore(FileStore):
    """FileStore adapter for local filesystem access."""

    def __init__(self, root: Path):
        # Resolve to absolute path to prevent symlink bypass and ensure
        # consistent comparisons in _to_local sandboxing.
        self._root = root.resolve()

    def _to_local(self, p: VaultPath) -> Path:
        """Resolve VaultPath to an absolute local Path."""
        # Ensure the path doesn't escape the root
        resolved = (self._root / Path(str(p))).resolve()
        if not str(resolved).startswith(str(self._root)):
            raise PermissionError(f"Path '{p}' is outside vault root '{self._root}'")
        return resolved

    def _from_local(self, local_path: Path) -> VaultPath:
        """Convert local Path to VaultPath."""
        rel = local_path.relative_to(self._root)
        return VaultPath(PurePosixPath(rel))

    def _make_entry(self, local_path: Path) -> FileEntry:
        stat = local_path.stat()
        return FileEntry(
            path=self._from_local(local_path),
            is_dir=local_path.is_dir(),
            is_readonly=not os.access(local_path, os.W_OK),
            size=stat.st_size,
            mtime=stat.st_mtime,
        )

    def exists(self, p: VaultPath) -> bool:
        return self._to_local(p).exists()

    def stat(self, p: VaultPath) -> FileEntry:
        return self._make_entry(self._to_local(p))

    def read_text(self, p: VaultPath) -> str:
        return self._to_local(p).read_text(encoding="utf-8")

    def write_text(self, p: VaultPath, content: str) -> None:
        target = self._to_local(p)
        # Dot-prefix keeps the temp file hidden from vault listings and watcher
        # filters. Same directory guarantees atomic rename on the same filesystem.
        fd, tmp_path = tempfile.mkstemp(
            dir=target.parent, prefix=".", suffix=".oatbrain.tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, target)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def list_dir(self, p: VaultPath) -> list[FileEntry]:
        local_dir = self._to_local(p)
        return [self._make_entry(child) for child in local_dir.iterdir()]

    def rename(self, src: VaultPath, dst: VaultPath) -> None:
        self._to_local(src).rename(self._to_local(dst))

    def delete(self, p: VaultPath) -> None:
        local_path = self._to_local(p)
        if local_path.is_dir():
            shutil.rmtree(local_path)
        else:
            local_path.unlink()

    def walk(self, root: VaultPath) -> Iterable[FileEntry]:
        local_root = self._to_local(root)
        for dirpath, dirnames, filenames in os.walk(local_root):
            dp = Path(dirpath)
            for d in dirnames:
                yield self._make_entry(dp / d)
            for f in filenames:
                yield self._make_entry(dp / f)
