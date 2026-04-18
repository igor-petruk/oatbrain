import pytest
from oatbrain.adapters.theme.loader import load_theme, list_theme_ids
from oatbrain.core.theme.models import ThemeData


def test_list_theme_ids_includes_bundled() -> None:
    ids = list_theme_ids()
    assert "solarized-light" in ids
    assert "monokai-dark" in ids
    assert "high-contrast-dark" in ids


def test_load_solarized_light() -> None:
    theme = load_theme("solarized-light")
    assert isinstance(theme, ThemeData)
    assert theme.name == "Solarized Light"
    assert theme.kind == "light"
    assert theme.source_scheme == "solarized-light"


def test_load_monokai_dark() -> None:
    theme = load_theme("monokai-dark")
    assert theme.kind == "dark"
    assert theme.source_scheme == "oblivion"


def test_load_high_contrast_dark() -> None:
    theme = load_theme("high-contrast-dark")
    assert theme.kind == "high-contrast-dark"
    assert theme.source_scheme == "cobalt"


def test_bundled_themes_have_required_tokens() -> None:
    required = {"color-bg", "color-fg", "color-accent", "color-border"}
    for theme_id in ("solarized-light", "monokai-dark", "high-contrast-dark"):
        theme = load_theme(theme_id)
        for token in required:
            assert token in theme.tokens, f"{theme_id} missing token {token!r}"


def test_bundled_themes_have_ansi_palette() -> None:
    for theme_id in ("solarized-light", "monokai-dark", "high-contrast-dark"):
        theme = load_theme(theme_id)
        for i in range(16):
            assert str(i) in theme.ansi, f"{theme_id} missing ansi[{i}]"
        assert "fg" in theme.ansi
        assert "bg" in theme.ansi


def test_load_unknown_theme_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_theme("no-such-theme")
