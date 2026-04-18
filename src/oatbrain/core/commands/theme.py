from dataclasses import dataclass


@dataclass(frozen=True)
class SetTheme:
    """Switch the active theme by ID (SPEC §20.5)."""

    theme_id: str
