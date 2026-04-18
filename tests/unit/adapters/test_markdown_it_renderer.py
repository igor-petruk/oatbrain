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


def test_frontmatter_is_rendered() -> None:
    # Verifies that frontmatter is rendered with the new structure
    md = "---\ntitle: Test\ntags: [a, b]\n---\n\nBody."
    html = make_renderer().render(md)
    assert '<div class="frontmatter"' in html
    assert (
        '<h1 style="margin-top:0; font-size: 1.5em; '
        'font-family: var(--font-sans, sans-serif);">Test</h1>' in html
    )
    assert "🏷️" in html
    assert '<span class="tag"' in html
    assert "Body." in html
    assert "Tags" in html
    assert "Tags:" not in html  # Verify no colon


def test_all_configured_extensions_are_active() -> None:
    # One smoke test: verify every extension we wired actually fires.
    # Tests the wiring in __init__, not the extension internals.
    md = (
        "| A | B |\n|---|---|\n| 1 | 2 |\n\n"  # tables
        "~~s~~\n\n"  # strikethrough
        "- [ ] todo\n\n"  # tasklists
        "H~2~O\n\n"  # subscript
        "foot[^1]\n\n[^1]: note"  # footnotes
    )
    html = make_renderer().render(md)
    assert "<table>" in html
    assert "<s>" in html
    assert 'type="checkbox"' in html
    assert "<sub>" in html
    assert "footnote" in html
