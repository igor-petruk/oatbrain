from typing import Any, Dict, List
from gi.repository import Gtk, Adw, Gdk
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
            "/": [
                "/explain this code",
                "/fix the bug",
                "/refactor this function",
            ],
            "!": ["ls -la", "git status", "make build"],
        }
        self._current_prefix = ""

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.box.set_margin_top(12)
        self.box.set_margin_bottom(12)
        self.box.set_margin_start(12)
        self.box.set_margin_end(12)
        self.set_child(self.box)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text(
            "Search files or type: # tags, % text, > commands, / AI command, ! shell"
        )
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.box.append(self.search_entry)

        # Search entry key handling for navigation
        self.search_key_controller = Gtk.EventControllerKey()
        self.search_key_controller.connect("key-pressed", self._on_search_key_pressed)
        self.search_entry.add_controller(self.search_key_controller)

        # List view setup
        self.model = Gtk.StringList.new([])
        self.selection_model = Gtk.SingleSelection.new(self.model)
        self.list_view = Gtk.ListView()
        self.list_view.set_model(self.selection_model)

        # Redirect typing from list back to search entry
        self.list_key_controller = Gtk.EventControllerKey()
        self.list_key_controller.connect("key-pressed", self._on_list_key_pressed)
        self.list_view.add_controller(self.list_key_controller)

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
        self._update_list("", "")

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

    def _on_search_key_pressed(
        self,
        controller: Gtk.EventControllerKey,
        keyval: int,
        keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        # Move selection in the list
        if keyval == Gdk.KEY_Down or (
            state & Gdk.ModifierType.CONTROL_MASK and keyval in (Gdk.KEY_n, Gdk.KEY_j)
        ):
            curr = self.selection_model.get_selected()
            if curr < self.model.get_n_items() - 1:
                self.selection_model.set_selected(curr + 1)
                self.list_view.scroll_to(curr + 1, Gtk.ListScrollFlags.NONE, None)
            return True
        if keyval == Gdk.KEY_Up or (
            state & Gdk.ModifierType.CONTROL_MASK and keyval in (Gdk.KEY_p, Gdk.KEY_k)
        ):
            curr = self.selection_model.get_selected()
            if curr > 0:
                self.selection_model.set_selected(curr - 1)
                self.list_view.scroll_to(curr - 1, Gtk.ListScrollFlags.NONE, None)
            return True
        return False

    def _on_list_key_pressed(
        self,
        controller: Gtk.EventControllerKey,
        keyval: int,
        keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        # If it's not navigation or execution, go back to search
        allowed_keys = (
            Gdk.KEY_Up,
            Gdk.KEY_Down,
            Gdk.KEY_Return,
            Gdk.KEY_KP_Enter,
            Gdk.KEY_Tab,
            Gdk.KEY_Page_Up,
            Gdk.KEY_Page_Down,
            Gdk.KEY_Home,
            Gdk.KEY_End,
        )
        if keyval in allowed_keys or (state & Gdk.ModifierType.CONTROL_MASK):
            return False

        self.search_entry.grab_focus()
        return False

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        text = entry.get_text()
        prefix = ""
        if text.startswith(("#", "%", ">", "/", "!")):
            prefix = text[0]
            query = text[1:]
        else:
            query = text

        if prefix != self._current_prefix:
            self._current_prefix = prefix

        self._update_list(prefix, query)

    def _update_list(self, prefix: str, query: str) -> None:
        from oatbrain.core.search import filter_and_rank

        items = self._mock_data.get(prefix, [])
        filtered_items = filter_and_rank(query, items)

        # Clear model
        while self.model.get_n_items() > 0:
            self.model.remove(0)
        # Add items
        for item in filtered_items:
            self.model.append(item)

        # Auto-select first item
        if self.model.get_n_items() > 0:
            self.selection_model.set_selected(0)
