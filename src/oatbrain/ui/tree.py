from typing import Final
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib  # noqa: E402

from oatbrain.core.ports.filestore import FileStore, VaultPath  # noqa: E402
from oatbrain.core.bus import EventBus  # noqa: E402

# TreeStore column indices for clarity and maintainability
COL_NAME: Final[int] = 0        # The display name of the file or folder
COL_PATH: Final[int] = 1        # The vault-relative path as a string
COL_IS_DUMMY: Final[int] = 2    # True if this is a "Loading..." placeholder
COL_IS_DIR: Final[int] = 3      # True if this entry represents a directory


class FileTree(Gtk.Box):  # type: ignore[misc]
    """
    A hierarchical file tree view for navigating the vault.
    
    Implementation details:
    - Uses Gtk.TreeView with a Gtk.TreeStore model.
    - Implements lazy loading: scans directories when they are expanded.
    - Supports single-click to expand/collapse directories.
    """

    def __init__(self, filestore: FileStore, event_bus: EventBus) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.filestore = filestore
        self._event_bus = event_bus

        # Scrolled window provides scrollbars when the tree exceeds the pane size
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_vexpand(True)
        self.scrolled.set_hexpand(True)
        self.append(self.scrolled)

        # Model: [Name, Path, IsDummy, IsDir]
        self.store = Gtk.TreeStore(str, str, bool, bool)
        self.tree_view = Gtk.TreeView(model=self.store)
        self.tree_view.set_headers_visible(False)
        
        # Enable single-click activation. This causes the 'row-activated' 
        # signal to be emitted on a single click instead of a double click.
        self.tree_view.set_activate_on_single_click(True)

        # Create a single column to display the file/folder name
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Name", renderer, text=COL_NAME)
        self.tree_view.append_column(column)

        self.scrolled.set_child(self.tree_view)

        # Signals for lazy loading and single-click interaction
        self.tree_view.connect("row-expanded", self.on_row_expanded)
        self.tree_view.connect("row-activated", self.on_row_activated)

        self._populate_root()

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
                iter_ = self.store.append(None, [name, path_str, False, entry.is_dir])
                if entry.is_dir:
                    # Add a dummy child to folders so they are expandable.
                    self.store.append(iter_, ["Loading...", "", True, False])
        except Exception as e:
            # TODO: Propagate this to the UI status bar in Phase 3.2
            print(f"Error loading root: {e}")

    def on_row_activated(
        self, tree_view: Gtk.TreeView, path: Gtk.TreePath, column: Gtk.TreeViewColumn
    ) -> None:
        """
        Triggered when a row is clicked (single click due to activate-on-single-click).
        Toggles expansion for directories.
        """
        # Use idle_add to ensure we don't interfere with the current signal emission.
        # This prevents "double-toggle" or flickering issues.
        GLib.idle_add(self._toggle_row_expansion, path)

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
        """
        Triggered when a directory row is expanded.
        Loads directory contents if they haven't been loaded yet.
        """
        self._ensure_dir_loaded(iter_)

    def _ensure_dir_loaded(self, iter_: Gtk.TreeIter) -> None:
        """Checks if a directory is loaded (no dummy child) and loads it if needed."""
        child_iter = self.store.iter_children(iter_)
        if child_iter:
            # Check if the first child is a dummy placeholder
            is_dummy = self.store.get_value(child_iter, COL_IS_DUMMY)
            if is_dummy:
                parent_path_str = self.store.get_value(iter_, COL_PATH)
                try:
                    parent_path = VaultPath.from_str(parent_path_str)
                    entries = self.filestore.list_dir(parent_path)
                    entries.sort(key=lambda e: (not e.is_dir, e.path.path.name))
                    
                    # Add real entries BEFORE removing the dummy placeholder
                    # to ensure the row always has children and stays expandable.
                    for entry in entries:
                        name = entry.path.path.name
                        path_str = str(entry.path)
                        new_iter = self.store.append(
                            iter_, [name, path_str, False, entry.is_dir]
                        )
                        if entry.is_dir:
                            self.store.append(
                                new_iter, ["Loading...", "", True, False]
                            )
                    
                    # Now safely remove the dummy placeholder
                    self.store.remove(child_iter)
                except Exception as e:
                    print(f"Error loading dir {parent_path_str}: {e}")
