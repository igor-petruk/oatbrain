import gi
import logging
from typing import List, Dict, Optional, Any, Callable
from gi.repository import Gtk, GLib

from oatbrain.core.state import EditorAreaState, AppState, GroupState, TabState
from oatbrain.ui.group_pane import GroupPane
from oatbrain.ui.editor import Editor
from oatbrain.core.bus import EventBus, CommandRouter
from oatbrain.core.commands import (
    OpenFile,
    NewTab,
    NewNote,
    CloseTab,
    SplitGroupRight,
)
from oatbrain.core.ports.filestore import FileStore, VaultPath
from oatbrain.core.ports.env import Env
from oatbrain.core.ports.watcher import FileWatcher
from oatbrain.core.ports.renderer import Renderer
from oatbrain.core.wikilink import WikilinkResolver
from oatbrain.core.events.ui import (
    TabPathChanged,
    TabTitleChanged,
    FocusedTabStats,
    WordCountChanged,
    DirtyStateChanged,
)

gi.require_version("Gtk", "4.0")


def compute_tab_titles(ea_state: EditorAreaState) -> Dict[str, str]:
    """Return a mapping of tab_id -> display title using VSCode-style disambiguation."""
    id_to_path: Dict[str, Optional[VaultPath]] = {}
    basename_to_ids: Dict[str, List[str]] = {}

    for g in ea_state.groups:
        for t in g.tabs:
            id_to_path[t.tab_id] = t.open_file
            if t.open_file:
                bn = t.open_file.path.name
                if bn not in basename_to_ids:
                    basename_to_ids[bn] = []
                basename_to_ids[bn].append(t.tab_id)

    titles: Dict[str, str] = {}
    for tid, path in id_to_path.items():
        # Priority 1: Title override from TabState (e.g. extracted heading)
        for g in ea_state.groups:
            for t in g.tabs:
                if t.tab_id == tid and t.title:
                    titles[tid] = t.title
                    break
            if tid in titles:
                break
        if tid in titles:
            continue

        if not path:
            titles[tid] = "Untitled"
            continue
        bn = path.path.name
        if len(basename_to_ids[bn]) == 1:
            titles[tid] = bn
        else:
            parent = path.parent
            if str(parent.path) != ".":
                titles[tid] = f"{bn} [{parent.path.name}]"
            else:
                titles[tid] = bn
    return titles


