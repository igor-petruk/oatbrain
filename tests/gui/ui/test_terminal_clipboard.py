import gi
import base64
from pathlib import Path
from unittest.mock import MagicMock

gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")
from gi.repository import Gtk, Vte, Gdk, GLib  # noqa: E402

from oatbrain.ui.terminal import Terminal  # noqa: E402


def test_terminal_osc52_clipboard_integration() -> None:
    """
    Verifies that the Terminal correctly handles OSC 52 escape sequences
    by updating the system clipboard.
    """
    # Use a dummy vault root
    vault_root = Path("/tmp")
    
    # Instantiate Terminal
    terminal = Terminal(vault_root=vault_root)
    
    display = Gdk.Display.get_default()
    if not display:
        return
        
    clipboard = display.get_clipboard()
    
    test_text = "Hello from OSC 52 GUI Test"
    b64_payload = base64.b64encode(test_text.encode()).decode()
    full_payload = f"c;{b64_payload}"
    
    mock_vte = MagicMock(spec=Vte.Terminal)
    mock_vte.get_termprop_string.return_value = full_payload
    
    # Call the handler
    terminal._on_termprop_changed(mock_vte, "clipboard")
    
    # Check the clipboard text.
    # We use a loop to wait for the content to be set and readable.
    result_data = {"text": None, "done": False}

    def on_text_read(clipboard, result, data):
        try:
            data["text"] = clipboard.read_text_finish(result)
        except Exception as e:
            print(f"Read error: {e}")
        data["done"] = True

    # Pump loop until we can read back the text
    # Clipboard operations in X11/Headless can be flaky, so we retry a bit.
    context = GLib.MainContext.default()
    for _ in range(20):
        clipboard.read_text_async(None, on_text_read, result_data)
        
        # Wait up to 200ms for this attempt
        for _ in range(10):
            if result_data["done"]:
                break
            context.iteration(False)
            GLib.usleep(10000)
            
        if result_data["text"] == test_text:
            break
        result_data["done"] = False
        context.iteration(True)

    assert result_data["text"] == test_text


def test_terminal_osc52_primary_selection() -> None:
    """
    Verifies that the Terminal handles OSC 52 targeting the primary selection.
    """
    vault_root = Path("/tmp")
    terminal = Terminal(vault_root=vault_root)
    display = Gdk.Display.get_default()
    if not display:
        return
        
    primary_clipboard = display.get_primary_clipboard()
    
    test_text = "Primary Selection Text"
    b64_payload = base64.b64encode(test_text.encode()).decode()
    full_payload = f"p;{b64_payload}"
    
    mock_vte = MagicMock(spec=Vte.Terminal)
    mock_vte.get_termprop_string.return_value = full_payload
    
    terminal._on_termprop_changed(mock_vte, "clipboard")
    
    result_data = {"text": None, "done": False}
    def on_text_read(clipboard, result, data):
        try:
            data["text"] = clipboard.read_text_finish(result)
        except:
            pass
        data["done"] = True
    
    context = GLib.MainContext.default()
    for _ in range(20):
        primary_clipboard.read_text_async(None, on_text_read, result_data)
        for _ in range(10):
            if result_data["done"]:
                break
            context.iteration(False)
            GLib.usleep(10000)
        if result_data["text"] == test_text:
            break
        result_data["done"] = False
        context.iteration(True)

    assert result_data["text"] == test_text
