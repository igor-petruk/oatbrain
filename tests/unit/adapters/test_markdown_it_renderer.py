from unittest.mock import MagicMock
from oatbrain.adapters.renderer.markdown_it import MarkdownItRenderer
from oatbrain.core.ports.renderer import Renderer
from oatbrain.core.ports.filestore import VaultPath, FileStore
from oatbrain.core.wikilink.resolver import WikilinkResolver


def make_renderer() -> MarkdownItRenderer:
    filestore = MagicMock(spec=FileStore)
    resolver = MagicMock(spec=WikilinkResolver)
    return MarkdownItRenderer(filestore, resolver)


def dummy_path() -> VaultPath:
    return VaultPath.from_str("note.md")


def test_implements_renderer_protocol() -> None:
    assert isinstance(make_renderer(), Renderer)


def test_instantiation_does_not_raise() -> None:
    make_renderer()


def test_empty_string_returns_empty() -> None:
    assert make_renderer().render("", dummy_path()) == ""


def test_output_is_deterministic() -> None:
    r = make_renderer()
    md = "# Heading\n\nParagraph with **bold** text."
    assert r.render(md, dummy_path()) == r.render(md, dummy_path())


def test_frontmatter_is_rendered() -> None:
    # Verifies that frontmatter is rendered with the new structure
    md = "---\ntitle: Test\ntags: [a, b]\n---\n\nBody."
    html = make_renderer().render(md, dummy_path())
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
    html = make_renderer().render(md, dummy_path())
    assert "<table>" in html
    assert "<s>" in html
    assert 'type="checkbox"' in html
    assert "<sub>" in html
    assert "footnote" in html


def test_mermaid_block_rendering() -> None:
    # This test will fail if the _render_mermaid signature is incorrect
    md = "```mermaid\ngraph TD; A-->B;\n```"
    html = make_renderer().render(md, dummy_path())
    assert (
        '<div class="mermaid" style="cursor: pointer" '
        'onclick="expandMermaid(this)">' in html
    )
    assert "graph TD; A--&gt;B;\n" in html


def test_standard_image_resolution() -> None:
    renderer = make_renderer()
    # Mock filestore and resolver
    renderer._filestore.exists = MagicMock(return_value=True)  # type: ignore
    renderer._filestore.get_path = MagicMock(
        return_value="/vault/img.png"
    )  # type: ignore
    renderer._resolver.resolve = MagicMock(
        return_value=VaultPath.from_str("img.png")
    )  # type: ignore

    html = renderer.render("![alt](img.png)", VaultPath.from_str("test.md"))
    assert '<img src="file:///vault/img.png" alt="alt" />' in html
