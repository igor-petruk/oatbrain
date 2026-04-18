from typing import Final
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from oatbrain.core.ports.filestore import FileStore, VaultPath  # noqa: E402
from oatbrain.core.bus import EventBus  # noqa: E402

# TreeStore column indices for clarity
COL_NAME: Final[int] = 0
COL_PATH: Final[int] = 1
COL_IS_DUMMY: Final[int] = 2
COL_IS_DIR: Final[int] = 3


class FileTree(Gtk.Box):  # type: ignore[misc]
    """
    A hierarchical file tree view for navigating the vault.
    Uses lazy loading to avoid scanning the entire filesystem at once.
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

        # Gtk.TreeStore(Name: str, Path: str, IsDummy: bool, IsDir: bool)
        self.store = Gtk.TreeStore(str, str, bool, bool)
        self.tree_view = Gtk.TreeView(model=self.store)
        self.tree_view.set_headers_visible(False)

        # Create a single column to display the file/folder name
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Name", renderer, text=COL_NAME)
        self.tree_view.append_column(column)

        self.scrolled.set_child(self.tree_view)

        # Connect the expansion signal to implement lazy loading of subdirectories
        self.tree_view.connect("row-expanded", self.on_row_expanded)

        # Single click to expand/collapse directories
        self.click_gesture = Gtk.GestureClick()
        self.click_gesture.connect("released", self.on_click_released)
        self.tree_view.add_controller(self.click_gesture)

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
                    # The actual content will be loaded when the user expands the row.
                    self.store.append(iter_, ["Loading...", "", True, False])
        except Exception as e:
            # TODO: Propagate this to the UI status bar instead of just printing
            print(f"Error loading root: {e}")

    def on_click_released(
        self, gesture: Gtk.GestureClick, n_press: int, x: float, y: float
    ) -> None:
        """Handles single clicks on the tree view to toggle expansion of directories."""
        if n_press != 1:
            return

        # Identify which row (path) was clicked
        path_info = self.tree_view.get_path_at_pos(int(x), int(y))
        if not path_info:
            return

        path, column, cell_x, cell_y = path_info
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
        If the directory has not been loaded yet (contains a dummy child),
        it fetches the actual directory contents.
        """
        child_iter = self.store.iter_children(iter_)
        if child_iter:
            # Check if the first child is a dummy placeholder
            is_dummy = self.store.get_value(child_iter, COL_IS_DUMMY)
            if is_dummy:
                # Remove placeholder and load real data
                self.store.remove(child_iter)
                parent_path_str = self.store.get_value(iter_, COL_PATH)
                try:
                    parent_path = VaultPath.from_str(parent_path_str)
                    entries = self.filestore.list_dir(parent_path)
                    entries.sort(key=lambda e: (not e.is_dir, e.path.path.name))
                    for entry in entries:
                        name = entry.path.path.name
                        path_str = str(entry.path)
                        new_iter = self.store.append(
                            iter_, [name, path_str, False, entry.is_dir]
                        )
                        if entry.is_dir:
                            self.store.append(new_iter, ["Loading...", "", True, False])
                except Exception as e:
                    print(f"Error loading dir {parent_path_str}: {e}")
            # Note: If is_dummy is False, the directory has already been loaded.
            # In this current phase, we don't implement automatic re-scanning
            # on every expansion to keep it simple and performant.
