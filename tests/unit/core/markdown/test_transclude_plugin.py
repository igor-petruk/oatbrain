from markdown_it import MarkdownIt
from unittest.mock import MagicMock
from oatbrain.core.markdown.wikilink import wikilink_plugin
from oatbrain.core.markdown.transclude import transclude_plugin
from oatbrain.core.ports.filestore import VaultPath, FileStore
from oatbrain.core.wikilink.resolver import WikilinkResolver


def test_transclude_parsing_simple() -> None:
    md = MarkdownIt().use(wikilink_plugin).use(transclude_plugin)
    
    # Mock dependencies
    filestore = MagicMock(spec=FileStore)
    resolver = MagicMock(spec=WikilinkResolver)
    
    from_path = VaultPath.from_str("note.md")
    target_path = VaultPath.from_str("other.md")
    
    resolver.resolve.return_value = target_path
    filestore.read_text.return_value = "Transcluded content"
    
    # We need md_instance in env for the renderer to work
    env = {
        "md_instance": md,
        "filestore": filestore,
        "resolver": resolver,
        "from_path": from_path,
    }
    
    html = md.render("![[other]]", env=env)
    
    assert 'class="transclusion"' in html
    assert "Transcluded content" in html
    resolver.resolve.assert_called_once_with("other", from_path)
    filestore.read_text.assert_called_once_with(target_path)


def test_transclude_circular_detection() -> None:
    md = MarkdownIt().use(wikilink_plugin).use(transclude_plugin)
    
    filestore = MagicMock(spec=FileStore)
    resolver = MagicMock(spec=WikilinkResolver)
    
    path_a = VaultPath.from_str("a.md")
    resolver.resolve.return_value = path_a
    
    # Simulate being already in the stack for path_a
    env = {
        "md_instance": md,
        "filestore": filestore,
        "resolver": resolver,
        "from_path": path_a,
        "transclude_stack": [str(path_a)]
    }
    
    html = md.render("![[a]]", env=env)
    assert "Circular transclusion detected" in html


def test_transclude_depth_limit() -> None:
    md = MarkdownIt().use(wikilink_plugin).use(transclude_plugin)
    
    filestore = MagicMock(spec=FileStore)
    resolver = MagicMock(spec=WikilinkResolver)
    
    path_deep = VaultPath.from_str("deep.md")
    resolver.resolve.return_value = path_deep
    
    # 6 levels already in stack
    env = {
        "md_instance": md,
        "filestore": filestore,
        "resolver": resolver,
        "from_path": VaultPath.from_str("top.md"),
        "transclude_stack": ["1", "2", "3", "4", "5", "6"]
    }
    
    html = md.render("![[deep]]", env=env)
    assert "Transclusion depth limit exceeded" in html
