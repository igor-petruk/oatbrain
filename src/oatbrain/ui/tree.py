import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from oatbrain.core.ports.filestore import FileStore, VaultPath  # noqa: E402
from oatbrain.core.bus import EventBus  # noqa: E402


class FileTree(Gtk.Box):  # type: ignore[misc]
    def __init__(self, filestore: FileStore, event_bus: EventBus) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.filestore = filestore
        self._event_bus = event_bus

        # Scrolled window
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_vexpand(True)
        self.scrolled.set_hexpand(True)
        self.append(self.scrolled)

        # Columns: Display Name, VaultPath string, is_dummy
        self.store = Gtk.TreeStore(str, str, bool)
        self.tree_view = Gtk.TreeView(model=self.store)
        self.tree_view.set_headers_visible(False)
        
        # We need a column to render text
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Name", renderer, text=0)
        self.tree_view.append_column(column)

        self.scrolled.set_child(self.tree_view)

        # Lazy loading
        self.tree_view.connect("row-expanded", self.on_row_expanded)

        self._populate_root()

    def _populate_root(self) -> None:
        root_path = VaultPath.from_str(".")
        try:
            entries = self.filestore.list_dir(root_path)
            # Sort: dirs first, then files
            entries.sort(key=lambda e: (not e.is_dir, e.path.path.name))
            for entry in entries:
                name = entry.path.path.name
                path_str = str(entry.path)
                iter_ = self.store.append(None, [name, path_str, False])
                if entry.is_dir:
                    # Add dummy child
                    self.store.append(iter_, ["Loading...", "", True])
        except Exception as e:
            # Handle empty/unreadable root
            print(f"Error loading root: {e}")

    def on_row_expanded(
        self, tree_view: Gtk.TreeView, iter_: Gtk.TreeIter, path: Gtk.TreePath
    ) -> None:
        # Check if it has a dummy child
        child_iter = self.store.iter_children(iter_)
        if child_iter:
            is_dummy = self.store.get_value(child_iter, 2)
            if is_dummy:
                self.store.remove(child_iter)
                parent_path_str = self.store.get_value(iter_, 1)
                try:
                    parent_path = VaultPath.from_str(parent_path_str)
                    entries = self.filestore.list_dir(parent_path)
                    entries.sort(key=lambda e: (not e.is_dir, e.path.path.name))
                    for entry in entries:
                        name = entry.path.path.name
                        path_str = str(entry.path)
                        new_iter = self.store.append(iter_, [name, path_str, False])
                        if entry.is_dir:
                            self.store.append(new_iter, ["Loading...", "", True])
                except Exception as e:
                    print(f"Error loading dir {parent_path_str}: {e}")
