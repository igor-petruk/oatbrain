from markdown_it import MarkdownIt
from mdit_py_plugins.front_matter import front_matter_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from mdit_py_plugins.subscript import sub_plugin

from oatbrain.core.ports.filestore import FileStore, VaultPath
from oatbrain.core.markdown.wikilink import wikilink_plugin
from oatbrain.core.markdown.transclude import transclude_plugin
from oatbrain.core.markdown.mark import mark_plugin
from oatbrain.core.markdown.callout import callout_plugin
from oatbrain.core.wikilink.resolver import WikilinkResolver


class MarkdownItRenderer:
    """Renders Markdown to HTML using markdown-it-py (SPEC §11.2).
    ...
    - YAML frontmatter (stripped; not rendered)
    - Wikilinks ([[Name]])

    Extensions NOT available in python3-mdit-py-plugins (Debian bookworm):
    ...
    """

    def __init__(self, filestore: FileStore, resolver: WikilinkResolver) -> None:
        self._filestore = filestore
        self._resolver = resolver
        self._md = (
            MarkdownIt("commonmark")
            .enable("strikethrough")
            .enable("table")
            .use(front_matter_plugin)
            .use(footnote_plugin)
            .use(tasklists_plugin)
            .use(sub_plugin)
            .use(wikilink_plugin)
            .use(transclude_plugin)
            .use(mark_plugin)
            .use(callout_plugin)
        )
        self._md.add_render_rule("fence", self._render_mermaid)

    def _render_mermaid(self, tokens, idx, options, env) -> str:
        token = tokens[idx]
        if token.info == "mermaid":
            import html

            content = html.escape(token.content)
            return (
                '<div class="mermaid-container">'
                f'<div class="mermaid">{content}</div>'
                '<button class="mermaid-expand-btn" onclick="expandMermaid(this)">🔍</button>'
                "</div>"
            )
        return self._md.renderer.renderToken(tokens, idx, options, env)

    def render(self, markdown: str, from_path: VaultPath) -> str:
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
                                f"{fm['title']}</h1>"
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

        # Pass resolver and filestore to plugin via env
        env = {
            "from_path": from_path,
            "resolver": self._resolver,
            "filestore": self._filestore,
            "md_instance": self._md,
        }
        return frontmatter_html + str(self._md.render(body, env=env))
