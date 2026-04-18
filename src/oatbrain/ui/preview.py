import gi
from typing import Callable, Optional

gi.require_version("WebKit", "6.0")
from gi.repository import WebKit, Gio, GLib  # noqa: E402

from oatbrain.core.ports.renderer import Renderer  # noqa: E402


class Preview:
    """Read-mode pane: renders Markdown to HTML via WebKitWebView (SPEC §11)."""

    def __init__(self, renderer: Renderer) -> None:
        self._renderer = renderer
        self._pending_fraction: Optional[float] = None

        self._webview = WebKit.WebView()
        self._webview.set_hexpand(True)
        self._webview.set_vexpand(True)
        self._webview.connect("load-changed", self._on_load_changed)

        self.widget = self._webview

    def render(
        self, markdown: str, scroll_to: float = 0.0, theme_css: str = ""
    ) -> None:
        self._pending_fraction = scroll_to
        self._theme_css = theme_css
        html = self._renderer.render(markdown)
        self._webview.load_html(self._wrap_html(html, theme_css), "file:///")

    def get_scroll_fraction(self, callback: Callable[[float], None]) -> None:
        script = (
            "(function(){"
            "var h=document.documentElement.scrollHeight-window.innerHeight;"
            "return h>0?window.scrollY/h:0;"
            "})()"
        )

        def _on_result(
            _wv: WebKit.WebView, result: Gio.AsyncResult, _ud: None
        ) -> None:
            try:
                js_val = self._webview.evaluate_javascript_finish(result)
                fraction = js_val.to_double() if js_val is not None else 0.0
            except Exception:
                fraction = 0.0
            callback(fraction)

        self._webview.evaluate_javascript(
            script, -1, None, None, None, _on_result, None
        )

    def clear(self) -> None:
        self._webview.load_html("", "file:///")

    def _on_load_changed(
        self, _wv: WebKit.WebView, event: WebKit.LoadEvent
    ) -> None:
        if event == WebKit.LoadEvent.FINISHED and self._pending_fraction is not None:
            frac = self._pending_fraction
            self._pending_fraction = None
            if frac > 0.0:
                # Delay slightly so layout is complete before scrolling
                GLib.timeout_add(80, self._apply_scroll, frac)

    def _apply_scroll(self, frac: float) -> bool:
        script = (
            f"(function(){{"
            f"var h=document.documentElement.scrollHeight-window.innerHeight;"
            f"if(h>0)window.scrollTo(0,{frac}*h);"
            f"}})()"
        )
        self._webview.evaluate_javascript(
            script, -1, None, None, None, None, None
        )
        return bool(GLib.SOURCE_REMOVE)

    @staticmethod
    def _wrap_html(body: str, theme_css: str = "") -> str:
        return (
            "<!DOCTYPE html><html><head>"
            "<meta charset='utf-8'>"
            f"<style>{theme_css}</style>"
            "<style>"
            "body { font-family: var(--font-sans, Arimo, sans-serif);"
            " color: var(--color-fg, #333);"
            " background: var(--color-bg, #fff);"
            " max-width: 72ch; margin: 2em auto; line-height: 1.6; }"
            "a { color: var(--color-link, #268bd2); }"
            "code { font-family: var(--font-mono, Cousine, monospace);"
            " background: var(--color-code-bg, #f4f4f4);"
            " color: var(--color-code-fg, #333);"
            " padding: 0.1em 0.3em; border-radius: 3px; }"
            "pre code { display: block; padding: 1em; overflow-x: auto; }"
            "table { border-collapse: collapse; }"
            "th, td { border: 1px solid var(--color-border, #ccc);"
            " padding: 0.4em 0.8em; }"
            "</style>"
            "</head><body>"
            f"{body}"
            "</body></html>"
        )
