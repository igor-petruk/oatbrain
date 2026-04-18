from gi.repository import Gtk, Adw, Gdk, Gio
from ..core.ports.state import AppState

class Palette(Gtk.Window):
    def __init__(self, state: AppState, parent_window: Gtk.Window):
        super().__init__(
            transient_for=parent_window,
            modal=True,
            destroy_with_parent=True,
            title="Palette"
        )
        self.set_default_size(600, 400)
        
        # Use a shortcut controller in CAPTURE phase to preempt SearchEntry's Esc handling
        shortcut_controller = Gtk.ShortcutController.new()
        shortcut_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        shortcut_controller.add_shortcut(Gtk.Shortcut.new(
            trigger=Gtk.ShortcutTrigger.parse_string("Escape"),
            action=Gtk.CallbackAction.new(self._on_escape)
        ))
        self.add_controller(shortcut_controller)
        
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        # Add some padding
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
        
        # Ensure focus is grabbed when the window is shown
        self.connect("map", lambda *_: self.search_entry.grab_focus())

    def _on_escape(self, widget, variant):
        self.close()
        return True
        
    def _on_search_changed(self, entry: Gtk.SearchEntry):
        text = entry.get_text()
        print(f"Searching for: {text}")

