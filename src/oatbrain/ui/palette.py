from typing import Any, Dict, List
from gi.repository import Gtk, Adw
from oatbrain.core.state.app_state import AppState


class Palette(Adw.Dialog):  # type: ignore[misc]
    def __init__(self, state: AppState):
        super().__init__()
        self.set_title("Palette")
        self.set_content_width(600)
        self.set_content_height(400)

        self._mock_data: Dict[str, List[str]] = {
            "": ["README.md", "PLAN.md", "SPEC.md", "src/main.py"],
            "#": ["#todo", "#work", "#personal", "#idea"],
            "%": ["Search result 1", "Search result 2", "Search result 3"],
            ">": ["Toggle Tree", "Toggle Terminal", "Set Theme: Dark", "New Note"],
            "/": ["/explain this code", "/fix the bug", "/refactor this function"],
        }
        self._current_prefix = ""

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.box.set_margin_top(12)
        self.box.set_margin_bottom(12)
        self.box.set_margin_start(12)
        self.box.set_margin_end(12)
        self.set_child(self.box)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.box.append(self.search_entry)

        # List view setup
        self.model = Gtk.StringList.new([])
        self.selection_model = Gtk.SingleSelection.new(self.model)
        self.list_view = Gtk.ListView()
        self.list_view.set_model(self.selection_model)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_list_item_setup)
        factory.connect("bind", self._on_list_item_bind)
        self.list_view.set_factory(factory)

        # Scrolled window for the list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self.list_view)
        scrolled.set_vexpand(True)
        self.box.append(scrolled)

        # Escape handling
        shortcut_controller = Gtk.ShortcutController.new()
        shortcut_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        shortcut_controller.add_shortcut(
            Gtk.Shortcut.new(
                trigger=Gtk.ShortcutTrigger.parse_string("Escape"),
                action=Gtk.CallbackAction.new(self._on_escape),
            )
        )
        self.add_controller(shortcut_controller)

        # Initial data
        self._update_list("")

        # Grabbing focus on search entry
        self.connect("map", lambda *_: self.search_entry.grab_focus())

    def _on_list_item_setup(
        self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        label = Gtk.Label(xalign=0)
        label.set_margin_start(6)
        label.set_margin_end(6)
        label.set_margin_top(4)
        label.set_margin_bottom(4)
        list_item.set_child(label)

    def _on_list_item_bind(
        self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        string_object = list_item.get_item()
        label = list_item.get_child()
        if isinstance(label, Gtk.Label) and isinstance(string_object, Gtk.StringObject):
            label.set_text(string_object.get_string())

    def _on_escape(self, widget: Gtk.Widget, variant: Any) -> bool:
        self.close()
        return True

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        text = entry.get_text()
        prefix = ""
        if text.startswith(("#", "%", ">", "/")):
            prefix = text[0]

        if prefix != self._current_prefix:
            self._current_prefix = prefix
            self._update_list(prefix)

    def _update_list(self, prefix: str) -> None:
        items = self._mock_data.get(prefix, [])
        # Clear model
        while self.model.get_n_items() > 0:
            self.model.remove(0)
        # Add items
        for item in items:
            self.model.append(item)
