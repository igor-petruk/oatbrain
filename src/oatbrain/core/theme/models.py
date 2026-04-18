from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class ThemeData:
    """Parsed theme TOML (SPEC §20.3)."""

    id: str
    name: str
    kind: Literal["light", "dark", "high-contrast-dark"]
    tokens: dict[str, str] = field(default_factory=dict)
    ansi: dict[str, str] = field(default_factory=dict)

    # GtkSourceView style scheme to use when this theme is active (§20.9)
    source_scheme: str = "classic"
