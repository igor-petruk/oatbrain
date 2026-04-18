from oatbrain.adapters.renderer.markdown_it import MarkdownItRenderer
from oatbrain.core.ports.renderer import Renderer


def make_renderer() -> MarkdownItRenderer:
    return MarkdownItRenderer()


def test_implements_renderer_protocol() -> None:
    assert isinstance(make_renderer(), Renderer)


def test_heading() -> None:
    html = make_renderer().render("# Hello World")
    assert "<h1>Hello World</h1>" in html


def test_paragraph() -> None:
    html = make_renderer().render("Simple paragraph.")
    assert "<p>Simple paragraph.</p>" in html


def test_bold_and_italic() -> None:
    html = make_renderer().render("**bold** and *italic*")
    assert "<strong>bold</strong>" in html
    assert "<em>italic</em>" in html


def test_inline_code_and_fenced_block() -> None:
    html = make_renderer().render("`code`\n\n```\nblock\n```")
    assert "<code>code</code>" in html
    assert "<code>block" in html


def test_link() -> None:
    html = make_renderer().render("[label](https://example.com)")
    assert 'href="https://example.com"' in html
    assert ">label<" in html


def test_gfm_table() -> None:
    md = "| A | B |\n|---|---|\n| 1 | 2 |"
    html = make_renderer().render(md)
    assert "<table>" in html
    assert "<th>A</th>" in html
    assert "<td>1</td>" in html


def test_strikethrough() -> None:
    html = make_renderer().render("~~struck~~")
    assert "<s>struck</s>" in html


def test_task_list_unchecked() -> None:
    html = make_renderer().render("- [ ] todo")
    assert 'type="checkbox"' in html
    assert "checked" not in html


def test_task_list_checked() -> None:
    html = make_renderer().render("- [x] done")
    assert 'checked="checked"' in html


def test_footnote() -> None:
    md = "Text[^1]\n\n[^1]: The footnote."
    html = make_renderer().render(md)
    assert "footnote" in html
    assert "The footnote." in html


def test_subscript() -> None:
    html = make_renderer().render("H~2~O")
    assert "<sub>2</sub>" in html


def test_frontmatter_stripped() -> None:
    md = "---\ntitle: Test\n---\n\nBody text."
    html = make_renderer().render(md)
    assert "title:" not in html
    assert "<p>Body text.</p>" in html


def test_empty_string() -> None:
    assert make_renderer().render("") == ""


def test_deterministic_output() -> None:
    r = make_renderer()
    md = "# Heading\n\nParagraph."
    assert r.render(md) == r.render(md)
