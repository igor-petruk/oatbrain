from markdown_it import MarkdownIt
from typing import Any, cast
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


def _highlight_code(code: str, lang: str, _attrs: str) -> str:
    """Highlight code using Pygments (SPEC §11.2)."""
    if not lang:
        return ""

    try:
        from pygments import highlight  # type: ignore[import-untyped]
        from pygments.formatters import HtmlFormatter  # type: ignore[import-untyped]
        from pygments.lexers import (  # type: ignore[import-untyped]
            get_lexer_by_name,
            ClassNotFound,
        )

        lexer = get_lexer_by_name(lang, stripall=True)
        # nowrap=True prevents Pygments from wrapping in <div class="highlight"><pre>
        # because markdown-it-py will wrap it in <pre><code class="language-...">
        formatter = HtmlFormatter(nowrap=True)
        return str(highlight(code, lexer, formatter))
    except (ClassNotFound, ImportError):
        return ""


class MarkdownItRenderer:
    """Renders Markdown to HTML using markdown-it-py (SPEC §11.2).
    Extensions enabled:
    - Strikethrough (~~)
    - Tables
    - Frontmatter (YAML)
    - Footnotes
    - Tasklists
    - Subscript
    - Wikilinks ([[Name]])
    - Transclusions (![[Name]])
    - Mark (==mark==)
    - Callouts (> [!INFO])
    - Syntax highlighting (Pygments)

    Extensions NOT available in python3-mdit-py-plugins (Debian bookworm):
    - Mermaid (handled via custom fence rule)
    """

    def __init__(self, filestore: FileStore, resolver: WikilinkResolver) -> None:
        self._filestore = filestore
        self._resolver = resolver
        self._md = (
            MarkdownIt("commonmark", {"highlight": _highlight_code})
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
        self._default_fence = cast(Any, self._md.renderer).rules["fence"]
        self._md.add_render_rule("fence", self._render_mermaid)
        self._md.add_render_rule("image", self._render_image)
        self._md.add_render_rule("link_open", self._render_link_open)

    def _render_link_open(
        self,
        tokens: list[Any],
        idx: int,
        options: dict[str, Any],
        env: dict[str, Any],
    ) -> str:
        token = tokens[idx]
        href = ""

        for attr, value in token.attrs.items():
            if attr == "href":
                href = value

        resolver = env.get("resolver")
        from_path = env.get("from_path")

        if (
            href
            and not href.startswith(("http://", "https://", "#"))
            and resolver
            and from_path
        ):
            target_path = resolver.resolve(href, from_path)
            if target_path:
                href = f"oatbrain://vault/{target_path}"

        attrs_str = ""
        for attr, value in token.attrs.items():
            val = href if attr == "href" else value
            attrs_str += f' {attr}="{val}"'

        return f"<a{attrs_str}>"

    def _render_image(
        self,
        tokens: list[Any],
        idx: int,
        options: dict[str, Any],
        env: dict[str, Any],
    ) -> str:
        token = tokens[idx]
        src = ""
        alt = token.content
        title = ""

        for attr, value in token.attrs.items():
            if attr == "src":
                src = value
            elif attr == "title":
                title = value

        resolver = env.get("resolver")
        filestore = env.get("filestore")
        from_path = env.get("from_path")

        if src and resolver and filestore and from_path:
            # Try to resolve the image path
            target_path = resolver.resolve(src, from_path)
            if target_path:
                abs_path = filestore.get_path(target_path)
                src = f"file://{abs_path}"

        title_attr = f' title="{title}"' if title else ""
        return f'<img src="{src}" alt="{alt}"{title_attr} />'

    def _render_mermaid(
        self,
        tokens: list[object],
        idx: int,
        options: dict[str, object],
        env: dict[str, object],
    ) -> str:
        token = tokens[idx]
        # In markdown-it-py, fenced code blocks have 'info' as their language
        if hasattr(token, "info") and token.info == "mermaid":
            import html

            content = html.escape(token.content)  # type: ignore
            return (
                '<div class="mermaid-container">'
                '<div class="mermaid" style="cursor: pointer" '
                f'onclick="expandMermaid(this)">{content}</div>'
                "</div>"
            )
        return str(self._default_fence(tokens, idx, options, env))

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
