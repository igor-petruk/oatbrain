from gi.repository import Gtk, Adw
from ..core.ports.state import AppState

class Palette(Adw.Dialog):
    def __init__(self, state: AppState):
        super().__init__()
        self.set_title("Palette")
        self.set_content_width(600)
        self.set_content_height(400)
        
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.box.set_margin_top(12)
        self.box.set_margin_bottom(12)
        self.box.set_margin_start(12)
        self.box.set_margin_end(12)
        self.set_child(self.box)
        
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.box.append(self.search_entry)
        
        self.list_view = Gtk.ListView()
        self.box.append(self.list_view)
        
        # In Adw.Dialog, we might still need to capture Escape if we want
        # custom behavior, but Adw.Dialog usually handles it.
        # Let's see if it works out of the box.
        # However, SearchEntry might still swallow it.
        shortcut_controller = Gtk.ShortcutController.new()
        shortcut_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        shortcut_controller.add_shortcut(Gtk.Shortcut.new(
            trigger=Gtk.ShortcutTrigger.parse_string("Escape"),
            action=Gtk.CallbackAction.new(self._on_escape)
        ))
        self.add_controller(shortcut_controller)
        
        # Grabbing focus on search entry
        self.connect("map", lambda *_: self.search_entry.grab_focus())

    def _on_escape(self, widget, variant):
        self.close()
        return True
        
    def _on_search_changed(self, entry: Gtk.SearchEntry):
        text = entry.get_text()
        print(f"Searching for: {text}")
