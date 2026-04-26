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
        # Resolved path for mapping followed symlinks back to vault-relative paths.
        self._resolved_root = self._root.resolve()

    def _to_local(self, p: VaultPath) -> Path:
        """Resolve VaultPath to an absolute local Path."""
        # Ensure the path doesn't escape the root.
        # We check against both the original root and the resolved root
        # to support symlinked vaults (SPEC §23).
        local_path = self._root / Path(str(p))
        try:
            # We resolve to catch both lexical and symlink-based escapes.
            resolved = local_path.resolve()
        except (OSError, RuntimeError):
            # Fallback for non-existent paths or other issues
            resolved = local_path.absolute()

        res_str = str(resolved)
        root_str = str(self._root)
        resolved_root_str = str(self._resolved_root)

        if not (res_str.startswith(root_str) or res_str.startswith(resolved_root_str)):
            # Syntactic check as a final fallback for non-existent paths
            # that might not resolve cleanly but are lexically inside.
            parts = p.path.parts
            if parts and parts[0] == "..":
                raise PermissionError(f"Path '{p}' escapes vault root")

        # We return the original local_path (not resolved) to preserve
        # symlink structures where possible, matching self._root.
        return local_path

    def _from_local(self, local_path: Path) -> VaultPath:
        """Convert local Path to VaultPath."""
        abs_p = local_path.absolute()
        try:
            rel = abs_p.relative_to(self._root)
        except ValueError:
            # If not relative to the symlink root, try the resolved root.
            # This handles cases where the vault root is a symlink
            # or contains symlinks.
            try:
                rel = abs_p.resolve().relative_to(self._resolved_root)
            except (ValueError, RuntimeError):
                # Fallback to absolute if it happens to be the same path
                # but different representation
                rel = abs_p.relative_to(self._resolved_root)
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
