import gi
from typing import Any, Callable, Optional

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
        self.on_zoom: Optional[Callable[[float], None]] = None
        self.on_scroll: Optional[Callable[[float], None]] = None
        self._last_rendered_html: str = ""
        self._scrolling_locked = False

        self._stack = Gtk.Stack()
        self._stack.set_hexpand(True)
        self._stack.set_vexpand(True)
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_transition_duration(50)

        self._wv1 = self._create_webview("wv1")
        self._wv2 = self._create_webview("wv2")

        self._stack.add_named(self._wv1, "wv1")
        self._stack.add_named(self._wv2, "wv2")

        self._active_wv = self._wv1
        self._stack.set_visible_child_name("wv1")

        self.widget = self._stack

    def _create_webview(self, name: str) -> WebKit.WebView:
        # Setup Content Manager for bidirectional communication
        cm = WebKit.UserContentManager()
        cm.register_script_message_handler("oatbrain")
        cm.connect("script-message-received::oatbrain", self._on_script_message)

        # Inject scroll listener
        script = WebKit.UserScript.new(
            """
            window.addEventListener('scroll', function() {
                var h = document.documentElement.scrollHeight - window.innerHeight;
                var frac = h > 0 ? window.scrollY / h : 0;
                window.webkit.messageHandlers.oatbrain.postMessage({
                    type: 'scroll',
                    fraction: frac
                });
            });
            """,
            WebKit.UserContentInjectedFrames.ALL_FRAMES,
            WebKit.UserScriptInjectionTime.END,
            None,
            None,
        )
        cm.add_script(script)

        # WebKit 6.0 constructor (GTK4 compatible)
        wv = WebKit.WebView(user_content_manager=cm)
        wv.set_hexpand(True)
        wv.set_vexpand(True)
        wv.set_background_color(Gdk.RGBA(0, 0, 0, 0))
        wv.connect("load-changed", self._on_load_changed, name)
        wv.connect("decide-policy", self._on_decide_policy)

        scroll_ctrl = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL
        )
        scroll_ctrl.connect("scroll", self._on_scroll)
        wv.add_controller(scroll_ctrl)

        return wv

    def _on_script_message(
        self,
        _cm: WebKit.UserContentManager,
        message: Any,
    ) -> None:
        try:
            # In WebKit 6.0, the message is a JSC.Value directly
            if message.is_object():
                obj = message.to_json(0)
                import json

                data = json.loads(obj)
                if data.get("type") == "scroll" and self.on_scroll:
                    if not self._scrolling_locked:
                        self.on_scroll(data.get("fraction", 0.0))
        except Exception:
            pass

    def set_zoom(self, zoom: float) -> None:
        self._wv1.set_zoom_level(zoom)
        self._wv2.set_zoom_level(zoom)

    def _on_scroll(self, ctrl: Gtk.EventControllerScroll, dx: float, dy: float) -> bool:
        event = ctrl.get_current_event()
        if not event:
            return False
        modifiers = event.get_modifier_state()
        if modifiers & Gdk.ModifierType.CONTROL_MASK:
            if self.on_zoom:
                delta = -0.1 if dy > 0 else 0.1
                self.on_zoom(delta)
                return True
        return False

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

        # Check for cached Mermaid library
        mermaid_path = self._env.get_xdg_cache_home() / "oatbrain" / "mermaid.min.js"
        mermaid_js = str(mermaid_path) if mermaid_path.exists() else None

        full_html = self._wrap_html(html, theme_css, mermaid_js, theme_id)

        # If it's the same base document, just update body to avoid flicker
        if self._last_rendered_html and len(full_html) > 0:
            if not mermaid_js:
                escaped_html = (
                    html.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
                )
                # Use surgical update via JS morphing
                script = f"""
                    (function() {{
                        const newHtml = '{escaped_html}';
                        const temp = document.createElement('div');
                        temp.innerHTML = newHtml;
                        
                        function morph(oldNode, newNode) {{
                            if (
                                oldNode.nodeType !== newNode.nodeType
                                || oldNode.tagName !== newNode.tagName
                            ) {{
                                oldNode.parentNode.replaceChild(
                                    newNode.cloneNode(true), oldNode
                                );
                                return;
                            }}
                            if (oldNode.nodeType === Node.TEXT_NODE) {{
                                if (oldNode.textContent !== newNode.textContent) {{
                                    oldNode.textContent = newNode.textContent;
                                }}
                                return;
                            }}
                            // Attributes
                            const oldAttrs = oldNode.attributes;
                            const newAttrs = newNode.attributes;
                            for (let i = 0; i < newAttrs.length; i++) {{
                                const attr = newAttrs[i];
                                if (oldNode.getAttribute(attr.name) !== attr.value) {{
                                    oldNode.setAttribute(attr.name, attr.value);
                                }}
                            }}
                            for (let i = 0; i < oldAttrs.length; i++) {{
                                const attr = oldAttrs[i];
                                if (!newNode.hasAttribute(attr.name)) {{
                                    oldNode.removeAttribute(attr.name);
                                }}
                            }}
                            // Children
                            const oldChildren = Array.from(oldNode.childNodes);
                            const newChildren = Array.from(newNode.childNodes);
                            
                            let i = 0;
                            while (i < newChildren.length) {{
                                if (i < oldChildren.length) {{
                                    morph(oldChildren[i], newChildren[i]);
                                }} else {{
                                    oldNode.appendChild(newChildren[i].cloneNode(true));
                                }}
                                i++;
                            }}
                            while (oldNode.childNodes.length > newChildren.length) {{
                                oldNode.removeChild(oldNode.lastChild);
                            }}
                        }}
                        
                        morph(document.body, temp);
                    }})();
                """
                self._active_wv.evaluate_javascript(
                    script, -1, None, None, None, None, None
                )
                self._last_rendered_html = full_html
                return

        self._last_rendered_html = full_html
        self._inactive_wv = self._wv2 if self._active_wv == self._wv1 else self._wv1
        self._inactive_wv.load_html(full_html, "file:///")

    def render_image(
        self,
        image_abs_path: str,
        theme_css: str = "",
        theme_id: str = "solarized-light",
    ) -> None:
        self._pending_fraction = None
        html = f'<img src="file://{image_abs_path}" />'
        self._inactive_wv = self._wv2 if self._active_wv == self._wv1 else self._wv1
        self._inactive_wv.load_html(
            self._wrap_html(html, theme_css, None, theme_id, is_full_page=True),
            "file:///",
        )
        self._last_rendered_html = ""

    def get_scroll_fraction(self, callback: Callable[[float], None]) -> None:
        script = (
            "(function(){"
            "var h=document.documentElement.scrollHeight-window.innerHeight;"
            "return h>0?window.scrollY/h:0;"
            "})()"
        )

        def _on_result(_wv: WebKit.WebView, result: Gio.AsyncResult, _ud: None) -> None:
            try:
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
        self._last_rendered_html = ""

    def _on_load_changed(
        self, wv: WebKit.WebView, event: WebKit.LoadEvent, name: str
    ) -> None:
        if event == WebKit.LoadEvent.FINISHED:
            if wv != self._active_wv:
                self._active_wv = wv
                self._stack.set_visible_child_name(name)

            if self._pending_fraction is not None:
                frac = self._pending_fraction
                self._pending_fraction = None
                if frac > 0.0:
                    GLib.timeout_add(80, self._apply_scroll, wv, frac)

    def _apply_scroll(self, wv: WebKit.WebView, frac: float) -> bool:
        self._scrolling_locked = True
        script = (
            f"(function(){{"
            f"var h=document.documentElement.scrollHeight-window.innerHeight;"
            f"if(h>0)window.scrollTo(0,{frac}*h);"
            f"}})()"
        )
        wv.evaluate_javascript(script, -1, None, None, None, None, None)
        GLib.timeout_add(100, self._unlock_scrolling)
        return False

    def _unlock_scrolling(self) -> bool:
        self._scrolling_locked = False
        return False

    @staticmethod
    def _get_pygments_css(theme_id: str) -> str:
        try:
            from pygments.formatters import (  # type: ignore[import-untyped]
                HtmlFormatter,
            )
            from pygments.styles import (  # type: ignore[import-untyped]
                get_style_by_name,
            )

            style_map = {
                "solarized-light": "solarized-light",
                "monokai-dark": "monokai",
                "high-contrast-dark": "monokai",
            }
            style_name = style_map.get(theme_id, "friendly")
            style = get_style_by_name(style_name)
            formatter = HtmlFormatter(style=style)
            return str(formatter.get_style_defs("pre code"))
        except (ImportError, Exception):
            return ""

    @staticmethod
    def _wrap_html(
        body: str,
        theme_css: str = "",
        mermaid_js: Optional[str] = None,
        theme_id: str = "solarized-light",
        is_full_page: bool = False,
    ) -> str:
        pygments_css = Preview._get_pygments_css(theme_id)
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
                "function expandMermaid(m) {"
                "  var s = m.innerHTML;"
                "  var mod = document.getElementById('mermaid-modal');"
                "  var mc = document.getElementById('mermaid-modal-content');"
                "  mc.innerHTML = s;"
                "  mod.style.display = 'block';"
                "}"
                "function closeMermaidModal() {"
                "  var m = document.getElementById('mermaid-modal');"
                "  if (m) m.style.display = 'none';"
                "}"
                "window.addEventListener('keydown', function(e) {"
                "  if (e.key === 'Escape') closeMermaidModal();"
                "});"
                "</script>"
            )
            mermaid_modal = (
                '<div id="mermaid-modal" class="mermaid-modal" '
                'onclick="closeMermaidModal()">'
                '<span class="mermaid-modal-close">&times;</span>'
                '<div id="mermaid-modal-content" class="mermaid-modal-content"></div>'
                "</div>"
            )

        body_style = (
            "body { font-family: var(--font-sans, Arimo, sans-serif); "
            "color: var(--color-fg, #1a1a1a); background: var(--color-bg, #fff); "
            "margin: 0; padding: 2em; display: flex; justify-content: center; "
            "align-items: flex-start; min-height: 100vh; box-sizing: border-box; }"
        )
        if not is_full_page:
            body_style = (
                "body { font-family: var(--font-sans, Arimo, sans-serif);"
                " color: var(--color-fg, #1a1a1a);"
                " background: var(--color-bg, #fff);"
                " max-width: 72ch; margin: 2em auto; padding: 0 1.5em; "
                "line-height: 1.6; }"
            )

        return (
            "<!DOCTYPE html><html><head>"
            "<meta charset='utf-8'>"
            f"<style>{theme_css}\n{pygments_css}</style>"
            "<style>"
            f"{body_style}"
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
            "img, svg { max-width: 100%; height: auto; }"
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
            "display: block; width: 100%; box-sizing: border-box; cursor: pointer; }"
            ".mermaid svg { display: block; width: 100%; height: auto; }"
            ".mermaid-modal { display: none; position: fixed; z-index: 9999; "
            "left: 0; top: 0; width: 100%; height: 100%; "
            "background-color: var(--color-bg, #fff); overflow: auto; "
            "cursor: pointer; }"
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
