from oatbrain.core.theme.models import ThemeData
from oatbrain.core.theme.engine import generate_gtk_css


def _make_theme(**kwargs: object) -> ThemeData:
    defaults: dict[str, object] = dict(
        id="test",
        name="Test Theme",
        kind="light",
        tokens={"color-bg": "#ffffff", "color-fg": "#000000"},
        ansi={},
        source_scheme="classic",
    )
    defaults.update(kwargs)
    return ThemeData(**defaults)  # type: ignore[arg-type]


def test_generate_css_produces_root_block() -> None:
    css = generate_gtk_css(_make_theme())
    assert ":root {" in css
    assert ".oatbrain-filetree" in css


def test_generate_css_includes_token_as_custom_property() -> None:
    css = generate_gtk_css(_make_theme())
    assert "--color-bg: #ffffff;" in css
    assert "--color-fg: #000000;" in css


def test_generate_css_empty_tokens() -> None:
    theme = _make_theme(tokens={})
    css = generate_gtk_css(theme)
    assert ":root {" in css


def test_theme_data_fields() -> None:
    theme = _make_theme()
    assert theme.id == "test"
    assert theme.kind == "light"
    assert theme.source_scheme == "classic"
