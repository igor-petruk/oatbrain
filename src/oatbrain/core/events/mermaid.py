from dataclasses import dataclass


@dataclass(frozen=True)
class MermaidFetchResult:
    """Emitted when the mermaid.js background fetch completes."""

    success: bool
    error: str = ""
