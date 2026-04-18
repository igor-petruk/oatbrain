from gi.repository import Gtk, Adw
from ..core.ports.state import AppState

class Palette(Adw.Window):
    def __init__(self, state: AppState):
        super().__init__()
        self.set_title("Palette")
        self.set_default_size(600, 400)
        self.set_modal(True)
        
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.set_content(self.box)
        
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.box.append(self.search_entry)
        
        self.list_view = Gtk.ListView()
        self.box.append(self.list_view)
        
        self.connect("key-pressed", self._on_key_pressed)
        
    def _on_search_changed(self, entry: Gtk.SearchEntry):
        text = entry.get_text()
        print(f"Searching for: {text}")
        
    def _on_key_pressed(self, widget, keyval, keycode, state):
        if keyval == Gtk.keysyms.Escape:
            self.close()
            return True
        return False
