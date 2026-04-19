from markdown_it import MarkdownIt
from oatbrain.core.markdown.wikilink import wikilink_plugin


def test_wikilink_parsing_simple() -> None:
    md = MarkdownIt().use(wikilink_plugin)
    html = md.render("[[Foo]]")
    assert '<a class="wikilink" href="oatbrain://vault/Foo">Foo</a>' in html


def test_wikilink_parsing_alias() -> None:
    md = MarkdownIt().use(wikilink_plugin)
    html = md.render("[[Foo|Bar]]")
    assert '<a class="wikilink" href="oatbrain://vault/Foo">Bar</a>' in html


def test_wikilink_parsing_fragment() -> None:
    md = MarkdownIt().use(wikilink_plugin)
    html = md.render("[[Foo#Heading]]")
    expected = '<a class="wikilink" href="oatbrain://vault/Foo#Heading">Foo#Heading</a>'
    assert expected in html


def test_wikilink_parsing_fragment_alias() -> None:
    md = MarkdownIt().use(wikilink_plugin)
    html = md.render("[[Foo#Heading|Bar]]")
    assert '<a class="wikilink" href="oatbrain://vault/Foo#Heading">Bar</a>' in html


def test_wikilink_parsing_block_id() -> None:
    md = MarkdownIt().use(wikilink_plugin)
    html = md.render("[[Foo#^block-id]]")
    expected = (
        '<a class="wikilink" href="oatbrain://vault/Foo#^block-id">'
        "Foo#^block-id</a>"
    )
    assert expected in html


def test_wikilink_not_confused_by_regular_link() -> None:
    md = MarkdownIt().use(wikilink_plugin)
    html = md.render("[Link](url)")
    assert '<a href="url">Link</a>' in html
    assert "wikilink" not in html
