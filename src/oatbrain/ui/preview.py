import gi
from typing import Callable, Optional

gi.require_version("WebKit", "6.0")
gi.require_version("Gtk", "4.0")
from gi.repository import WebKit, Gio, GLib, Gtk, Gdk  # noqa: E402

from oatbrain.core.ports.renderer import Renderer  # noqa: E402
from oatbrain.core.ports.filestore import VaultPath  # noqa: E402
from oatbrain.core.ports.env import Env  # noqa: E402


class Preview:
    """Read-mode pane: renders Markdown to HTML via WebKitWebView (SPEC §11)."""

    def __init__(self, renderer: Renderer, env: Env) -> None:
        self._renderer = renderer
        self._env = env
        self._pending_fraction: Optional[float] = None
        self.on_wikilink_clicked: Optional[Callable[[str], None]] = None

        # --- Dual WebView setup for flicker-free swaps (Option B) ---
        self._stack = Gtk.Stack()
        self._stack.set_hexpand(True)
        self._stack.set_vexpand(True)
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_transition_duration(50)  # Very fast crossfade

        self._wv1 = self._create_webview("wv1")
        self._wv2 = self._create_webview("wv2")

        self._stack.add_named(self._wv1, "wv1")
        self._stack.add_named(self._wv2, "wv2")

        # Start with wv1
        self._active_wv = self._wv1
        self._stack.set_visible_child_name("wv1")

        self.widget = self._stack

    def _create_webview(self, name: str) -> WebKit.WebView:
        wv = WebKit.WebView()
        wv.set_hexpand(True)
        wv.set_vexpand(True)
        # Use transparent background to avoid white flashes
        wv.set_background_color(Gdk.RGBA(0, 0, 0, 0))
        wv.connect("load-changed", self._on_load_changed, name)
        wv.connect("decide-policy", self._on_decide_policy)
        return wv

    def _on_decide_policy(
        self,
        webview: WebKit.WebView,
        decision: WebKit.PolicyDecision,
        decision_type: WebKit.PolicyDecisionType,
    ) -> bool:
        if decision_type in (
            WebKit.PolicyDecisionType.NAVIGATION_ACTION,
            WebKit.PolicyDecisionType.NEW_WINDOW_ACTION,
        ):
            navigation_action = decision.get_navigation_action()
            request = navigation_action.get_request()
            uri = request.get_uri() if request else "N/A"

            if navigation_action.is_user_gesture() and uri:
                if uri.startswith("http"):
                    import subprocess

                    subprocess.Popen(["xdg-open", uri])
                    decision.ignore()
                    return True
                elif uri.startswith("oatbrain://vault/"):
                    from urllib.parse import unquote

                    target = unquote(uri[len("oatbrain://vault/") :])
                    if self.on_wikilink_clicked:
                        self.on_wikilink_clicked(target)
                    decision.ignore()
                    return True
        return False

    def render(
        self,
        markdown: str,
        from_path: VaultPath,
        scroll_to: float = 0.0,
        theme_css: str = "",
        theme_id: str = "solarized-light",
    ) -> None:
        self._pending_fraction = scroll_to
        html = self._renderer.render(markdown, from_path)

        # Check for cached Mermaid library (§15.1)
        mermaid_path = self._env.get_xdg_cache_home() / "oatbrain" / "mermaid.min.js"
        mermaid_js = str(mermaid_path) if mermaid_path.exists() else None

        # Render to the INACTIVE webview
        self._inactive_wv = self._wv2 if self._active_wv == self._wv1 else self._wv1
        self._inactive_wv.load_html(
            self._wrap_html(html, theme_css, mermaid_js, theme_id), "file:///"
        )

    def get_scroll_fraction(self, callback: Callable[[float], None]) -> None:
        script = (
            "(function(){"
            "var h=document.documentElement.scrollHeight-window.innerHeight;"
            "return h>0?window.scrollY/h:0;"
            "})()"
        )

        def _on_result(_wv: WebKit.WebView, result: Gio.AsyncResult, _ud: None) -> None:
            try:
                # Always evaluate on the ACTIVE webview
                js_val = self._active_wv.evaluate_javascript_finish(result)
                fraction = js_val.to_double() if js_val is not None else 0.0
            except Exception:
                fraction = 0.0
            callback(fraction)

        self._active_wv.evaluate_javascript(
            script, -1, None, None, None, _on_result, None
        )

    def clear(self) -> None:
        self._wv1.load_html("", "file:///")
        self._wv2.load_html("", "file:///")

    def _on_load_changed(
        self, wv: WebKit.WebView, event: WebKit.LoadEvent, name: str
    ) -> None:
        if event == WebKit.LoadEvent.FINISHED:
            # If this is the one we were loading in the background, swap it in
            if wv != self._active_wv:
                self._active_wv = wv
                self._stack.set_visible_child_name(name)

            if self._pending_fraction is not None:
                frac = self._pending_fraction
                self._pending_fraction = None
                if frac > 0.0:
                    GLib.timeout_add(80, self._apply_scroll, wv, frac)

    def _apply_scroll(self, wv: WebKit.WebView, frac: float) -> bool:
        script = (
            f"(function(){{"
            f"var h=document.documentElement.scrollHeight-window.innerHeight;"
            f"if(h>0)window.scrollTo(0,{frac}*h);"
            f"}})()"
        )
        wv.evaluate_javascript(script, -1, None, None, None, None, None)
        return bool(GLib.SOURCE_REMOVE)

    @staticmethod
    def _wrap_html(
        body: str,
        theme_css: str = "",
        mermaid_js: Optional[str] = None,
        theme_id: str = "solarized-light",
    ) -> str:
        mermaid_script = ""
        mermaid_modal = ""
        if mermaid_js:
            mermaid_theme = "dark" if "dark" in theme_id.lower() else "default"
            mermaid_script = (
                f'<script src="file://{mermaid_js}"></script>'
                f"<script>mermaid.initialize({{"
                f"startOnLoad:true, theme:'{mermaid_theme}'}});"
                "</script>"
                "<script>"
                "function expandMermaid(btn) {"
                "  var c = btn.parentElement;"
                "  var m = c.querySelector('.mermaid');"
                "  var s = m.innerHTML;"
                "  var mod = document.getElementById('mermaid-modal');"
                "  var mc = document.getElementById("
                "'mermaid-modal-content');"
                "  mc.innerHTML = s;"
                "  mod.style.display = 'block';"
                "}"
                "function closeMermaidModal() {"
                "  document.getElementById('mermaid-modal').style.display = "
                "'none';"
                "}"
                "</script>"
            )
            mermaid_modal = (
                '<div id="mermaid-modal" class="mermaid-modal">'
                '<span class="mermaid-modal-close" '
                'onclick="closeMermaidModal()">&times;</span>'
                '<div id="mermaid-modal-content" class="mermaid-modal-content"></div>'
                "</div>"
            )

        return (
            "<!DOCTYPE html><html><head>"
            "<meta charset='utf-8'>"
            f"<style>{theme_css}</style>"
            "<style>"
            "body { font-family: var(--font-sans, Arimo, sans-serif);"
            " color: var(--color-fg, #1a1a1a);"
            " background: var(--color-bg, #fff);"
            " max-width: 72ch; margin: 2em auto; padding: 0 1.5em; line-height: 1.6; }"
            "a { color: var(--color-link, #268bd2); }"
            "code { font-family: var(--font-mono, Cousine, monospace);"
            " background: var(--color-code-bg, #f4f4f4);"
            " color: var(--color-code-fg, #333);"
            " padding: 0.1em 0.3em; border-radius: 3px; }"
            "pre code { display: block; padding: 1em; overflow-x: auto; }"
            "table { border-collapse: collapse; }"
            "th, td { border: 1px solid var(--color-border, #ccc);"
            " padding: 0.4em 0.8em; }"
            "a.wikilink.broken { color: var(--color-link-broken, #f44336); "
            "text-decoration: underline dashed; }"
            "mark { background: var(--color-bg-alt, #fff59d); "
            "color: var(--color-fg, #000); padding: 0 2px; }"
            ".callout { margin: 1em 0; padding: 0.8em; border-radius: 4px; "
            "border-left: 4px solid var(--color-border, #ccc); "
            "background: var(--color-bg-alt, rgba(0,0,0,0.05)); }"
            ".callout-title { font-weight: bold; margin-bottom: 0.4em; "
            "display: flex; align-items: center; gap: 8px; }"
            "details.callout summary { cursor: pointer; list-style: none; }"
            "details.callout summary::-webkit-details-marker { display: none; }"
            "details.callout summary::before { content: '▶'; "
            "display: inline-block; transition: transform 0.1s; "
            "font-size: 0.8em; }"
            "details.callout[open] summary::before { transform: rotate(90deg); }"
            ".callout-info { border-left-color: var(--color-accent, #2196f3); }"
            ".callout-warning { border-left-color: #ff9800; }"
            ".callout-error { border-left-color: #f44336; }"
            ".callout-note { border-left-color: #9e9e9e; }"
            ".mermaid-container { "
            "position: relative; "
            "margin: 1.5em auto; "
            "display: block; "
            "text-align: center; "
            "width: 100%; }"
            ".mermaid { background: var(--color-bg); border-radius: 4px; padding: 1em; "
            "display: block; width: 100%; box-sizing: border-box; }"
            ".mermaid svg { display: block; width: 100%; height: auto; }"
            ".mermaid-expand-btn { position: absolute; top: 8px; right: 8px; "
            "background: var(--color-bg-alt, rgba(0,0,0,0.05)); "
            "color: var(--color-fg-muted); "
            "border: 1px solid var(--color-border); border-radius: 4px; "
            "padding: 2px 6px; cursor: pointer; opacity: 0; "
            "transition: opacity 0.2s; z-index: 10; font-size: 14px; }"
            ".mermaid-container:hover .mermaid-expand-btn { opacity: 1; }"
            ".mermaid-modal { display: none; position: fixed; z-index: 9999; "
            "left: 0; top: 0; width: 100%; height: 100%; "
            "background-color: var(--color-bg, #fff); overflow: auto; }"
            ".mermaid-modal-content { "
            "display: flex; "
            "justify-content: center; "
            "min-height: 100%; "
            "padding: 60px 20px 20px 20px; "
            "box-sizing: border-box; }"
            ".mermaid-modal-content svg { "
            "width: auto; "
            "height: auto; "
            "max-width: 100%; "
            "margin: 0 auto; }"
            ".mermaid-modal-close { "
            "position: fixed; "
            "top: 60px; "
            "right: 25px; "
            "color: var(--color-fg, #000); "
            "font-size: 35px; "
            "font-weight: bold; "
            "cursor: pointer; "
            "z-index: 10000; }"
            "</style>"
            f"{mermaid_script}"
            "</head><body>"
            f"{body}"
            f"{mermaid_modal}"
            "</body></html>"
        )
