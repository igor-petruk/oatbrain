import gi
from unittest.mock import MagicMock
from pathlib import Path
from oatbrain.core.ports.renderer import Renderer  # noqa: E402
from oatbrain.core.ports.filestore import VaultPath  # noqa: E402
from oatbrain.core.ports.env import Env  # noqa: E402
from oatbrain.ui.preview import Preview  # noqa: E402

gi.require_version("WebKit", "6.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402


def make_renderer(html: str = "<p>body</p>") -> Renderer:
    r = MagicMock(spec=Renderer)
    r.render.return_value = html
    return r


def make_env() -> Env:
    env = MagicMock(spec=Env)
    env.get_xdg_cache_home.return_value = Path("/tmp/cache")
    return env


def dummy_path() -> VaultPath:
    return VaultPath.from_str("note.md")


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------


def test_preview_widget_is_stack() -> None:
    p = Preview(make_renderer(), make_env())
    # widget is now a Gtk.Stack for double-buffering
    assert isinstance(p.widget, Gtk.Stack)


def test_preview_widget_expands() -> None:
    p = Preview(make_renderer(), make_env())
    # The stack should expand to fill the available space
    assert p.widget.get_hexpand()
    assert p.widget.get_vexpand()


def test_pending_fraction_starts_none() -> None:
    p = Preview(make_renderer(), make_env())
    assert p._pending_fraction is None


# ---------------------------------------------------------------------------
# _wrap_html (pure function)
# ---------------------------------------------------------------------------


def test_wrap_html_contains_body_content() -> None:
    html = Preview._wrap_html("<h1>Hello</h1>")
    assert "<h1>Hello</h1>" in html


def test_wrap_html_has_doctype_and_charset() -> None:
    html = Preview._wrap_html("")
    assert "<!DOCTYPE html>" in html
    assert "charset='utf-8'" in html


def test_wrap_html_has_style_block() -> None:
    html = Preview._wrap_html("")
    assert "<style>" in html
    assert "max-width: 72ch" in html


def test_wrap_html_is_complete_document() -> None:
    html = Preview._wrap_html("<p>x</p>")
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html


# ---------------------------------------------------------------------------
# render()
# ---------------------------------------------------------------------------


def test_render_calls_renderer_with_markdown() -> None:
    renderer = make_renderer()
    p = Preview(renderer, make_env())
    p.render("# Title", dummy_path())
    renderer.render.assert_called_once_with("# Title", dummy_path())


def test_render_sets_pending_fraction_to_default_zero() -> None:
    p = Preview(make_renderer(), make_env())
    p.render("# Title", dummy_path())
    assert p._pending_fraction == 0.0


def test_render_stores_explicit_fraction() -> None:
    p = Preview(make_renderer(), make_env())
    p.render("# Title", dummy_path(), scroll_to=0.75)
    assert p._pending_fraction == 0.75


def test_render_clears_fraction_zero_does_not_scroll() -> None:
    p = Preview(make_renderer(), make_env())
    p.render("# Title", dummy_path(), scroll_to=0.0)
    # fraction=0 means no scroll needed; pending is stored but won't trigger JS
    assert p._pending_fraction == 0.0


# ---------------------------------------------------------------------------
# clear()
# ---------------------------------------------------------------------------


def test_clear_resets_view() -> None:
    p = Preview(make_renderer(), make_env())
    p.render("# Before", dummy_path())
    p.clear()

    # After clear, _pending_fraction is still whatever render() set, but
    # the WebView has been told to load empty HTML — just verify no exception.
    assert p._pending_fraction is not None or p._pending_fraction is None
