from typing import Any, List
from gi.repository import Gtk, Adw, Gdk
from oatbrain.core.state.app_state import AppState
from oatbrain.core.ports.config import AppConfig
from oatbrain.core.ports.filestore import FileStore, VaultPath
from oatbrain.core.bus import CommandRouter
from oatbrain.core.commands import OpenFile
from oatbrain.core.search import AICommandFetcher, filter_and_rank


class Palette(Adw.Dialog):  # type: ignore[misc]
    def __init__(
        self,
        state: AppState,
        config: AppConfig,
        filestore: FileStore,
        command_router: CommandRouter,
        initial_text: str = "",
    ):
        super().__init__()
        self.set_title("Palette")
        self.set_content_width(600)
        self.set_content_height(400)

        self._state = state
        self._config = config
        self._filestore = filestore
        self._command_router = command_router
        self._ai_fetcher = AICommandFetcher(config.palette)

        self._current_prefix = ""
        self._items: List[str] = []

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
        self.search_entry.connect("activate", self._on_execute)
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
        self.list_view.connect("activate", self._on_execute)

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

        if initial_text:
            self.search_entry.set_text(initial_text)

        # Initial data
        self._update_list()

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
        self._update_list()

    def _on_execute(self, *_: Any) -> None:
        selected_idx = self.selection_model.get_selected()
        if selected_idx == Gtk.INVALID_LIST_POSITION:
            # Maybe try to execute the query as shell command if in shell mode?
            text = self.search_entry.get_text()
            if text.startswith("!"):
                self._execute_shell(text[1:])
                self.close()
            return

        item = self.model.get_item(selected_idx)
        if not isinstance(item, Gtk.StringObject):
            return

        text = item.get_string()
        prefix = self._current_prefix

        if prefix == "" or prefix == "%" or prefix == "#":
            # Files, Text, Tags results are often file paths or contain file paths.
            # For tags/text we need to extract the path.
            path_str = text.split(":")[0] if ":" in text else text
            self._command_router.dispatch(OpenFile(VaultPath.from_str(path_str)))
        elif prefix == ">":
            # Execute app command
            for cmd_type, name in self._command_router.list_commands():
                if name == text:
                    self._command_router.dispatch(cmd_type())
                    break
        elif prefix == "/":
            self._paste_to_terminal(text)
        elif prefix == "!":
            self._execute_shell(text)

        self.close()

    def _execute_shell(self, command: str) -> None:
        # For now, we'll just print it.
        print(f"DEBUG: Executing shell command: {command}")

    def _paste_to_terminal(self, text: str) -> None:
        # For now, we'll just print it.
        print(f"DEBUG: Pasting to terminal: {text}")

    def _update_list(self) -> None:
        text = self.search_entry.get_text()
        prefix = ""
        if text.startswith(("#", "%", ">", "/", "!", "?")):
            prefix = text[0]
            query = text[1:]
        else:
            query = text

        # For files mode, we want to update items if query was empty and now isn't
        # to switch from MRU to all files.
        needs_fetch = prefix != self._current_prefix or not self._items

        if prefix == "" and not query:
            # Always show MRU when empty
            self._items = self._fetch_data(prefix)
            needs_fetch = False
        elif prefix == "" and query and not self._current_prefix:
            # Switching from MRU to all files
            needs_fetch = True

        if needs_fetch:
            self._current_prefix = prefix
            self._items = self._fetch_data(prefix)

        filtered_items = filter_and_rank(query, self._items)

        # Clear model
        while self.model.get_n_items() > 0:
            self.model.remove(0)
        # Add items
        for item in filtered_items:
            self.model.append(item)

        # Auto-select first item
        if self.model.get_n_items() > 0:
            self.selection_model.set_selected(0)

    def _fetch_data(self, prefix: str) -> List[str]:
        if prefix == "":
            # Files mode
            if not self.search_entry.get_text():
                # MRU
                return self._state.editor.mru
            else:
                # All files
                files = [
                    str(f.path) for f in self._filestore.walk(VaultPath.from_str(""))
                ]
                return files
        elif prefix == ">":
            # App commands
            return [name for _, name in self._command_router.list_commands()]
        elif prefix == "/":
            # AI commands
            return self._ai_fetcher.fetch()
        elif prefix == "!":
            # Shell commands (history deferred, using mocks for now)
            return ["ls -la", "git status", "make build"]
        elif prefix == "#":
            # Tags using ripgrep
            try:
                import subprocess

                result = subprocess.run(
                    ["rg", "--no-heading", "--column", "-o", r"#[a-zA-Z0-9_-]+", "."],
                    cwd=str(self._state.vault_root),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                # Format: path:line:col:#tag
                return result.stdout.splitlines()
            except Exception as e:
                print(f"Warning: ripgrep for tags failed: {e}")
                return []
        elif prefix == "%":
            # Full text search using ripgrep
            try:
                import subprocess

                # We don't want to fetch ALL text at once, but for FZF filter
                # we might need to. Better to use fzf's own ripgrep integration
                # if possible, but for simplicity we'll just get all lines with
                # content.
                result = subprocess.run(
                    ["rg", "--no-heading", "--line-number", "."],
                    cwd=str(self._state.vault_root),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                return result.stdout.splitlines()
            except Exception as e:
                print(f"Warning: ripgrep for full text failed: {e}")
                return []
        elif prefix == "?":
            # Help cheatsheet
            return [
                " (none)  Search files",
                " #       Search tags",
                " %       Full text search",
                " >       App commands",
                " /       AI commands",
                " !       Shell commands",
                " ?       Help cheatsheet",
            ]

        return []
