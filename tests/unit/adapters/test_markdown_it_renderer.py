from oatbrain.adapters.renderer.markdown_it import MarkdownItRenderer
from oatbrain.core.ports.renderer import Renderer


def make_renderer() -> MarkdownItRenderer:
    return MarkdownItRenderer()


def test_implements_renderer_protocol() -> None:
    assert isinstance(make_renderer(), Renderer)


def test_instantiation_does_not_raise() -> None:
    make_renderer()


def test_empty_string_returns_empty() -> None:
    assert make_renderer().render("") == ""


def test_output_is_deterministic() -> None:
    r = make_renderer()
    md = "# Heading\n\nParagraph with **bold** text."
    assert r.render(md) == r.render(md)


def test_frontmatter_is_stripped() -> None:
    # We explicitly chose to add front_matter_plugin; verify it strips YAML
    md = "---\ntitle: Test\ntags: [a, b]\n---\n\nBody."
    html = make_renderer().render(md)
    assert "title:" not in html
    assert "tags:" not in html
    assert "Body." in html


def test_all_configured_extensions_are_active() -> None:
    # One smoke test: verify every extension we wired actually fires.
    # Tests the wiring in __init__, not the extension internals.
    md = (
        "| A | B |\n|---|---|\n| 1 | 2 |\n\n"  # tables
        "~~s~~\n\n"                              # strikethrough
        "- [ ] todo\n\n"                         # tasklists
        "H~2~O\n\n"                              # subscript
        "foot[^1]\n\n[^1]: note"                 # footnotes
    )
    html = make_renderer().render(md)
    assert "<table>" in html
    assert "<s>" in html
    assert 'type="checkbox"' in html
    assert "<sub>" in html
    assert "footnote" in html
