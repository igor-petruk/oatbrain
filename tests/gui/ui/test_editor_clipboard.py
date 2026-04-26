import gi
from unittest.mock import MagicMock

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk  # noqa: E402

from oatbrain.ui.editor import Editor  # noqa: E402
from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.ports.env import Env  # noqa: E402


def test_editor_copy_keybinding() -> None:
    """
    Verifies that Ctrl+Shift+C triggers clipboard copy.
    """
    bus = EventBus()
    router = CommandRouter()
    env = MagicMock(spec=Env)

    editor = Editor(
        filestore=MagicMock(),
        event_bus=bus,
        command_router=router,
        env=env,
        vim_enabled=False,
    )

    # Mock emit to see if it's called
    editor.view.emit = MagicMock()

    ctrl_shift = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK

    # Try with Gdk.KEY_c (lowercase)
    handled = editor._on_key_pressed(None, Gdk.KEY_c, 0, ctrl_shift)
    assert handled is True
    editor.view.emit.assert_called_with("copy-clipboard")

    # Try with Gdk.KEY_C (uppercase)
    editor.view.emit.reset_mock()
    handled_V = editor._on_key_pressed(None, Gdk.KEY_C, 0, ctrl_shift)
    assert handled_V is True
    editor.view.emit.assert_called_with("copy-clipboard")


def test_editor_paste_keybinding() -> None:
    """
    Verifies that Ctrl+Shift+V triggers clipboard paste.
    """
    bus = EventBus()
    router = CommandRouter()
    env = MagicMock(spec=Env)

    editor = Editor(
        filestore=MagicMock(),
        event_bus=bus,
        command_router=router,
        env=env,
        vim_enabled=False,
    )

    # Mock emit to see if it's called
    editor.view.emit = MagicMock()

    ctrl_shift = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK

    # Try with Gdk.KEY_v (lowercase)
    handled = editor._on_key_pressed(None, Gdk.KEY_v, 0, ctrl_shift)
    assert handled is True
    editor.view.emit.assert_called_with("paste-clipboard")

    # Try with Gdk.KEY_V (uppercase)
    editor.view.emit.reset_mock()
    handled_V = editor._on_key_pressed(None, Gdk.KEY_V, 0, ctrl_shift)
    assert handled_V is True
    editor.view.emit.assert_called_with("paste-clipboard")
