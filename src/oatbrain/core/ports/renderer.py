from typing import Protocol, runtime_checkable


@runtime_checkable
class Renderer(Protocol):
    """Port: converts Markdown source to an HTML string."""

    def render(self, markdown: str) -> str:
        """Return an HTML fragment for the given Markdown source."""
        ...
