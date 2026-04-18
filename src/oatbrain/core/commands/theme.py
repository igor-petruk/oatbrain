from dataclasses import dataclass


@dataclass(frozen=True)
class SetTheme:
    """Switch the active theme by ID (SPEC §20.5)."""

    theme_id: str

    @classmethod
    def get_palette_commands(cls) -> list[tuple[str, "SetTheme"]]:
        return [
            ("Set Theme: Solarized Light", cls("solarized-light")),
            ("Set Theme: High Contrast Dark", cls("high-contrast-dark")),
            ("Set Theme: Monokai Dark", cls("monokai-dark")),
        ]