class EditorArea:
    """Coordinates multiple horizontal tab groups (Groups) in a set of Paned widgets."""

    def __init__(
        self,
        filestore: FileStore,
        event_bus: EventBus,
        command_router: CommandRouter,
        env: Env,
        renderer: Renderer,
        resolver: WikilinkResolver,
        watcher: FileWatcher,
        on_state_change_requested: Callable[[EditorAreaState], None],
    ) -> None:
        self._filestore = filestore
        self._event_bus = event_bus
        self._command_router = command_router
        self._env = env
        self._renderer = renderer
        self._resolver = resolver
        self._watcher = watcher
        self._on_state_change_requested = on_state_change_requested

        self.logger = logging.getLogger("oatbrain.editor_area")

        self.groups_panes: Dict[str, GroupPane] = {}  # group_id -> GroupPane
        self.focused_editor: Optional[Editor] = None
        self._state: Optional[EditorAreaState] = None
        self._app_state: Optional[AppState] = None

        self._root_widget = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._paned_root: Optional[Gtk.Paned] = None
        self.widget = self._root_widget

        # Track Paned widgets in order from root-most to leaf-most for fraction mapping
        self._paned_widgets: List[Gtk.Paned] = []
        self._paned_handler_ids: Dict[Gtk.Paned, int] = {}

        self._last_active_gids: List[str] = []
        self._dirty_states: Dict[str, bool] = {}  # tab_id -> is_dirty
        self._is_syncing = False

        # Theme caching for new editors
        self._current_theme_css: Optional[str] = None
        self._current_theme_id: str = "solarized-light"
        self._current_source_scheme: Optional[str] = None

        # Stats tracking
        self._word_counts: Dict[int, int] = {}  # ed_id -> count
        self._dirty_states_by_id: Dict[int, bool] = {}  # ed_id -> dirty

        self._event_bus.subscribe(TabPathChanged, self._on_tab_path_changed)
        self._event_bus.subscribe(TabTitleChanged, self._on_tab_title_changed)
        self._event_bus.subscribe(WordCountChanged, self._on_word_count_changed)
        self._event_bus.subscribe(DirtyStateChanged, self._on_dirty_state_changed)

    def _on_tab_title_changed(self, event: TabTitleChanged) -> None:
        """
        Update the title of a specific tab in the state when it changes in the editor.
        """
        if not self._state:
            return

        # We need to reconstruct the EditorAreaState with the updated tab title.
        new_groups = []
        for group in self._state.groups:
            new_tabs = []
            for tab in group.tabs:
                if tab.tab_id == event.tab_id:
                    # Update matching tab title
                    new_tabs.append(
                        TabState(
                            tab_id=tab.tab_id,
                            open_file=tab.open_file,
                            is_new=tab.is_new,
                            title=event.title,
                            target_dir=tab.target_dir,
                            mode=tab.mode,
                            zoom=tab.zoom,
                            preview_zoom=tab.preview_zoom,
                        )
                    )
                else:
                    new_tabs.append(tab)

            new_groups.append(
                GroupState(
                    group_id=group.group_id,
                    tabs=tuple(new_tabs),
                    active_tab_index=group.active_tab_index,
                )
            )

        self._on_state_change_requested(
            EditorAreaState(
                groups=tuple(new_groups),
                divider_fractions=self._state.divider_fractions,
                focused_group_index=self._state.focused_group_index,
            )
        )

    def _on_tab_path_changed(self, event: TabPathChanged) -> None:
        # Update the state with the new path for this tab
        if not self._state:
            return

        new_groups = []
        for g in self._state.groups:
            new_tabs = []
            for t in g.tabs:
                if t.tab_id == event.tab_id:
                    new_tabs.append(
                        TabState(
                            tab_id=t.tab_id,
                            open_file=event.new_path,
                            mode=t.mode,
                            zoom=t.zoom,
                            preview_zoom=t.preview_zoom,
                        )
                    )
                else:
                    new_tabs.append(t)
            new_groups.append(
                GroupState(
                    group_id=g.group_id,
                    tabs=tuple(new_tabs),
                    active_tab_index=g.active_tab_index,
                )
            )

        self._on_state_change_requested(
            EditorAreaState(
                groups=tuple(new_groups),
                divider_fractions=self._state.divider_fractions,
                focused_group_index=self._state.focused_group_index,
            )
        )

    def update_from_state(self, ea_state: EditorAreaState, app_state: AppState) -> None:
        self._state = ea_state
        self._app_state = app_state

        # 1. Update/Rebuild the Paned tree
        self._sync_paned_structure(ea_state)

        # 2. Compute disambiguated titles
        titles = self._compute_tab_titles(ea_state)

        # 3. Update each GroupPane
        for i, group_state in enumerate(ea_state.groups):
            gid = group_state.group_id
            pane = self.groups_panes[gid]
            pane.update_from_state(
                group_state, app_state, self._create_editor, titles, self._dirty_states
            )

    def _create_editor(self, tab_state: TabState) -> Editor:
        ed = Editor(
            filestore=self._filestore,
            event_bus=self._event_bus,
            command_router=self._command_router,
            env=self._env,
            vault_root=self._app_state.vault_root if self._app_state else None,
            renderer=self._renderer,
            resolver=self._resolver,
            watcher=self._watcher,
            tab_id=tab_state.tab_id,
        )
        ed.on_path_changed = lambda new_path: self._event_bus.publish(
            TabPathChanged(tab_id=tab_state.tab_id, new_path=new_path)
        )
        if self._app_state:
            ed.update_from_state(tab_state, self._app_state)
        # Apply current theme if available
        if self._current_theme_css:
            ed.set_theme_css(self._current_theme_css, self._current_theme_id)
        if self._current_source_scheme:
            ed.apply_source_scheme(self._current_source_scheme)

        return ed

    def _on_word_count_changed(self, event: WordCountChanged) -> None:
        if event.sender_id:
            self._word_counts[event.sender_id] = event.count
            self._notify_stats_if_focused(event.sender_id)

    def _on_dirty_state_changed(self, event: DirtyStateChanged) -> None:
        if event.sender_id:
            self._dirty_states_by_id[event.sender_id] = event.dirty
            self._notify_stats_if_focused(event.sender_id)

    def _notify_stats_if_focused(self, sender_id: int) -> None:
        if self.focused_editor and id(self.focused_editor) == sender_id:
            self._publish_focused_stats()

    def _publish_focused_stats(self) -> None:
        if not self.focused_editor:
            self._event_bus.publish(FocusedTabStats(None, 0, False))
            return

        ed_id = id(self.focused_editor)
        self._event_bus.publish(
            FocusedTabStats(
                path=self.focused_editor._current_path,
                word_count=self._word_counts.get(ed_id, 0),
                is_dirty=self._dirty_states_by_id.get(ed_id, False),
            )
        )

    def _sync_paned_structure(self, ea_state: EditorAreaState) -> None:
        """
        Synchronize the GTK widget structure (Paned widgets and GroupPanes)
        to match the EditorAreaState.
        """
        self._is_syncing = True
        try:
            active_gids = [g.group_id for g in ea_state.groups]

            # 0. Check if the structure actually changed
            if self._last_active_gids == active_gids and all(
                gid in self.groups_panes for gid in active_gids
            ):
                return

            self._unparent_all_group_widgets()
            self._cleanup_removed_groups(active_gids)
            self._clear_root_widget()
            self._ensure_active_groups_exist(active_gids)

            if not active_gids:
                return

            self._build_paned_tree(active_gids, ea_state.divider_fractions)

            self._root_widget.append(self._paned_root)
            self._last_active_gids = active_gids
        finally:
            self._is_syncing = False

    def _unparent_all_group_widgets(self) -> None:
        """Unparent all current group widgets to prepare for restructuring."""
        for pane in self.groups_panes.values():
            if pane.widget.get_parent():
                pane.widget.unparent()

    def _cleanup_removed_groups(self, active_gids: List[str]) -> None:
        """Destroy GroupPanes that are no longer in the state."""
        to_remove = [gid for gid in self.groups_panes if gid not in active_gids]
        for gid in to_remove:
            pane = self.groups_panes.pop(gid)
            pane.destroy()

    def _clear_root_widget(self) -> None:
        """Clear the root widget and dismantle the old Paned tree."""
        while child := self._root_widget.get_first_child():
            self._root_widget.remove(child)

        if self._paned_root:
            self._unparent_paned_recursive(self._paned_root)
            self._paned_root = None

    def _ensure_active_groups_exist(self, active_gids: List[str]) -> None:
        """Ensure that a GroupPane exists for every active group ID."""
        for gid in active_gids:
            if gid not in self.groups_panes:
                self.groups_panes[gid] = GroupPane(
                    group_id=gid,
                    on_tab_switched=self._on_tab_switched,
                    on_close_requested=self._on_close_requested,
                    on_split_requested=self._on_split_requested,
                    on_new_tab_requested=self._on_new_tab_requested,
                    on_editor_focused=self._on_editor_focused,
                )

    def _build_paned_tree(
        self, active_gids: List[str], divider_fractions: tuple
    ) -> None:
        """Build the nested Gtk.Paned structure for the given groups."""
        panes = [self.groups_panes[gid].widget for gid in active_gids]
        self._paned_widgets.clear()
        self._paned_handler_ids.clear()

        if len(panes) == 1:
            self._paned_root = panes[0]
        else:
            # Build from right to left: RootPaned(Pane0, Paned(Pane1, ...))
            current = panes[-1]
            temp_paneds = []
            for i in range(len(panes) - 2, -1, -1):
                p = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
                p.set_wide_handle(True)
                p.set_start_child(panes[i])
                p.set_end_child(current)

                # Prevent zero-size tabs by disabling shrink (§17.2)
                p.set_shrink_start_child(False)
                p.set_shrink_end_child(False)

                temp_paneds.append(p)
                current = p

            # temp_paneds is [Leaf-most-Paned, ..., Root-most-Paned]
            # Reverse it to have [Root, ..., Leaf]
            self._paned_widgets = list(reversed(temp_paneds))
            self._paned_root = current

            # Connect signals and apply fractions
            for i, p in enumerate(self._paned_widgets):
                if i < len(divider_fractions):
                    frac = divider_fractions[i]
                    GLib.idle_add(lambda p=p, f=frac: self._set_paned_fraction(p, f))

                handler_id = p.connect("notify::position", self._on_divider_moved)
                self._paned_handler_ids[p] = handler_id

    def _unparent_paned_recursive(self, widget: Gtk.Widget) -> None:
        if isinstance(widget, Gtk.Paned):
            c1 = widget.get_start_child()
            c2 = widget.get_end_child()
            if c1:
                self._unparent_paned_recursive(c1)
                widget.set_start_child(None)
            if c2:
                self._unparent_paned_recursive(c2)
                widget.set_end_child(None)

    def destroy(self) -> None:
        """Cleanup subscriptions and widgets."""
        self._event_bus.unsubscribe(TabPathChanged, self._on_tab_path_changed)
        self._event_bus.unsubscribe(WordCountChanged, self._on_word_count_changed)
        self._event_bus.unsubscribe(DirtyStateChanged, self._on_dirty_state_changed)

        for pane in self.groups_panes.values():
            pane.destroy()
        self.groups_panes.clear()

    def set_theme_css(self, css: str, theme_id: str) -> None:
        self._current_theme_css = css
        self._current_theme_id = theme_id
        for pane in self.groups_panes.values():
            for ed in pane.editors.values():
                ed.set_theme_css(css, theme_id)

    def apply_source_scheme(self, scheme_id: str) -> None:
        self._current_source_scheme = scheme_id
        for pane in self.groups_panes.values():
            for ed in pane.editors.values():
                ed.apply_source_scheme(scheme_id)

    def _set_paned_fraction(self, paned: Gtk.Paned, fraction: float) -> bool:
        width = paned.get_width()
        if width > 0:
            handler_id = self._paned_handler_ids.get(paned)
            if handler_id is not None:
                paned.handler_block(handler_id)
                try:
                    paned.set_position(int(width * fraction))
                finally:
                    paned.handler_unblock(handler_id)
            else:
                paned.set_position(int(width * fraction))
            return False
        return True

    def _on_divider_moved(self, paned: Gtk.Paned, _pspec: Any) -> None:
        if self._is_syncing or not self._state or not self._paned_widgets:
            return

        # Calculate all current fractions
        new_fractions = []
        changed = False
        for i, p in enumerate(self._paned_widgets):
            width = p.get_width()
            if width > 0:
                pos = p.get_position()
                frac = round(float(pos) / width, 3)  # Round to 3 decimal places
                new_fractions.append(frac)

                old_frac = (
                    self._state.divider_fractions[i]
                    if i < len(self._state.divider_fractions)
                    else 0.5
                )
                if abs(frac - old_frac) > 0.001:
                    changed = True
            else:
                old_frac = (
                    self._state.divider_fractions[i]
                    if i < len(self._state.divider_fractions)
                    else 0.5
                )
                new_fractions.append(old_frac)

        if changed:
            self._on_state_change_requested(
                EditorAreaState(
                    groups=self._state.groups,
                    divider_fractions=tuple(new_fractions),
                    focused_group_index=self._state.focused_group_index,
                )
            )

    def _on_tab_switched(self, group_id: str, index: int) -> None:
        if not self._state:
            return

        new_groups = []
        for g in self._state.groups:
            if g.group_id == group_id:
                new_groups.append(
                    GroupState(group_id=g.group_id, tabs=g.tabs, active_tab_index=index)
                )
            else:
                new_groups.append(g)

        self._on_state_change_requested(
            EditorAreaState(
                groups=tuple(new_groups),
                divider_fractions=self._state.divider_fractions,
                focused_group_index=self._state.focused_group_index,
            )
        )

    def _on_new_tab_requested(self, group_id: str) -> None:
        if not self._state:
            return

        # Find the group index
        idx = -1
        for i, g in enumerate(self._state.groups):
            if g.group_id == group_id:
                idx = i
                break

        if idx == -1:
            return

        # Update focus to this group and then add tab
        # Actually we can just do it in one go
        g = self._state.groups[idx]
        current_tab = g.tabs[g.active_tab_index]

        new_tab = TabState(
            open_file=current_tab.open_file,
            mode=current_tab.mode,
            zoom=current_tab.zoom,
            preview_zoom=current_tab.preview_zoom,
        )

        new_tabs = list(g.tabs)
        new_tabs.insert(g.active_tab_index + 1, new_tab)

        new_groups = list(self._state.groups)
        new_groups[idx] = GroupState(
            group_id=g.group_id,
            tabs=tuple(new_tabs),
            active_tab_index=g.active_tab_index + 1,
        )

        self._on_state_change_requested(
            EditorAreaState(
                groups=tuple(new_groups),
                divider_fractions=self._state.divider_fractions,
                focused_group_index=idx,
            )
        )

    def _on_close_requested(self, group_id: str, tab_id: str) -> None:
        if not self._state:
            return

        new_groups = []
        for g in self._state.groups:
            if g.group_id == group_id:
                new_tabs = [t for t in g.tabs if t.tab_id != tab_id]
                if not new_tabs:
                    continue  # Empty group -> will be removed

                new_active = min(g.active_tab_index, len(new_tabs) - 1)
                new_groups.append(
                    GroupState(
                        group_id=g.group_id,
                        tabs=tuple(new_tabs),
                        active_tab_index=new_active,
                    )
                )
            else:
                new_groups.append(g)

        if not new_groups:
            new_groups = [GroupState()]  # Fallback to blank

        expected = len(new_groups) - 1
        # Balance widths equally among all groups (§17.2)
        fractions = [1.0 / (len(new_groups) - i) for i in range(expected)]

        self._on_state_change_requested(
            EditorAreaState(
                groups=tuple(new_groups),
                divider_fractions=tuple(fractions),
                focused_group_index=0,  # Resets focus if root changed
            )
        )

    def _on_split_requested(self, group_id: str, tab_id: str) -> None:
        if not self._state:
            return

        source_tab: Optional[TabState] = None
        for g in self._state.groups:
            for t in g.tabs:
                if t.tab_id == tab_id:
                    source_tab = t
                    break

        if not source_tab:
            return

        new_tab = TabState(
            open_file=source_tab.open_file,
            mode=source_tab.mode,
            zoom=source_tab.zoom,
            preview_zoom=source_tab.preview_zoom,
        )

        new_groups: List[GroupState] = []
        new_focus_idx = self._state.focused_group_index
        for g in self._state.groups:
            new_groups.append(g)
            if g.group_id == group_id:
                new_groups.append(GroupState(tabs=(new_tab,), active_tab_index=0))
                new_focus_idx = len(new_groups) - 1

        expected = len(new_groups) - 1
        # Balance widths equally among all groups (§17.2)
        fractions = [1.0 / (len(new_groups) - i) for i in range(expected)]

        self._on_state_change_requested(
            EditorAreaState(
                groups=tuple(new_groups),
                divider_fractions=tuple(fractions),
                focused_group_index=new_focus_idx,
            )
        )

    def _on_editor_focused(self, editor: Editor) -> None:
        self.focused_editor = editor
        if not self._state:
            return

        for i, g in enumerate(self._state.groups):
            pane = self.groups_panes.get(g.group_id)
            if pane and editor in pane.editors.values():
                if self._state.focused_group_index != i:
                    self._on_state_change_requested(
                        EditorAreaState(
                            groups=self._state.groups,
                            divider_fractions=self._state.divider_fractions,
                            focused_group_index=i,
                        )
                    )
                break
        self._publish_focused_stats()

    def _compute_tab_titles(self, ea_state: EditorAreaState) -> Dict[str, str]:
        return compute_tab_titles(ea_state)

    def handle_command(self, cmd: Any) -> bool:
        if isinstance(cmd, NewTab):
            self._handle_new_tab()
            return True
        if isinstance(cmd, NewNote):
            self._handle_new_note(cmd.target_dir)
            return True
        if isinstance(cmd, CloseTab):
            if self._state:
                fg = self._state.groups[self._state.focused_group_index]
                if fg.tabs:
                    tid = fg.tabs[fg.active_tab_index].tab_id
                    self._on_close_requested(fg.group_id, tid)
                    return True
        if isinstance(cmd, SplitGroupRight):
            if self._state:
                fg = self._state.groups[self._state.focused_group_index]
                if fg.tabs:
                    tid = fg.tabs[fg.active_tab_index].tab_id
                    self._on_split_requested(fg.group_id, tid)
                    return True

        if isinstance(cmd, OpenFile):
            self._handle_open_file(cmd.path)
            return True
        return False

    def _handle_new_tab(self) -> None:
        if not self._state:
            return

        idx = self._state.focused_group_index
        g = self._state.groups[idx]
        current_tab = g.tabs[g.active_tab_index]

        new_tab = TabState(
            open_file=current_tab.open_file,
            mode=current_tab.mode,
            zoom=current_tab.zoom,
            preview_zoom=current_tab.preview_zoom,
        )

        new_tabs = list(g.tabs)
        new_tabs.insert(g.active_tab_index + 1, new_tab)

        new_groups = list(self._state.groups)
        new_groups[idx] = GroupState(
            group_id=g.group_id,
            tabs=tuple(new_tabs),
            active_tab_index=g.active_tab_index + 1,
        )

        self._on_state_change_requested(
            EditorAreaState(
                groups=tuple(new_groups),
                divider_fractions=self._state.divider_fractions,
                focused_group_index=idx,
            )
        )

    def _handle_new_note(self, target_dir: Optional[str] = None) -> None:
        """
        Handle NewNote command by creating a new in-memory TabState and adding
        it to the focused group. The tab is marked as is_new=True to trigger
        the Save As workflow upon first save.
        """
        if not self._state:
            return

        idx = self._state.focused_group_index
        g = self._state.groups[idx]

        new_tab = TabState(
            open_file=None,
            is_new=True,
            title="Untitled",
            target_dir=target_dir,
        )

        new_tabs = list(g.tabs)
        new_tabs.insert(g.active_tab_index + 1, new_tab)

        new_groups = list(self._state.groups)
        new_groups[idx] = GroupState(
            group_id=g.group_id,
            tabs=tuple(new_tabs),
            active_tab_index=g.active_tab_index + 1,
        )

        self._on_state_change_requested(
            EditorAreaState(
                groups=tuple(new_groups),
                divider_fractions=self._state.divider_fractions,
                focused_group_index=idx,
            )
        )

    def _handle_open_file(self, path: VaultPath) -> None:
        if not self._state:
            return

        idx = self._state.focused_group_index
        g = self._state.groups[idx]

        new_tabs = []
        for i, t in enumerate(g.tabs):
            if i == g.active_tab_index:
                new_tabs.append(
                    TabState(
                        tab_id=t.tab_id,
                        open_file=path,
                        mode=t.mode,
                        zoom=t.zoom,
                        preview_zoom=t.preview_zoom,
                    )
                )
            else:
                new_tabs.append(t)

        new_groups = list(self._state.groups)
        new_groups[idx] = GroupState(
            group_id=g.group_id,
            tabs=tuple(new_tabs),
            active_tab_index=g.active_tab_index,
        )

        self._on_state_change_requested(
            EditorAreaState(
                groups=tuple(new_groups),
                divider_fractions=self._state.divider_fractions,
                focused_group_index=idx,
            )
        )
