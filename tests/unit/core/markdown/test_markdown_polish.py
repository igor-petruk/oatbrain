from unittest.mock import MagicMock
from oatbrain.adapters.renderer.markdown_it import MarkdownItRenderer
from oatbrain.core.ports.filestore import FileStore, VaultPath
from oatbrain.core.wikilink.resolver import WikilinkResolver


def test_markdown_polish_features() -> None:
    filestore = MagicMock(spec=FileStore)
    resolver = MagicMock(spec=WikilinkResolver)
    renderer = MarkdownItRenderer(filestore, resolver)
    path = VaultPath.from_str("note.md")

    # 1. Highlight
    html = renderer.render("==highlight==", path)
    assert "<mark>highlight</mark>" in html

    # 2. Callout
    callout_md = "> [!info] My Title\n> My content"
    html = renderer.render(callout_md, path)
    assert '<div class="callout callout-info" data-callout="info">' in html
    assert '<div class="callout-title">My Title</div>' in html
    assert "My content" in html

    # 3. Collapsible Callout
    callout_md = "> [!warning]- Collapsed\n> Content"
    html = renderer.render(callout_md, path)
    assert '<details class="callout callout-warning" data-callout="warning">' in html
    assert '<summary class="callout-title">Collapsed</summary>' in html

    # 4. Image Sizing
    image_path = VaultPath.from_str("image.png")
    resolver.resolve.return_value = image_path
    filestore.get_path = MagicMock(return_value="/vault/image.png")

    html = renderer.render("![[image.png|300]]", path)
    assert '<img src="file:///vault/image.png" alt="300" style="width: 300px;">' in html

    # 5. Fragment Transclusion (Heading)
    target_path = VaultPath.from_str("target.md")
    resolver.resolve.return_value = target_path
    filestore.read_text.return_value = "# Header\nContent\n## Sub\nSubcontent\n# Next"

    # Transclude just ## Sub
    html = renderer.render("![[target#Sub]]", path)
    assert "Subcontent" in html
    assert "Header" not in html
    assert "Next" not in html
