from oatbrain.core.ports.filestore import VaultPath
from oatbrain.core.wikilink import WikilinkResolver
from typing import Iterable, Any
from dataclasses import dataclass


@dataclass
class FakeEntry:
    path: VaultPath
    is_dir: bool = False


class FakeFileStore:
    def __init__(self, files: list[str]) -> None:
        self.files = files

    def exists(self, p: VaultPath) -> bool:
        return str(p) in self.files

    def walk(self, root: VaultPath) -> Iterable[Any]:
        for f in self.files:
            yield FakeEntry(path=VaultPath.from_str(f))


def test_url_decoding_repro() -> None:
    # Simulating the user's vault state
    store = FakeFileStore(
        [
            "Projects/Japan Trip 2026/Research/Pregnancy Travel.md",
            "Projects/Japan Trip 2026/Japan Trip Hub.md",
        ]
    )
    resolver = WikilinkResolver(store)  # type: ignore

    # What the browser sends: oatbrain://vault/Pregnancy%20Travel#OB%20Clearance
    # We extract the part after oatbrain://vault/
    raw_from_browser = "Pregnancy%20Travel#OB%20Clearance"

    from urllib.parse import unquote

    decoded = unquote(raw_from_browser)
    assert decoded == "Pregnancy Travel#OB Clearance"

    target = decoded.split("#")[0]
    source_path = VaultPath.from_str("Projects/Japan Trip 2026/Japan Trip Hub.md")

    resolved = resolver.resolve(target, source_path)
    assert resolved is not None
    assert str(resolved) == "Projects/Japan Trip 2026/Research/Pregnancy Travel.md"
