from typing import Final, Any
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib  # noqa: E402

from oatbrain.core.ports.filestore import FileStore, VaultPath  # noqa: E402
from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.commands import OpenFile  # noqa: E402

from oatbrain.core.events.state import StateUpdated  # noqa: E402

# TreeStore column indices for clarity and maintainability
COL_ICON: Final[int] = 0        # Icon name
COL_NAME: Final[int] = 1        # The display name of the file or folder
COL_PATH: Final[int] = 2        # The vault-relative path as a string
COL_IS_DUMMY: Final[int] = 3    # True if this is a "Loading..." placeholder
COL_IS_DIR: Final[int] = 4      # True if this entry represents a directory
COL_IS_DIRTY: Final[int] = 5    # True if file has unsaved changes


class FileTree(Gtk.Box):  # type: ignore[misc]
    """
    A hierarchical file tree view for navigating the vault.

    Implementation details:
    - Uses Gtk.TreeView with a Gtk.TreeStore model.
    - Implements lazy loading: scans directories when they are expanded.
    - Supports single-click to expand/collapse directories.
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

        # Enable single-click activation.
        self.tree_view.set_activate_on_single_click(True)

        # Create columns
        column = Gtk.TreeViewColumn("Name")

        # Icon
        icon_renderer = Gtk.CellRendererPixbuf()
        column.pack_start(icon_renderer, False)
        column.add_attribute(icon_renderer, "icon-name", COL_ICON)

        # Name
        text_renderer = Gtk.CellRendererText()
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

        self._populate_root()
        self._event_bus.subscribe(StateUpdated, self._on_state_updated)

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
        GLib.idle_add(self._update_dirty_states, event)

    def _update_dirty_states(self, event: StateUpdated) -> bool:
        # TODO: Implement deep update of dirty states in tree
        return bool(GLib.SOURCE_REMOVE)

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
                    self.store.append(
                        iter_, ["", "Loading...", "", True, False, False]
                    )
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
                            iter_,
                            [icon, name, path_str, False, entry.is_dir, False]
                        )
                        if entry.is_dir:
                            self.store.append(
                                new_iter,
                                ["", "Loading...", "", True, False, False]
                            )

                    self.store.remove(child_iter)
                except Exception as e:
                    print(f"Error loading dir {parent_path_str}: {e}")
