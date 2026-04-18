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
        frontmatter_html = ""
        body = markdown
        if markdown.startswith("---"):
            parts = markdown.split("---", 2)
            if len(parts) >= 3:
                import yaml  # type: ignore[import-untyped]

                try:
                    fm = yaml.safe_load(parts[1])
                    if fm and isinstance(fm, dict):
                        frontmatter_html = (
                            '<div class="frontmatter" style="font-size: 0.9em; '
                            "margin-bottom: 1.5em; opacity: 0.9; "
                            'font-family: var(--font-mono, monospace);">'
                        )

                        # Use 'title' as main header if exists
                        if "title" in fm:
                            frontmatter_html += (
                                '<h1 style="margin-top:0; font-size: 1.5em; '
                                'font-family: var(--font-sans, sans-serif);">'
                                f'{fm["title"]}</h1>'
                            )
                            del fm["title"]

                        frontmatter_html += (
                            '<table style="border:none; width:100%; '
                            'border-collapse: collapse;">'
                        )
                        for k, v in fm.items():
                            icon = "🏷️" if k == "tags" else "📝"
                            if k == "tags" and isinstance(v, list):
                                val = " ".join(
                                    [
                                        (
                                            '<span class="tag" style="'
                                            "background:var(--color-bg-alt); "
                                            "color:var(--color-fg-muted); "
                                            "padding:0.1em 0.4em; "
                                            "border-radius:3px; "
                                            'font-size: 0.9em;">'
                                            f"{t}</span>"
                                        )
                                        for t in v
                                    ]
                                )
                            else:
                                str_v = str(v)
                                if str_v.startswith(("http://", "https://")):
                                    val = (
                                        f'<a href="{str_v}" style="'
                                        'color:var(--color-link);" '
                                        f'target="_blank">{str_v}</a>'
                                    )
                                else:
                                    val = str_v
                            frontmatter_html += (
                                "<tr>"
                                '<td style="border:none; width:20px; padding: 2px;">'
                                f"{icon}</td>"
                                '<td style="border:none; font-weight:bold; '
                                "width:80px; padding: 2px; "
                                'color:var(--color-fg-muted);">'
                                f"{k.capitalize()}</td>"
                                f'<td style="border:none; padding: 2px;">{val}</td>'
                                "</tr>"
                            )
                        frontmatter_html += "</table></div>"
                except yaml.YAMLError:
                    pass
                body = parts[2]

        return frontmatter_html + str(self._md.render(body))
