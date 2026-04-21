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
from oatbrain.core.events.watcher import (  # noqa: E402
    FileCreated,
    FileDeleted,
    FileRenamed,
)

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
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.filestore = filestore
        self._event_bus = event_bus
        self._command_router = command_router
        self._vault_root = vault_root

        # Scrolled window provides scrollbars
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_vexpand(True)
        self.scrolled.set_hexpand(True)
        self.append(self.scrolled)

        # Model: [Icon, Name, Path, IsDummy, IsDir, IsDirty]
        self.store = Gtk.TreeStore(str, str, str, bool, bool, bool)
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

        # Signals for lazy loading
        self.tree_view.connect("row-expanded", self.on_row_expanded)
        self.tree_view.connect("row-collapsed", self.on_row_collapsed)
        # We manually handle clicks instead of row-activated to prevent flicker
        # and support single-click vs right-click more reliably.

        # Click handling for Single-click activation and Right-click context menu
        self.click_gesture = Gtk.GestureClick.new()
        self.click_gesture.set_button(0)  # Listen for all buttons
        self.click_gesture.connect("released", self._on_click_released)
        self.tree_view.add_controller(self.click_gesture)

        # Context Menu (§9.2)
        self._setup_context_menu()

        # Keyboard shortcuts (§9.2)
        self._setup_key_controller()

        self._expanded_state: set[str] = set()
        self._last_synced_path: Optional[VaultPath] = None
        self._sync_idle_id: Optional[int] = None
        self._populate_root()
        self._event_bus.subscribe(StateUpdated, self._on_state_updated)
        self._event_bus.subscribe(FileCreated, self._on_file_created)
        self._event_bus.subscribe(FileDeleted, self._on_file_deleted)
        self._event_bus.subscribe(FileRenamed, self._on_file_renamed)

    def _on_click_released(
        self, gesture: Gtk.GestureClick, n_press: int, x: float, y: float
    ) -> None:
        button = gesture.get_current_button()
        res = self.tree_view.get_path_at_pos(int(x), int(y))

        if res:
            path, col, cell_x, cell_y = res
            tree_iter = self.store.get_iter(path)
            is_dir = self.store.get_value(tree_iter, COL_IS_DIR)
            path_str = self.store.get_value(tree_iter, COL_PATH)

            if button == 1:  # Left click
                self.tree_view.get_selection().select_path(path)
                if is_dir:
                    GLib.idle_add(self._toggle_row_expansion, path)
                else:
                    self._command_router.dispatch(
                        OpenFile(path=VaultPath.from_str(path_str))
                    )
            elif button == 3:  # Right click
                self.tree_view.get_selection().select_path(path)
                self._show_context_menu(x, y)

    def _setup_context_menu(self) -> None:
        """Sets up the right-click context menu."""
        self.menu = Gio.Menu()
        self.menu.append("New Note", "tree_app.new_note")
        self.menu.append("New Folder", "tree_app.new_folder")
        self.menu.append("Rename", "tree_app.rename_file")
        self.menu.append("Delete", "tree_app.delete_file")

        self.popover = Gtk.PopoverMenu.new_from_model(self.menu)
        self.popover.set_parent(self.tree_view)
        self.popover.set_has_arrow(False)

        # Register actions
        action_group = Gio.SimpleActionGroup()

        # Placeholders for actions
        for act in ["new_note", "new_folder", "rename_file", "delete_file"]:
            action_group.add_action(Gio.SimpleAction.new(act, None))

        self.insert_action_group("tree_app", action_group)

    def _show_context_menu(self, x: float, y: float) -> None:
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        self.popover.set_pointing_to(rect)
        self.popover.popup()

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
        base_size = 11.0
        new_size = base_size * event.state.tree_zoom
        css = f".oatbrain-filetree {{ font-size: {new_size:.1f}pt; }}"
        self._zoom_provider.load_from_string(css)

        # Apply expansion state
        if self._expanded_state != new_expanded:
            to_collapse = self._expanded_state - new_expanded
            self._expanded_state = new_expanded

            for path_str in to_collapse:
                self._collapse_path(VaultPath.from_str(path_str))

            for path_str in sorted(new_expanded, key=lambda p: p.count("/")):
                self._expand_path(VaultPath.from_str(path_str))

        open_path = event.state.editor.open_file
        if open_path != self._last_synced_path:
            self._last_synced_path = open_path
            if open_path:
                self._reveal_path(open_path)

        self._update_dirty_states(event)
        return False

    def _collapse_path(self, target_path: VaultPath) -> None:
        path_str = str(target_path)
        it = self._find_iter_for_path(path_str)
        if it:
            tree_path = self.store.get_path(it)
            self.tree_view.collapse_row(tree_path)

    def _expand_path(self, target_path: VaultPath) -> None:
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
                if self.store.get_value(child_iter, COL_PATH) == accumulated:
                    current_iter = child_iter
                    found = True
                    if self.store.get_value(current_iter, COL_IS_DIR):
                        self._ensure_dir_loaded(current_iter)
                        self.tree_view.expand_row(
                            self.store.get_path(current_iter), False
                        )
                    break
                child_iter = self.store.iter_next(child_iter)
            if not found:
                return

    def _reveal_path(self, target_path: VaultPath) -> None:
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
                if self.store.get_value(child_iter, COL_PATH) == accumulated:
                    current_iter = child_iter
                    found = True
                    if (
                        self.store.get_value(current_iter, COL_IS_DIR)
                        and i < len(parts) - 1
                    ):
                        self._ensure_dir_loaded(current_iter)
                        self.tree_view.expand_row(
                            self.store.get_path(current_iter), False
                        )
                    break
                child_iter = self.store.iter_next(child_iter)
            if not found:
                return
        if current_iter:
            self.tree_view.get_selection().select_iter(current_iter)
            self.tree_view.scroll_to_cell(
                self.store.get_path(current_iter), None, True, 0.5, 0.0
            )

    def _get_icon(self, is_dir: bool) -> str:
        return "folder-symbolic" if is_dir else "text-x-generic-symbolic"

    def _vault_rel(self, abs_path: str) -> Optional[str]:
        if self._vault_root is None:
            return None
        prefix = str(self._vault_root) + "/"
        if abs_path.startswith(prefix):
            return abs_path[len(prefix) :]
        return None

    def _find_iter_for_path(self, rel_path: str) -> Optional[Gtk.TreeIter]:
        parts = rel_path.split("/")
        current_iter = None
        accumulated = ""
        for i, part in enumerate(parts):
            if i > 0:
                accumulated += "/"
            accumulated += part
            child_iter = self.store.iter_children(current_iter)
            while child_iter:
                if self.store.get_value(child_iter, COL_PATH) == accumulated:
                    current_iter = child_iter
                    break
                child_iter = self.store.iter_next(child_iter)
            else:
                return None
        return current_iter

    def _on_file_created(self, event: FileCreated) -> None:
        GLib.idle_add(self._handle_file_created, event.path)

    def _split_rel_path(self, rel_path: str) -> tuple[str, str]:
        parts = rel_path.split("/")
        parent_rel = "/".join(parts[:-1]) if len(parts) > 1 else ""
        name = parts[-1]
        return parent_rel, name

    def _handle_file_created(self, abs_path: str) -> bool:
        rel = self._vault_rel(abs_path)
        if rel is None:
            return False
        parent_rel, name = self._split_rel_path(rel)
        is_dir = self._path_is_dir(abs_path)
        parent_iter = self._find_iter_for_path(parent_rel) if parent_rel else None
        if parent_rel and (
            parent_iter is None
            or (child := self.store.iter_children(parent_iter))
            and self.store.get_value(child, COL_IS_DUMMY)
        ):
            return False
        if self._find_iter_for_path(rel) is not None:
            return False
        icon = self._get_icon(is_dir)
        new_iter = self.store.append(
            parent_iter, [icon, name, rel, False, is_dir, False]
        )
        if is_dir:
            self.store.append(new_iter, ["", "Loading...", "", True, False, False])
        return False

    def _path_is_dir(self, abs_path: str) -> bool:
        import os

        return os.path.isdir(abs_path)

    def _compare_rows(
        self, model: Gtk.TreeModel, iter1: Gtk.TreeIter, iter2: Gtk.TreeIter, data: Any
    ) -> int:
        is_dir1 = model.get_value(iter1, COL_IS_DIR)
        is_dir2 = model.get_value(iter2, COL_IS_DIR)
        if is_dir1 != is_dir2:
            return -1 if is_dir1 else 1
        name1 = str(model.get_value(iter1, COL_NAME)).lower()
        name2 = str(model.get_value(iter2, COL_NAME)).lower()
        return -1 if name1 < name2 else (1 if name1 > name2 else 0)

    def _on_file_deleted(self, event: FileDeleted) -> None:
        GLib.idle_add(self._handle_file_deleted, event.path)

    def _handle_file_deleted(self, abs_path: str) -> bool:
        rel = self._vault_rel(abs_path)
        if rel is None:
            return False
        it = self._find_iter_for_path(rel)
        if it is not None:
            self.store.remove(it)
        return False

    def _on_file_renamed(self, event: FileRenamed) -> None:
        GLib.idle_add(self._handle_file_renamed, event.old_path, event.new_path)

    def _handle_file_renamed(self, old_abs: str, new_abs: str) -> bool:
        old_rel, new_rel = self._vault_rel(old_abs), self._vault_rel(new_abs)
        if old_rel is None or new_rel is None:
            return False
        it = self._find_iter_for_path(old_rel)
        if it is None:
            return False
        _, new_name = self._split_rel_path(new_rel)
        self.store.set_value(it, COL_NAME, new_name)
        self.store.set_value(it, COL_PATH, new_rel)
        self._repath_descendants(it, old_rel, new_rel)
        return False

    def _repath_descendants(
        self, it: Gtk.TreeIter, old_prefix: str, new_prefix: str
    ) -> None:
        child = self.store.iter_children(it)
        while child:
            p = self.store.get_value(child, COL_PATH)
            if p.startswith(old_prefix + "/"):
                self.store.set_value(child, COL_PATH, new_prefix + p[len(old_prefix) :])
            self._repath_descendants(child, old_prefix, new_prefix)
            child = self.store.iter_next(child)

    def _populate_root(self) -> None:
        try:
            entries = self.filestore.list_dir(VaultPath.from_str("."))
            entries.sort(key=lambda e: (not e.is_dir, e.path.path.name))
            for entry in entries:
                iter_ = self.store.append(
                    None,
                    [
                        self._get_icon(entry.is_dir),
                        entry.path.path.name,
                        str(entry.path),
                        False,
                        entry.is_dir,
                        False,
                    ],
                )
                if entry.is_dir:
                    self.store.append(iter_, ["", "Loading...", "", True, False, False])
        except Exception as e:
            print(f"Error loading root: {e}")

    def _toggle_row_expansion(self, path: Gtk.TreePath) -> None:
        if self.tree_view.row_expanded(path):
            self.tree_view.collapse_row(path)
        else:
            self.tree_view.expand_row(path, False)

    def on_row_expanded(
        self, tree_view: Gtk.TreeView, iter_: Gtk.TreeIter, path: Gtk.TreePath
    ) -> None:
        self._ensure_dir_loaded(iter_)
        path_str = self.store.get_value(iter_, COL_PATH)
        if path_str not in self._expanded_state:
            self._command_router.dispatch(
                SetTreeExpanded(path=path_str, is_expanded=True)
            )

    def on_row_collapsed(
        self, tree_view: Gtk.TreeView, iter_: Gtk.TreeIter, path: Gtk.TreePath
    ) -> None:
        path_str = self.store.get_value(iter_, COL_PATH)
        child_iter = self.store.iter_children(iter_)
        while child_iter:
            self.store.remove(child_iter)
            child_iter = self.store.iter_children(iter_)
        self.store.append(iter_, ["", "Loading...", "", True, False, False])
        if path_str in self._expanded_state:
            self._command_router.dispatch(
                SetTreeExpanded(path=path_str, is_expanded=False)
            )

    def _ensure_dir_loaded(self, iter_: Gtk.TreeIter) -> None:
        child_iter = self.store.iter_children(iter_)
        if child_iter and self.store.get_value(child_iter, COL_IS_DUMMY):
            parent_path_str = self.store.get_value(iter_, COL_PATH)
            try:
                entries = self.filestore.list_dir(VaultPath.from_str(parent_path_str))
                entries.sort(key=lambda e: (not e.is_dir, e.path.path.name))
                for entry in entries:
                    new_iter = self.store.append(
                        iter_,
                        [
                            self._get_icon(entry.is_dir),
                            entry.path.path.name,
                            str(entry.path),
                            False,
                            entry.is_dir,
                            False,
                        ],
                    )
                    if entry.is_dir:
                        self.store.append(
                            new_iter, ["", "Loading...", "", True, False, False]
                        )
                self.store.remove(child_iter)
            except Exception as e:
                print(f"Error loading dir {parent_path_str}: {e}")
