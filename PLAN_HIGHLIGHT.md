# PLAN: Syntax Highlighting for Markdown Code Blocks

This plan details the implementation of syntax highlighting for fenced code blocks in Markdown using Pygments.

## 1. Update Dependencies [DONE]
Add `Pygments` to `dependencies` in `pyproject.toml`. Pygments is a standard Python library for syntax highlighting and is available in Debian as `python3-pygments`.

## 2. Integrate Pygments into `MarkdownItRenderer` [DONE]
Update `src/oatbrain/adapters/renderer/markdown_it.py` to use a highlighting hook.

```python
def highlight_code(code: str, lang: str, attrs: str) -> str:
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name, ClassNotFound
    from pygments.formatters import HtmlFormatter

    if not lang:
        return ""

    try:
        lexer = get_lexer_by_name(lang, stripall=True)
        formatter = HtmlFormatter(nowrap=True)
        return highlight(code, lexer, formatter)
    except ClassNotFound:
        return ""
```

Configure `MarkdownIt` with this function:
```python
self._md = MarkdownIt("commonmark", {"highlight": highlight_code})
```

## 3. Inject CSS Styles [DONE]
Update `src/oatbrain/ui/preview.py` to inject Pygments CSS into the HTML template.

- Define a method to get Pygments CSS based on the theme (e.g., `solarized-light` for light themes, `monokai` for dark themes).
- Update `_wrap_html` to include this CSS.

## 4. Testing [DONE]
- Update `tests/unit/adapters/test_markdown_it_renderer.py` to verify that code blocks are correctly highlighted (i.e., contain Pygments' HTML tags/classes).
- Verify with `make test`.

## 5. Verification [DONE]
- Manual verification in the GUI using `make run` (if possible) or by inspecting the rendered HTML in tests.
- Ensure no regressions in Mermaid rendering or other Markdown features.
