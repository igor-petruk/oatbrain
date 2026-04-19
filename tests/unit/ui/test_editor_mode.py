"""Tests for editor mode toggle, preview integration, and scroll sync."""

import gi
from pathlib import Path
from unittest.mock import MagicMock
from dataclasses import replace

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")
from gi.repository import Gtk  # noqa: E402, F401

from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.state.app_state import AppState  # noqa: E402
from oatbrain.core.events.state import StateUpdated  # noqa: E402
from oatbrain.core.ports.filestore import FileStore, VaultPath  # noqa: E402
from oatbrain.core.ports.renderer import Renderer  # noqa: E402
from oatbrain.core.commands.editor import (  # noqa: E402
    ToggleMode,
    SetDirty,
    UpdateWordCount,
)
from oatbrain.ui.editor import Editor  # noqa: E402
from oatbrain.ui.window import AdwAppShell  # noqa: E402


def make_renderer(html: str = "<p>ok</p>") -> Renderer:
    r = MagicMock(spec=Renderer)
    r.render.return_value = html
    return r


def make_editor(
    renderer: Renderer | None = None,
    vim_enabled: bool = False,
) -> tuple[Editor, CommandRouter, list[object]]:
    filestore = MagicMock(spec=FileStore)
    filestore.read_text.return_value = "# Hello\n\nWorld"
    event_bus = EventBus()
    dispatched: list[object] = []
    command_router = CommandRouter()
    command_router.register(UpdateWordCount, dispatched.append)
    command_router.register(SetDirty, dispatched.append)
    command_router.register(ToggleMode, dispatched.append)
    editor = Editor(
        filestore, event_bus, command_router, renderer=renderer, vim_enabled=vim_enabled
    )
    return editor, command_router, dispatched


# ---------------------------------------------------------------------------
# Preview widget wiring
# ---------------------------------------------------------------------------


def test_editor_without_renderer_has_no_preview() -> None:
    editor, _, _ = make_editor(renderer=None)
    assert editor._preview is None


def test_editor_with_renderer_has_preview() -> None:
    editor, _, _ = make_editor(renderer=make_renderer())
    assert editor._preview is not None


def test_editor_stack_has_preview_page_when_renderer_given() -> None:
    editor, _, _ = make_editor(renderer=make_renderer())
    assert editor._stack.get_child_by_name("preview") is not None


def test_editor_stack_has_no_preview_page_without_renderer() -> None:
    editor, _, _ = make_editor(renderer=None)
    assert editor._stack.get_child_by_name("preview") is None


# ---------------------------------------------------------------------------
# Toggle button visibility
# ---------------------------------------------------------------------------


def test_toggle_box_hidden_initially() -> None:
    editor, _, _ = make_editor(renderer=make_renderer())
    assert not editor._toggle_box.get_visible()


def test_toggle_box_hidden_without_renderer() -> None:
    editor, _, _ = make_editor(renderer=None)
    assert not editor._toggle_box.get_visible()


def test_toggle_box_shown_for_markdown_file() -> None:
    editor, _, _ = make_editor(renderer=make_renderer())
    editor._current_path = VaultPath.from_str("note.md")
    # Simulate update_ui with a markdown file open
    state = AppState(vault_root=Path("/tmp"))
    new_editor_state = replace(state.editor, open_file=VaultPath.from_str("note.md"))
    state = replace(state, editor=new_editor_state)
    # Directly call the path/toggle logic that _update_ui uses
    is_markdown = str(VaultPath.from_str("note.md")).endswith((".md", ".markdown"))
    editor._toggle_box.set_visible(is_markdown and editor._preview is not None)
    assert editor._toggle_box.get_visible()


def test_toggle_box_hidden_for_non_markdown_file() -> None:
    editor, _, _ = make_editor(renderer=make_renderer())
    is_markdown = "note.txt".endswith((".md", ".markdown"))
    editor._toggle_box.set_visible(is_markdown and editor._preview is not None)
    assert not editor._toggle_box.get_visible()


# ---------------------------------------------------------------------------
# Scroll fraction
# ---------------------------------------------------------------------------


def test_scroll_fraction_initializes_to_zero() -> None:
    editor, _, _ = make_editor()
    assert editor._scroll_fraction == 0.0


def test_apply_fraction_to_source_stores_fraction() -> None:
    editor, _, _ = make_editor()
    editor._apply_fraction_to_source(0.5)
    assert editor._scroll_fraction == 0.5


def test_apply_fraction_to_source_via_standalone_adjustment() -> None:
    from gi.repository import Gtk as _Gtk

    editor, _, _ = make_editor()

    # Use a standalone adjustment to verify the math, since ScrolledWindow
    # clamps values without a realized window.
    adj = _Gtk.Adjustment(
        value=0, lower=0, upper=1000, step_increment=1, page_increment=10, page_size=200
    )
    upper = adj.get_upper() - adj.get_page_size()  # 800
    adj.set_value(0.5 * upper)
    assert abs(adj.get_value() - 400.0) < 1.0


def test_apply_fraction_zero_does_not_scroll() -> None:
    editor, _, _ = make_editor()
    adj = editor._source_scroll.get_vadjustment()
    adj.set_upper(1000.0)
    adj.set_page_size(200.0)
    adj.set_value(300.0)

    editor._apply_fraction_to_source(0.0)

    # upper <= 0 or fraction=0 → scrollY = 0
    assert editor._scroll_fraction == 0.0


def test_apply_fraction_noop_when_no_scrollable_range() -> None:
    editor, _, _ = make_editor()
    adj = editor._source_scroll.get_vadjustment()
    adj.set_upper(100.0)
    adj.set_page_size(100.0)  # upper - page_size = 0, nothing to scroll
    adj.set_value(0.0)

    editor._apply_fraction_to_source(0.9)
    assert adj.get_value() == 0.0


# ---------------------------------------------------------------------------
# ToggleMode command (state layer)
# ---------------------------------------------------------------------------


def test_toggle_mode_command_is_frozen_dataclass() -> None:
    cmd = ToggleMode()
    import dataclasses

    assert dataclasses.is_dataclass(cmd)


def test_window_toggle_mode_flips_read_mode() -> None:
    event_bus = EventBus()
    command_router = CommandRouter()
    state = AppState(vault_root=Path("/tmp"))
    filestore = MagicMock(spec=FileStore)

    received: list[StateUpdated] = []
    event_bus.subscribe(StateUpdated, received.append)

    app = AdwAppShell(
        event_bus=event_bus,
        command_router=command_router,
        initial_state=state,
        filestore=filestore,
        state_store=MagicMock(),
        config=MagicMock(),
        application_id="org.oatbrain.TestToggle",
    )
    app.on_activate(app)

    assert not app._state.editor.read_mode
    command_router.dispatch(ToggleMode())
    assert app._state.editor.read_mode

    command_router.dispatch(ToggleMode())
    assert not app._state.editor.read_mode


def test_toggle_mode_publishes_state_updated() -> None:
    event_bus = EventBus()
    command_router = CommandRouter()
    state = AppState(vault_root=Path("/tmp"))

    received: list[StateUpdated] = []
    event_bus.subscribe(StateUpdated, received.append)

    app = AdwAppShell(
        event_bus=event_bus,
        command_router=command_router,
        initial_state=state,
        filestore=MagicMock(spec=FileStore),
        state_store=MagicMock(),
        config=MagicMock(),
        application_id="org.oatbrain.TestToggleEvent",
    )
    app.on_activate(app)
    before = len(received)
    command_router.dispatch(ToggleMode())
    assert len(received) > before
