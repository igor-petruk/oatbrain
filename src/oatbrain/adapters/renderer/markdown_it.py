from markdown_it import MarkdownIt
from mdit_py_plugins.front_matter import front_matter_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from mdit_py_plugins.subscript import sub_plugin


class MarkdownItRenderer:
    """Renders Markdown to HTML using markdown-it-py (SPEC §11.2).

    Extensions enabled (from §12.2):
    - CommonMark baseline
    - GFM tables
    - Strikethrough (~~text~~)
    - Task lists (- [ ] / - [x])
    - Footnotes ([^1])
    - Subscript (H~2~O)
    - YAML frontmatter (stripped; not rendered)

    Extensions NOT available in python3-mdit-py-plugins (Debian bookworm):
    - Superscript (x^2^) — no sup_plugin in packaged version
    - Highlight (==text==) — no mark plugin in packaged version
    """

    def __init__(self) -> None:
        self._md = (
            MarkdownIt("commonmark")
            .enable("strikethrough")
            .enable("table")
            .use(front_matter_plugin)
            .use(footnote_plugin)
            .use(tasklists_plugin)
            .use(sub_plugin)
        )

    def render(self, markdown: str) -> str:
        return str(self._md.render(markdown))
