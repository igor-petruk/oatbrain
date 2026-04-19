from typing import Final, Any
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, GLib, Gio, Gdk  # noqa: E402

from oatbrain.core.ports.filestore import FileStore, VaultPath  # noqa: E402
from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.commands import OpenFile  # noqa: E402

from oatbrain.core.events.state import StateUpdated  # noqa: E402

# TreeStore column indices for clarity and maintainability
COL_ICON: Final[int] = 0  # Icon name
COL_NAME: Final[int] = 1  # The display name of the file or folder
COL_PATH: Final[int] = 2  # The vault-relative path as a string
COL_IS_DUMMY: Final[int] = 3  # True if this is a "Loading..." placeholder
COL_IS_DIR: Final[int] = 4  # True if this entry represents a directory
COL_IS_DIRTY: Final[int] = 5  # True if file has unsaved changes


class FileTree(Gtk.Box):  # type: ignore[misc]
    """
    A hierarchical file tree view for navigating the vault.

    Implementation details:
    - Uses Gtk.TreeView with a Gtk.TreeStore model.
    - Implements lazy loading: scans directories when they are expanded.
    - Supports single-click to expand/collapse directories and open files.
    """

    def __init__(
        self,
        filestore: FileStore,
        event_bus: EventBus,
        command_router: CommandRouter,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.filestore = filestore
        self._event_bus = event_bus
        self._command_router = command_router

        # Scrolled window provides scrollbars
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_vexpand(True)
        self.scrolled.set_hexpand(True)
        self.append(self.scrolled)

        # Model: [Icon, Name, Path, IsDummy, IsDir, IsDirty]
        self.store = Gtk.TreeStore(str, str, str, bool, bool, bool)
        self.tree_view = Gtk.TreeView(model=self.store)
        self.tree_view.set_headers_visible(False)
        self.tree_view.add_css_class("oatbrain-filetree")

        # Enable single-click activation (SPEC §9.2 updated)
        self.tree_view.set_activate_on_single_click(True)

        # Create columns
        column = Gtk.TreeViewColumn("Name")

        # Icon
        icon_renderer = Gtk.CellRendererPixbuf()
        icon_renderer.set_property("xpad", 6)
        column.pack_start(icon_renderer, False)
        column.add_attribute(icon_renderer, "icon-name", COL_ICON)

        # Name
        text_renderer = Gtk.CellRendererText()
        text_renderer.set_property("xpad", 4)
        column.pack_start(text_renderer, True)
        column.add_attribute(text_renderer, "text", COL_NAME)

        # Unsaved dot
        dot_renderer = Gtk.CellRendererText()
        column.pack_start(dot_renderer, False)
        column.set_cell_data_func(dot_renderer, self._render_unsaved_dot)

        self.tree_view.append_column(column)

        self.scrolled.set_child(self.tree_view)

        # Signals for lazy loading and single-click interaction
        self.tree_view.connect("row-expanded", self.on_row_expanded)
        self.tree_view.connect("row-activated", self.on_row_activated)

        # Context Menu (§9.2)
        self._setup_context_menu()

        # Keyboard shortcuts (§9.2)
        self._setup_key_controller()

        self._last_synced_path: Optional[VaultPath] = None
        self._populate_root()
        self._event_bus.subscribe(StateUpdated, self._on_state_updated)

    def _setup_context_menu(self) -> None:
        """Sets up the right-click context menu."""
        self.menu = Gio.Menu()
        self.menu.append("New Note", "app.new_note")
        self.menu.append("New Folder", "app.new_folder")
        self.menu.append("Rename", "app.rename_file")
        self.menu.append("Delete", "app.delete_file")

        self.popover = Gtk.PopoverMenu.new_from_model(self.menu)
        self.popover.set_parent(self)
        self.popover.set_has_arrow(False)

        gesture = Gtk.GestureClick.new()
        gesture.set_button(3)  # Right click
        gesture.connect("pressed", self._on_right_click)
        self.tree_view.add_controller(gesture)

    def _setup_key_controller(self) -> None:
        """Sets up keyboard event handling."""
        controller = Gtk.EventControllerKey.new()
        controller.connect("key-pressed", self._on_key_pressed)
        self.tree_view.add_controller(controller)

    def _on_key_pressed(
        self,
        controller: Gtk.EventControllerKey,
        keyval: int,
        keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        if keyval == Gdk.KEY_Delete:
            self._on_delete_pressed()
            return True
        return False

    def _on_delete_pressed(self) -> None:
        """Handles the Delete key press."""
        selection = self.tree_view.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter:
            path_str = model.get_value(tree_iter, COL_PATH)
            # Permanent delete (§22.4) logic will go here
            print(f"Delete permanently: {path_str}")

    def _on_right_click(
        self, gesture: Gtk.GestureClick, n_press: int, x: float, y: int
    ) -> None:
        """Shows the context menu at the click location."""
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 0
        rect.height = 0
        self.popover.set_pointing_to(rect)
        self.popover.popup()

    def _render_unsaved_dot(
        self,
        column: Gtk.TreeViewColumn,
        cell: Gtk.CellRenderer,
        model: Gtk.TreeModel,
        iter_: Gtk.TreeIter,
        data: Any,
    ) -> None:
        is_dirty = model.get_value(iter_, COL_IS_DIRTY)
        cell.set_property("text", "●" if is_dirty else "")

    def _on_state_updated(self, event: StateUpdated) -> None:
        GLib.idle_add(self._sync_with_state, event)

    def grab_focus(self) -> bool:
        """Override to focus the internal TreeView."""
        return bool(self.tree_view.grab_focus())

    def _update_dirty_states(self, event: StateUpdated) -> bool:
        # TODO: Implement deep update of dirty states in tree
        return bool(GLib.SOURCE_REMOVE)

    def _sync_with_state(self, event: StateUpdated) -> bool:
        open_path = event.state.editor.open_file
        if open_path != self._last_synced_path:
            self._last_synced_path = open_path
            if open_path:
                self._reveal_path(open_path)
        
        # Also update dirty states (placeholder for now)
        self._update_dirty_states(event)
        return bool(GLib.SOURCE_REMOVE)

    def _reveal_path(self, target_path: VaultPath) -> None:
        """Finds, expands, and selects the given path in the tree."""
        path_str = str(target_path)
        parts = path_str.split("/")
        
        current_iter = None
        accumulated = ""
        
        for i, part in enumerate(parts):
            if i > 0:
                accumulated += "/"
            accumulated += part
            
            found = False
            child_iter = self.store.iter_children(current_iter)
            while child_iter:
                row_path = self.store.get_value(child_iter, COL_PATH)
                if row_path == accumulated:
                    current_iter = child_iter
                    found = True
                    
                    # If this is a directory and not the final file, expand it
                    is_dir = self.store.get_value(current_iter, COL_IS_DIR)
                    if is_dir and i < len(parts) - 1:
                        self._ensure_dir_loaded(current_iter)
                        tree_path = self.store.get_path(current_iter)
                        self.tree_view.expand_row(tree_path, False)
                    break
                child_iter = self.store.iter_next(child_iter)
            
            if not found:
                return

        if current_iter:
            # Block signal to avoid re-triggering OpenFile from selection change
            # Actually, activation triggers OpenFile, selection doesn't by default here.
            selection = self.tree_view.get_selection()
            selection.select_iter(current_iter)
            tree_path = self.store.get_path(current_iter)
            # Scroll to make it visible
            self.tree_view.scroll_to_cell(tree_path, None, True, 0.5, 0.0)

    def _get_icon(self, is_dir: bool) -> str:
        return "folder-symbolic" if is_dir else "text-x-generic-symbolic"

    def _populate_root(self) -> None:
        """Initial population of the tree's root level."""
        root_path = VaultPath.from_str(".")
        try:
            entries = self.filestore.list_dir(root_path)
            # Sort: directories first, then files alphabetically
            entries.sort(key=lambda e: (not e.is_dir, e.path.path.name))
            for entry in entries:
                name = entry.path.path.name
                path_str = str(entry.path)
                icon = self._get_icon(entry.is_dir)
                iter_ = self.store.append(
                    None, [icon, name, path_str, False, entry.is_dir, False]
                )
                if entry.is_dir:
                    # Add a dummy child to folders
                    self.store.append(iter_, ["", "Loading...", "", True, False, False])
        except Exception as e:
            print(f"Error loading root: {e}")

    def on_row_activated(
        self,
        tree_view: Gtk.TreeView,
        path: Gtk.TreePath,
        column: Gtk.TreeViewColumn,
    ) -> None:
        """Toggles expansion for directories, opens files."""
        tree_iter = self.store.get_iter(path)
        is_dir = self.store.get_value(tree_iter, COL_IS_DIR)

        if is_dir:
            GLib.idle_add(self._toggle_row_expansion, path)
        else:
            path_str = self.store.get_value(tree_iter, COL_PATH)
            vault_path = VaultPath.from_str(path_str)
            self._command_router.dispatch(OpenFile(path=vault_path))

    def _toggle_row_expansion(self, path: Gtk.TreePath) -> None:
        """Helper to toggle the expansion state of a row."""
        tree_iter = self.store.get_iter(path)
        is_dir = self.store.get_value(tree_iter, COL_IS_DIR)

        if is_dir:
            if self.tree_view.row_expanded(path):
                self.tree_view.collapse_row(path)
            else:
                self.tree_view.expand_row(path, False)

    def on_row_expanded(
        self, tree_view: Gtk.TreeView, iter_: Gtk.TreeIter, path: Gtk.TreePath
    ) -> None:
        """Loads directory contents if they haven't been loaded yet."""
        self._ensure_dir_loaded(iter_)

    def _ensure_dir_loaded(self, iter_: Gtk.TreeIter) -> None:
        """Checks if a directory is loaded and loads it if needed."""
        child_iter = self.store.iter_children(iter_)
        if child_iter:
            is_dummy = self.store.get_value(child_iter, COL_IS_DUMMY)
            if is_dummy:
                parent_path_str = self.store.get_value(iter_, COL_PATH)
                try:
                    parent_path = VaultPath.from_str(parent_path_str)
                    entries = self.filestore.list_dir(parent_path)
                    entries.sort(key=lambda e: (not e.is_dir, e.path.path.name))

                    for entry in entries:
                        name = entry.path.path.name
                        path_str = str(entry.path)
                        icon = self._get_icon(entry.is_dir)
                        new_iter = self.store.append(
                            iter_, [icon, name, path_str, False, entry.is_dir, False]
                        )
                        if entry.is_dir:
                            self.store.append(
                                new_iter, ["", "Loading...", "", True, False, False]
                            )

                    self.store.remove(child_iter)
                except Exception as e:
                    print(f"Error loading dir {parent_path_str}: {e}")
