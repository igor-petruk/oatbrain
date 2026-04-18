from dataclasses import dataclass


@dataclass(frozen=True)
class ToggleTree:
    """Toggle file tree visibility."""

    @classmethod
    def get_palette_commands(cls) -> list[tuple[str, "ToggleTree"]]:
        return [("Toggle File Tree", cls())]


@dataclass(frozen=True)
class ToggleTerminal:
    """Toggle terminal visibility."""

    @classmethod
    def get_palette_commands(cls) -> list[tuple[str, "ToggleTerminal"]]:
        return [("Toggle Terminal", cls())]
