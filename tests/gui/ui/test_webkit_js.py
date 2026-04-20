import gi
from unittest.mock import MagicMock
from pathlib import Path

gi.require_version("WebKit", "6.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, WebKit, GLib  # noqa: E402

from oatbrain.ui.preview import Preview  # noqa: E402
from oatbrain.core.ports.renderer import Renderer  # noqa: E402
from oatbrain.core.ports.env import Env  # noqa: E402
from oatbrain.core.ports.filestore import VaultPath  # noqa: E402


def test_webkit_js_bidirectional_scroll() -> None:
    """Tests that JS scroll events in WebKit are received in Python."""
    renderer = MagicMock(spec=Renderer)
    renderer.render.return_value = (
        "<div style='height: 5000px; background: red;'>long content</div>"
    )
    env = MagicMock(spec=Env)
    env.get_xdg_cache_home.return_value = Path("/tmp/oatbrain-test-cache")

    p = Preview(renderer, env)
    win = Gtk.Window()
    win.set_child(p.widget)
    win.set_default_size(400, 400)
    win.present()

    received_fraction = -1.0
    loop = GLib.MainLoop()

    def on_scroll(frac: float) -> None:
        nonlocal received_fraction
        received_fraction = frac
        loop.quit()

    p.on_scroll = on_scroll

    def trigger_scroll(wv: WebKit.WebView, event: WebKit.LoadEvent, _name: str) -> None:
        if event == WebKit.LoadEvent.FINISHED:
            script = """
                var h = document.documentElement.scrollHeight - window.innerHeight;
                window.scrollTo(0, h * 0.5);
            """
            wv.evaluate_javascript(script, -1, None, None, None, None, None)

    p._wv1.connect("load-changed", trigger_scroll, "wv1")
    p._wv2.connect("load-changed", trigger_scroll, "wv2")

    p.render("test content", VaultPath.from_str("test.md"))

    GLib.timeout_add(2000, loop.quit)
    loop.run()
    win.destroy()

    assert received_fraction > 0.4 and received_fraction < 0.6


def test_webkit_content_injection_flicker_free() -> None:
    """Tests that body.innerHTML update works as a flicker-free optimization."""
    renderer = MagicMock(spec=Renderer)
    renderer.render.side_effect = [
        "<div id='target'>Initial</div>",
        "<div id='target'>Updated</div>",
    ]
    env = MagicMock(spec=Env)
    env.get_xdg_cache_home.return_value = Path("/tmp/oatbrain-test-cache")

    p = Preview(renderer, env)
    win = Gtk.Window()
    win.set_child(p.widget)
    win.present()

    loop = GLib.MainLoop()
    results = []

    def check_content(wv: WebKit.WebView) -> None:
        script = (
            "document.getElementById('target') ? "
            "document.getElementById('target').innerText : 'NOT_FOUND'"
        )

        def on_js_result(
            _wv: WebKit.WebView, res: gi.repository.Gio.AsyncResult, _data: None
        ) -> None:
            try:
                js_val = wv.evaluate_javascript_finish(res)
                text = js_val.to_string() if js_val else "VAL_IS_NONE"
                results.append(text)
            except Exception as e:
                results.append(f"ERROR: {e}")

            if len(results) >= 2:
                loop.quit()

        wv.evaluate_javascript(script, -1, None, None, None, on_js_result, None)

    step = 0

    def on_load_changed(
        wv: WebKit.WebView, event: WebKit.LoadEvent, _name: str
    ) -> None:
        nonlocal step
        if event == WebKit.LoadEvent.FINISHED:
            if step == 0:
                step = 1
                # First content is ready, check it
                check_content(wv)
                # Trigger second render — should use innerHTML injection on same WV
                GLib.timeout_add(
                    100,
                    lambda: p.render("test 2", VaultPath.from_str("test.md")),
                )
                # Check again after injection
                GLib.timeout_add(400, lambda: check_content(wv))

    # Connect to both as we don't know which one render() will pick first
    p._wv1.connect("load-changed", on_load_changed, "wv1")
    p._wv2.connect("load-changed", on_load_changed, "wv2")

    p.render("test 1", VaultPath.from_str("test.md"))

    GLib.timeout_add(2000, loop.quit)
    loop.run()

    win.destroy()

    assert "Initial" in results
    assert "Updated" in results
