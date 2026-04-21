import gi
from pathlib import Path
from unittest.mock import MagicMock

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Vte", "3.91")
from gi.repository import Gdk, GLib  # noqa: E402

from oatbrain.ui.terminal import Terminal  # noqa: E402

def test_terminal_paste_keybinding() -> None:
    """
    Verifies that Ctrl+Shift+V triggers clipboard paste.
    """
    vault_root = Path("/tmp")
    terminal = Terminal(vault_root=vault_root)
    
    # Mock _paste_from_clipboard to see if it's called
    terminal._paste_from_clipboard = MagicMock()
    
    ctrl_shift = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
    
    # Try with Gdk.KEY_v (lowercase)
    handled = terminal._on_key_pressed(None, Gdk.KEY_v, 0, ctrl_shift)
    assert handled is True
    
    # Try with Gdk.KEY_V (uppercase)
    handled_V = terminal._on_key_pressed(None, Gdk.KEY_V, 0, ctrl_shift)
    assert handled_V is True
    
    assert terminal._paste_from_clipboard.call_count == 2

def test_terminal_copy_keybinding() -> None:
    """
    Verifies that Ctrl+Shift+C triggers clipboard copy.
    """
    vault_root = Path("/tmp")
    terminal = Terminal(vault_root=vault_root)
    
    # Mock _copy_to_clipboard to see if it's called
    terminal._copy_to_clipboard = MagicMock()
    
    ctrl_shift = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
    
    # Try with Gdk.KEY_c (lowercase)
    handled = terminal._on_key_pressed(None, Gdk.KEY_c, 0, ctrl_shift)
    assert handled is True
    
    # Try with Gdk.KEY_C (uppercase)
    handled_C = terminal._on_key_pressed(None, Gdk.KEY_C, 0, ctrl_shift)
    assert handled_C is True
    
    assert terminal._copy_to_clipboard.call_count == 2

def test_terminal_copy_execution() -> None:
    """
    Verifies that _copy_to_clipboard calls vte.copy_clipboard.
    """
    vault_root = Path("/tmp")
    terminal = Terminal(vault_root=vault_root)
    
    terminal._vte = MagicMock()
    terminal._copy_to_clipboard()
    
    assert terminal._vte.copy_clipboard.called

def test_terminal_paste_execution() -> None:
    """
    Verifies that _paste_from_clipboard actually feeds text to the terminal.
    """
    vault_root = Path("/tmp")
    terminal = Terminal(vault_root=vault_root)
    
    test_text = "Pasted Text Content"
    
    # Mock clipboard
    display = Gdk.Display.get_default()
    clipboard = display.get_clipboard()
    clipboard.set_content(Gdk.ContentProvider.new_for_value(test_text))
    
    # Mock _feed to capture output
    terminal._feed = MagicMock()
    
    terminal._paste_from_clipboard()
    
    # Pump loop to allow async read to complete
    context = GLib.MainContext.default()
    for _ in range(20):
        if terminal._feed.called:
            break
        context.iteration(False)
        GLib.usleep(10000)
        
    assert terminal._feed.called
    terminal._feed.assert_called_with(test_text)
