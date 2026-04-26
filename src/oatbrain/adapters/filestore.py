import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Iterable
from oatbrain.core.ports.filestore import FileStore, VaultPath, FileEntry


class LocalFileStore(FileStore):
    """FileStore adapter for local filesystem access."""

    def __init__(self, root: Path):
        # We use absolute() instead of resolve() to preserve symlinks in the root path.
        # This allows the vault itself to be a symlink (SPEC §23).
        self._root = root.absolute()

    def _to_local(self, p: VaultPath) -> Path:
        """Resolve VaultPath to an absolute local Path."""
        # Ensure the path doesn't syntactically escape the root.
        # We do not use .resolve() to allow symlinks inside the vault
        # to point to external directories (e.g. ~/Vault -> ~/ActualVault).
        if p.path.parts and p.path.parts[0] == "..":
            raise PermissionError(f"Path '{p}' escapes vault root '{self._root}'")
        return self._root / Path(str(p))

    def _from_local(self, local_path: Path) -> VaultPath:
        """Convert local Path to VaultPath."""
        # Use absolute() here too to match self._root formatting
        rel = local_path.absolute().relative_to(self._root)
        return VaultPath(PurePosixPath(rel))

    def _make_entry(self, local_path: Path) -> FileEntry | None:
        try:
            stat = local_path.stat()
            return FileEntry(
                path=self._from_local(local_path),
                is_dir=local_path.is_dir(),
                is_readonly=not os.access(local_path, os.W_OK),
                size=stat.st_size,
                mtime=stat.st_mtime,
            )
        except (FileNotFoundError, PermissionError, ValueError):
            return None

    def get_path(self, p: VaultPath) -> str:
        """Resolve VaultPath to an absolute local path string."""
        return str(self._to_local(p))

    def exists(self, p: VaultPath) -> bool:
        return self._to_local(p).exists()

    def stat(self, p: VaultPath) -> FileEntry:
        entry = self._make_entry(self._to_local(p))
        if entry is None:
            raise FileNotFoundError(f"Path '{p}' not found")
        return entry

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
            # Preserve original permissions if file exists
            if target.exists():
                os.fchmod(fd, target.stat().st_mode)

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
        entries = [
            self._make_entry(child)
            for child in local_dir.iterdir()
            if not child.name.startswith(".")
        ]
        return [e for e in entries if e is not None]

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
        for dirpath, dirnames, filenames in os.walk(local_root, followlinks=True):
            dp = Path(dirpath)
            # Filter hidden directories from being traversed
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            # Filter out entries that disappeared
            for d in dirnames:
                entry = self._make_entry(dp / d)
                if entry:
                    yield entry
            for f in filenames:
                if not f.startswith("."):
                    entry = self._make_entry(dp / f)
                    if entry:
                        yield entry
