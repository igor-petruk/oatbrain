from typing import Iterable
from dataclasses import dataclass
from oatbrain.core.ports.filestore import VaultPath, FileEntry
from oatbrain.core.wikilink.resolver import WikilinkResolver


@dataclass
class FakeEntry:
    path: str
    is_dir: bool = False


class FakeFileStore:
    def __init__(self, files: list[str]) -> None:
        self.files = files

    def exists(self, p: VaultPath) -> bool:
        return str(p) in self.files

    def walk(self, root: VaultPath) -> Iterable[FileEntry]:
        for f in self.files:
            yield FileEntry(
                path=VaultPath.from_str(f),
                is_dir=False,
                is_readonly=False,
                size=0,
                mtime=0.0,
            )


def test_resolver_simple_name() -> None:
    store = FakeFileStore(["foo.md", "bar.md"])
    resolver = WikilinkResolver(store)  # type: ignore

    result = resolver.resolve("foo", VaultPath.from_str("note.md"))
    assert result is not None
    assert str(result) == "foo.md"


def test_resolver_ambiguous_name_prefers_root() -> None:
    # Multiple files with same basename, none in same folder as source
    # Alphabetical order would pick folder1/foo.md
    store = FakeFileStore(["folder1/foo.md", "foo.md"])
    resolver = WikilinkResolver(store)  # type: ignore

    result = resolver.resolve("foo", VaultPath.from_str("other_folder/note.md"))
    assert result is not None
    # depth-based sorting: foo.md (depth 0) comes before folder1/foo.md (depth 1)
    assert str(result) == "foo.md"


def test_resolver_same_folder_priority() -> None:
    # Multiple files with same basename, one IS in same folder as source
    store = FakeFileStore(["folder1/foo.md", "folder2/foo.md"])
    resolver = WikilinkResolver(store)  # type: ignore

    # Source is in folder2, should pick folder2/foo.md
    # despite folder1 coming first alphabetically
    result = resolver.resolve("foo", VaultPath.from_str("folder2/note.md"))
    assert result is not None
    assert str(result) == "folder2/foo.md"


def test_resolver_local_first_over_depth() -> None:
    # Multiple files with same basename, root (depth 0) vs local (depth 1)
    # The local one should win (Local-First)
    store = FakeFileStore(["foo.md", "folder/foo.md"])
    resolver = WikilinkResolver(store)  # type: ignore

    result = resolver.resolve("foo", VaultPath.from_str("folder/note.md"))
    assert result is not None
    assert str(result) == "folder/foo.md"


def test_resolver_root_relative_via_slash() -> None:
    # Explicitly ask for root using leading slash
    store = FakeFileStore(["folder1/foo.md", "foo.md"])
    resolver = WikilinkResolver(store)  # type: ignore

    # Even if source is in folder1, /foo should resolve to root foo.md
    result = resolver.resolve("/foo", VaultPath.from_str("folder1/note.md"))
    assert result is not None
    assert str(result) == "foo.md"


def test_resolver_vault_relative_path() -> None:
    store = FakeFileStore(["folder/foo.md"])
    resolver = WikilinkResolver(store)  # type: ignore

    result = resolver.resolve("folder/foo", VaultPath.from_str("note.md"))
    assert result is not None
    assert str(result) == "folder/foo.md"


def test_resolver_file_relative_path() -> None:
    store = FakeFileStore(["folder/sub/foo.md"])
    resolver = WikilinkResolver(store)  # type: ignore

    # linking from folder/other.md to sub/foo
    result = resolver.resolve("sub/foo", VaultPath.from_str("folder/other.md"))
    assert result is not None
    assert str(result) == "folder/sub/foo.md"


def test_resolver_dot_dot_relative_path() -> None:
    store = FakeFileStore(["folder/foo.md"])
    resolver = WikilinkResolver(store)  # type: ignore

    # linking from folder/sub/note.md to ../foo
    result = resolver.resolve("../foo", VaultPath.from_str("folder/sub/note.md"))
    assert result is not None
    assert str(result) == "folder/foo.md"


def test_resolver_unresolved() -> None:
    store = FakeFileStore(["foo.md"])
    resolver = WikilinkResolver(store)  # type: ignore

    result = resolver.resolve("missing", VaultPath.from_str("note.md"))
    assert result is None
