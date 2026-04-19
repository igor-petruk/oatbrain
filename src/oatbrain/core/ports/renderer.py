from typing import Protocol, runtime_checkable


from .filestore import VaultPath


@runtime_checkable
class Renderer(Protocol):
    """Port: converts Markdown source to an HTML string."""

    def render(self, markdown: str, from_path: VaultPath) -> str:
        """Return an HTML fragment for the given Markdown source."""
        ...
