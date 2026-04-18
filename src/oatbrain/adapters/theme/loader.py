import tomllib
from pathlib import Path
from typing import Literal, cast

from oatbrain.core.theme.models import ThemeData

_BUNDLED_DIR = Path(__file__).parent.parent.parent / "data" / "themes"

# Maps theme id → GtkSourceView style scheme id (§20.9)
_SOURCE_SCHEMES: dict[str, str] = {
    "solarized-light": "solarized-light",
    "monokai-dark": "oblivion",
    "high-contrast-dark": "cobalt",
}


def load_theme(theme_id: str, user_theme_dir: Path | None = None) -> ThemeData:
    """Load a theme by ID from bundled or user theme directories."""
    path = _find_theme_file(theme_id, user_theme_dir)
    with open(path, "rb") as f:
        raw = tomllib.load(f)

    raw_kind = raw.get("kind", "light")
    assert raw_kind in ("light", "dark", "high-contrast-dark")
    kind = cast(Literal["light", "dark", "high-contrast-dark"], raw_kind)

    return ThemeData(
        id=theme_id,
        name=raw.get("name", theme_id),
        kind=kind,
        tokens=raw.get("tokens", {}),
        ansi=raw.get("ansi", {}),
        source_scheme=_SOURCE_SCHEMES.get(theme_id, "classic"),
    )


def list_theme_ids(user_theme_dir: Path | None = None) -> list[str]:
    """Return IDs of all available themes (bundled + user)."""
    ids: list[str] = []
    for p in sorted(_BUNDLED_DIR.glob("*.toml")):
        ids.append(p.stem)
    if user_theme_dir and user_theme_dir.is_dir():
        for p in sorted(user_theme_dir.glob("*.toml")):
            if p.stem not in ids:
                ids.append(p.stem)
    return ids


def _find_theme_file(theme_id: str, user_theme_dir: Path | None) -> Path:
    if user_theme_dir:
        candidate = user_theme_dir / f"{theme_id}.toml"
        if candidate.exists():
            return candidate
    bundled = _BUNDLED_DIR / f"{theme_id}.toml"
    if bundled.exists():
        return bundled
    raise FileNotFoundError(f"Theme not found: {theme_id!r}")
