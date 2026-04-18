import gi

gi.require_version("WebKit", "6.0")
from gi.repository import WebKit  # noqa: E402

from oatbrain.core.ports.renderer import Renderer  # noqa: E402


class Preview:
    """Read-mode pane: renders Markdown to HTML via WebKitWebView (SPEC §11)."""

    def __init__(self, renderer: Renderer) -> None:
        self._renderer = renderer

        self._webview = WebKit.WebView()
        self._webview.set_hexpand(True)
        self._webview.set_vexpand(True)

        settings = self._webview.get_settings()
        settings.set_enable_javascript(False)
        settings.set_enable_write_console_messages_to_stdout(False)

        self.widget = self._webview

    def render(self, markdown: str) -> None:
        html = self._renderer.render(markdown)
        full_html = self._wrap_html(html)
        self._webview.load_html(full_html, "file:///")

    def clear(self) -> None:
        self._webview.load_html("", "file:///")

    @staticmethod
    def _wrap_html(body: str) -> str:
        return (
            "<!DOCTYPE html><html><head>"
            "<meta charset='utf-8'>"
            "<style>"
            "body { font-family: sans-serif; max-width: 72ch;"
            " margin: 2em auto; line-height: 1.6; }"
            "code { background: #f4f4f4; padding: 0.1em 0.3em;"
            " border-radius: 3px; }"
            "pre code { display: block; padding: 1em; overflow-x: auto; }"
            "table { border-collapse: collapse; } "
            "th, td { border: 1px solid #ccc; padding: 0.4em 0.8em; }"
            "</style>"
            "</head><body>"
            f"{body}"
            "</body></html>"
        )
