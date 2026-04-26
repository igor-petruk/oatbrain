from typing import Any, Final, Optional
from pathlib import Path
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, GLib, Gio, Gdk  # noqa: E402

from oatbrain.core.ports.filestore import FileStore, VaultPath  # noqa: E402
from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.commands import OpenFile, SetTreeExpanded, Zoom  # noqa: E402

from oatbrain.core.events.state import StateUpdated  # noqa: E402
from oatbrain.core.ports.watcher import FileWatcher, Unsubscribe  # noqa: E402

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
        vault_root: Optional[Path] = None,
        watcher: Optional[FileWatcher] = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.filestore = filestore
        self._event_bus = event_bus
        self._command_router = command_router
        self._vault_root = vault_root
        self._watcher = watcher
        self._watch_subscriptions: dict[str, Unsubscribe] = {}

        # Scrolled window provides scrollbars
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_vexpand(True)
        self.scrolled.set_hexpand(True)
        self.append(self.scrolled)

        # Model: [Icon, Name, Path, IsDummy, IsDir, IsDirty]
        self.store = Gtk.TreeStore(str, str, str, bool, bool, bool)
        self._path_registry: dict[str, Gtk.TreeRowReference] = {}
        self.store.set_sort_func(COL_NAME, self._compare_rows)
        self.store.set_sort_column_id(COL_NAME, Gtk.SortType.ASCENDING)

        self.tree_view = Gtk.TreeView(model=self.store)
        self.tree_view.set_headers_visible(False)
        self.tree_view.add_css_class("oatbrain-filetree")

        # Zoom provider for FileTree (§19)
        self._zoom_provider = Gtk.CssProvider()
        self.tree_view.get_style_context().add_provider(
            self._zoom_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Enable single-click activation (SPEC §9.2 updated)
        self.tree_view.set_activate_on_single_click(True)

        # Create columns
        column = Gtk.TreeViewColumn("Name")

        # Icon
        self.icon_renderer = Gtk.CellRendererPixbuf()
        self.icon_renderer.set_property("xpad", 6)
        column.pack_start(self.icon_renderer, False)
        column.add_attribute(self.icon_renderer, "icon-name", COL_ICON)

        # Name
        self.text_renderer = Gtk.CellRendererText()
        self.text_renderer.set_property("xpad", 4)
        column.pack_start(self.text_renderer, True)
        column.add_attribute(self.text_renderer, "text", COL_NAME)

        # Unsaved dot
        self.dot_renderer = Gtk.CellRendererText()
        column.pack_start(self.dot_renderer, False)
        column.set_cell_data_func(self.dot_renderer, self._render_unsaved_dot)

        self.tree_view.append_column(column)

        self.scrolled.set_child(self.tree_view)

        # Ctrl+MouseScroll zooming (§19)
        scroll_ctrl = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL
        )
        scroll_ctrl.connect("scroll", self._on_scroll)
        self.tree_view.add_controller(scroll_ctrl)

        # Signals for lazy loading and single-click interaction
        self.tree_view.connect("row-expanded", self.on_row_expanded)
        self.tree_view.connect("row-collapsed", self.on_row_collapsed)
        self.tree_view.connect("row-activated", self.on_row_activated)

        # Context Menu (§9.2)
        self._setup_context_menu()

        # Keyboard shortcuts (§9.2)
        self._setup_key_controller()

        self._expanded_state: set[str] = set()
        self._last_synced_path: Optional[VaultPath] = None
        self._sync_idle_id: Optional[int] = None
        self._populate_root()
        if self._watcher and self._vault_root:
            unsub = self._watcher.subscribe_dir(
                self._vault_root, self._on_watched_dir_event
            )
            self._watch_subscriptions["."] = unsub

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

    def _on_scroll(self, ctrl: Gtk.EventControllerScroll, dx: float, dy: float) -> bool:
        """Handle Ctrl+MouseScroll to zoom tree (§19)."""
        event = ctrl.get_current_event()
        if not event:
            return False
        modifiers = event.get_modifier_state()
        if modifiers & Gdk.ModifierType.CONTROL_MASK:
            # dy is positive for scroll down, negative for scroll up
            delta = -0.1 if dy > 0 else 0.1
            self._command_router.dispatch(Zoom("tree", delta))
            return True
        return False

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
        if self._sync_idle_id is not None:
            GLib.source_remove(self._sync_idle_id)
        self._sync_idle_id = GLib.idle_add(self._sync_with_state, event)

    def grab_focus(self) -> bool:
        """Override to focus the internal TreeView."""
        return bool(self.tree_view.grab_focus())

    def _update_dirty_states(self, event: StateUpdated) -> bool:
        # TODO: Implement deep update of dirty states in tree
        return False

    def _sync_with_state(self, event: StateUpdated) -> bool:
        self._sync_idle_id = None
        new_expanded = set(event.state.tree_expanded)

        # Apply zoom (§19)
        # Use CSS for font-size so that row height and icons scale together.
        # Adwaita default UI font size is ~11pt.
        base_size = 11.0
        new_size = base_size * event.state.tree_zoom
        css = f".oatbrain-filetree {{ font-size: {new_size:.1f}pt; }}"
        self._zoom_provider.load_from_string(css)

        # Apply expansion state on initial sync or if it changes externally
        if self._expanded_state != new_expanded:
            to_collapse = self._expanded_state - new_expanded
            to_expand = new_expanded - self._expanded_state
            self._expanded_state = new_expanded

            # Collapse those that were removed
            for path_str in to_collapse:
                self._collapse_path(VaultPath.from_str(path_str))
                unsub = self._watch_subscriptions.pop(path_str, None)
                if unsub:
                    unsub()

            # Sort by path depth to expand parents before children
            for path_str in sorted(new_expanded, key=lambda p: p.count("/")):
                self._expand_path(VaultPath.from_str(path_str))

            for path_str in to_expand:
                vp = VaultPath.from_str(path_str)
                try:
                    if self.filestore.exists(vp) and self.filestore.stat(vp).is_dir:
                        if self._watcher and self._vault_root:
                            abs_path = self._vault_root / path_str
                            unsub = self._watcher.subscribe_dir(
                                abs_path, self._on_watched_dir_event
                            )
                            self._watch_subscriptions[path_str] = unsub
                    else:
                        # Prune from state if it doesn't exist
                        self._command_router.dispatch(
                            SetTreeExpanded(path=path_str, is_expanded=False)
                        )
                except Exception as e:
                    print(f"Error subscribing: {e}")

        ea = event.state.editor_area
        open_path = None
        if ea.groups:
            idx = min(ea.focused_group_index, len(ea.groups) - 1)
            focused_group = ea.groups[idx]
            active = min(focused_group.active_tab_index, len(focused_group.tabs) - 1)
            if focused_group.tabs:
                open_path = focused_group.tabs[active].open_file

        if open_path != self._last_synced_path:
            self._last_synced_path = open_path
            if open_path:
                self._reveal_path(open_path)

        # Also update dirty states (placeholder for now)
        self._update_dirty_states(event)
        return False

    def _collapse_path(self, target_path: VaultPath) -> None:
        """Finds and collapses the given path in the tree."""
        path_str = str(target_path)
        it = self._find_iter_for_path(path_str)
        if it:
            tree_path = self.store.get_path(it)
            self.tree_view.collapse_row(tree_path)

    def _expand_path(self, target_path: VaultPath) -> None:
        """Finds and expands the given path in the tree without selecting it."""
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

                    is_dir = self.store.get_value(current_iter, COL_IS_DIR)
                    if is_dir:
                        self._ensure_dir_loaded(current_iter)
                        tree_path = self.store.get_path(current_iter)
                        self.tree_view.expand_row(tree_path, False)
                    break
                child_iter = self.store.iter_next(child_iter)

            if not found:
                return

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

    # ------------------------------------------------------------------
    # File watcher event handlers
    # ------------------------------------------------------------------

    def _vault_rel(self, abs_path: str) -> Optional[str]:
        """Convert an absolute path to vault-relative, or None if outside vault."""
        if self._vault_root is None:
            return None
        prefix = str(self._vault_root) + "/"
        if abs_path.startswith(prefix):
            return abs_path[len(prefix) :]
        return None

    def _find_iter_for_path(self, rel_path: str) -> Optional[Gtk.TreeIter]:
        """O(1) lookup using the path registry."""
        ref = self._path_registry.get(rel_path)
        if ref and ref.valid():
            path = ref.get_path()
            if path:
                return self.store.get_iter(path)
        return None

    def _register_node(self, iter_: Gtk.TreeIter, rel_path: str) -> None:
        path = self.store.get_path(iter_)
        if rel_path:
            self._path_registry[rel_path] = Gtk.TreeRowReference.new(self.store, path)

    def _unregister_node(self, rel_path: str) -> None:
        if rel_path in self._path_registry:
            del self._path_registry[rel_path]

    def _remove_node(self, rel_path: str) -> bool:
        """Remove a node and its descendants from the store and registry.

        Returns True if the node was found.
        """
        it = self._find_iter_for_path(rel_path)
        if it is None:
            return False

        def _unregister_descendants(parent_iter: Gtk.TreeIter) -> None:
            child = self.store.iter_children(parent_iter)
            while child:
                child_path = self.store.get_value(child, COL_PATH)
                if child_path:
                    self._unregister_node(child_path)
                _unregister_descendants(child)
                child = self.store.iter_next(child)

        _unregister_descendants(it)
        self._unregister_node(rel_path)
        self.store.remove(it)
        return True

    def _on_watched_dir_event(
        self, action: str, path: Path, new_path: Optional[Path]
    ) -> None:
        if action == "CREATED":
            GLib.idle_add(self._handle_file_created, str(path))
        elif action == "DELETED":
            GLib.idle_add(self._handle_file_deleted, str(path))
        elif action == "RENAMED" and new_path:
            GLib.idle_add(self._handle_file_renamed, str(path), str(new_path))

    def _split_rel_path(self, rel_path: str) -> tuple[str, str]:
        """
        Splits a vault-relative path into (parent_rel, name).

        Input: "projects/oatbrain/README.md"
        Output: ("projects/oatbrain", "README.md")

        Input: "top_level.md"
        Output: ("", "top_level.md")
        """
        parts = rel_path.split("/")
        parent_rel = "/".join(parts[:-1]) if len(parts) > 1 else ""
        name = parts[-1]
        return parent_rel, name

    def _is_hidden(self, rel_path: str) -> bool:
        """Returns True if the path contains any hidden component."""
        for part in rel_path.split("/"):
            if part.startswith(".") and part != ".":
                return True
        return False

    def _handle_file_created(self, abs_path: str) -> bool:
        rel = self._vault_rel(abs_path)
        if rel is None or self._is_hidden(rel):
            return False

        parent_rel, name = self._split_rel_path(rel)
        is_dir = not abs_path.endswith(name) or self._path_is_dir(abs_path)

        parent_iter = self._find_iter_for_path(parent_rel) if parent_rel else None

        # Only insert if parent is loaded (no dummy child) or we're at root
        if parent_rel:
            if parent_iter is None:
                return False
            child = self.store.iter_children(parent_iter)
            if child and self.store.get_value(child, COL_IS_DUMMY):
                return False
        else:
            # Root: always loaded
            pass

        # Check not already present
        if self._find_iter_for_path(rel) is not None:
            return False

        icon = self._get_icon(is_dir)
        new_iter = self.store.append(
            parent_iter, [icon, name, rel, False, is_dir, False]
        )
        self._register_node(new_iter, rel)
        if is_dir:
            self.store.append(new_iter, ["", "Loading...", "", True, False, False])

        return False

    def _path_is_dir(self, abs_path: str) -> bool:
        import os

        return os.path.isdir(abs_path)

    def _compare_rows(
        self, model: Gtk.TreeModel, iter1: Gtk.TreeIter, iter2: Gtk.TreeIter, data: Any
    ) -> int:
        """Custom sort: directories first, then alphabetical name."""
        is_dir1 = model.get_value(iter1, COL_IS_DIR)
        is_dir2 = model.get_value(iter2, COL_IS_DIR)

        if is_dir1 != is_dir2:
            return -1 if is_dir1 else 1

        name1 = str(model.get_value(iter1, COL_NAME)).lower()
        name2 = str(model.get_value(iter2, COL_NAME)).lower()

        if name1 < name2:
            return -1
        if name1 > name2:
            return 1
        return 0

    def _handle_file_deleted(self, abs_path: str) -> bool:
        rel = self._vault_rel(abs_path)
        if rel is None or self._is_hidden(rel):
            return False
        self._remove_node(rel)
        return False

    def _handle_file_renamed(self, old_abs: str, new_abs: str) -> bool:
        old_rel = self._vault_rel(old_abs)
        new_rel = self._vault_rel(new_abs)
        if old_rel is None or new_rel is None:
            return False

        if self._is_hidden(new_rel):
            # Target is hidden. If old wasn't, it effectively disappeared.
            if not self._is_hidden(old_rel):
                return self._handle_file_deleted(old_abs)
            return False

        if self._is_hidden(old_rel):
            # A hidden file was renamed to a visible file. Treat as creation.
            return self._handle_file_created(new_abs)

        existing_target_iter = self._find_iter_for_path(new_rel)
        if existing_target_iter is not None:
            self._remove_node(new_rel)

        it = self._find_iter_for_path(old_rel)
        if it is None:
            # If we missed the creation of the old file for some reason,
            # treat this as a plain creation.
            return self._handle_file_created(new_abs)

        _, new_name = self._split_rel_path(new_rel)
        self.store.set_value(it, COL_NAME, new_name)
        self.store.set_value(it, COL_PATH, new_rel)

        self._unregister_node(old_rel)
        self._register_node(it, new_rel)

        # Update COL_PATH for all descendants (prefix swap)
        self._repath_descendants(it, old_rel, new_rel)

        return False

    def _repath_descendants(
        self, it: Gtk.TreeIter, old_prefix: str, new_prefix: str
    ) -> None:
        """Recursively update COL_PATH for all children after a rename."""
        child = self.store.iter_children(it)
        while child:
            p = self.store.get_value(child, COL_PATH)
            if p.startswith(old_prefix + "/"):
                new_p = new_prefix + p[len(old_prefix) :]
                self.store.set_value(child, COL_PATH, new_p)
                self._unregister_node(p)
                self._register_node(child, new_p)
            self._repath_descendants(child, old_prefix, new_prefix)
            child = self.store.iter_next(child)

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
                self._register_node(iter_, path_str)
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
        path_str = self.store.get_value(iter_, COL_PATH)
        if path_str not in self._expanded_state:
            self._command_router.dispatch(
                SetTreeExpanded(path=path_str, is_expanded=True)
            )

    def on_row_collapsed(
        self, tree_view: Gtk.TreeView, iter_: Gtk.TreeIter, path: Gtk.TreePath
    ) -> None:
        """Unloads directory contents and stores a dummy node."""
        path_str = self.store.get_value(iter_, COL_PATH)

        # Remove all children
        child_iter = self.store.iter_children(iter_)
        while child_iter:
            child_path_str = self.store.get_value(child_iter, COL_PATH)
            if child_path_str:
                self._remove_node(child_path_str)
            else:
                self.store.remove(child_iter)
            child_iter = self.store.iter_children(iter_)

        # Re-add dummy node
        self.store.append(iter_, ["", "Loading...", "", True, False, False])

        if path_str in self._expanded_state:
            self._command_router.dispatch(
                SetTreeExpanded(path=path_str, is_expanded=False)
            )

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
                        self._register_node(new_iter, path_str)
                        if entry.is_dir:
                            self.store.append(
                                new_iter, ["", "Loading...", "", True, False, False]
                            )

                    self.store.remove(child_iter)
                except Exception as e:
                    print(f"Error loading dir {parent_path_str}: {e}")
