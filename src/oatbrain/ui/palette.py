from gi.repository import Gtk, Adw, Gdk
from ..core.ports.state import AppState

class Palette(Adw.Window):
    def __init__(self, state: AppState, parent_window: Gtk.Window):
        super().__init__(
            transient_for=parent_window,
            modal=True,
            destroy_with_parent=True,
            title="Palette"
        )
        self.set_default_size(600, 400)
        
        # Explicitly center on parent (GtkWindow method)
        self.set_transient_for(parent_window)
        self.set_modal(True)
        # In Gtk4, set_decorated=True is default, but let's ensure it's not a utility window
        
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.set_content(self.box)
        
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.box.append(self.search_entry)
        
        self.list_view = Gtk.ListView()
        self.box.append(self.list_view)
        
        self.key_controller = Gtk.EventControllerKey()
        self.key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(self.key_controller)
        self.search_entry.grab_focus()
        
    def _on_search_changed(self, entry: Gtk.SearchEntry):
        text = entry.get_text()
        print(f"Searching for: {text}")
        
    def _on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False
