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

        self._dirty_states: Dict[str, bool] = {}  # tab_id -> is_dirty

        # Theme caching for new editors
        self._current_theme_css: Optional[str] = None
        self._current_theme_id: str = "solarized-light"
        self._current_source_scheme: Optional[str] = None

        # Stats tracking
        self._word_counts: Dict[int, int] = {}  # ed_id -> count
        self._dirty_states_by_id: Dict[int, bool] = {}  # ed_id -> dirty

        self._event_bus.subscribe(TabPathChanged, self._on_tab_path_changed)
        self._event_bus.subscribe(WordCountChanged, self._on_word_count_changed)
        self._event_bus.subscribe(DirtyStateChanged, self._on_dirty_state_changed)

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
        active_gids = [g.group_id for g in ea_state.groups]
        
        # 0. Check if the structure actually changed (number of groups or their IDs/order)
        if hasattr(self, "_last_active_gids") and self._last_active_gids == active_gids:
            return
        self._last_active_gids = active_gids

        # 1. Collect all current group widgets and ensure they are unparented
        # from any previous Paned or Box structure.
        for gid, pane in self.groups_panes.items():
            if pane.widget.get_parent():
                pane.widget.unparent()

        # 2. Remove old panes that are no longer active
        to_remove = [gid for gid in self.groups_panes if gid not in active_gids]
        for gid in to_remove:
            pane = self.groups_panes.pop(gid)
            pane.destroy()

        # 3. Clear the root widget entirely
        while (child := self._root_widget.get_first_child()):
            self._root_widget.remove(child)

        # 4. Dismantle the old Paned tree if it exists
        if self._paned_root:
            self._unparent_paned_recursive(self._paned_root)
            self._paned_root = None

        # 5. Ensure all active panes exist
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

        if not active_gids:
            return

        # 6. Build a new sequence of Paned widgets or just use the single pane
        panes = [self.groups_panes[gid].widget for gid in active_gids]
        self._paned_widgets.clear()

        if len(panes) == 1:
            self._paned_root = panes[0]
        else:
            # Build from right to left: RootPaned(Pane0, Paned(Pane1, ...))
            # The indices in ea_state.divider_fractions correspond to i=0, 1, 2...
            # where i=0 is the root-most Paned.
            
            # To apply fractions correctly, we need the Paned widgets in order.
            current = panes[-1]
            temp_paneds = []
            for i in range(len(panes) - 2, -1, -1):
                p = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
                p.set_wide_handle(True)
                p.set_start_child(panes[i])
                p.set_end_child(current)
                temp_paneds.append(p)
                current = p
            
            # temp_paneds is [Leaf-most-Paned, ..., Root-most-Paned]
            # Reverse it to have [Root, ..., Leaf]
            self._paned_widgets = list(reversed(temp_paneds))
            self._paned_root = current

            # Connect signals and apply fractions
            for i, p in enumerate(self._paned_widgets):
                if i < len(ea_state.divider_fractions):
                    frac = ea_state.divider_fractions[i]
                    GLib.idle_add(lambda p=p, f=frac: self._set_paned_fraction(p, f))

                p.connect("notify::position", self._on_divider_moved)

        self._root_widget.append(self._paned_root)

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
            paned.set_position(int(width * fraction))
            return False
        return True

    def _on_divider_moved(self, paned: Gtk.Paned, _pspec: Any) -> None:
        if not self._state or not self._paned_widgets:
            return

        # Calculate all current fractions
        new_fractions = []
        changed = False
        for i, p in enumerate(self._paned_widgets):
            width = p.get_width()
            if width > 0:
                pos = p.get_position()
                frac = round(float(pos) / width, 3) # Round to 3 decimal places
                new_fractions.append(frac)
                
                old_frac = self._state.divider_fractions[i] if i < len(self._state.divider_fractions) else 0.5
                if abs(frac - old_frac) > 0.001:
                    changed = True
            else:
                old_frac = self._state.divider_fractions[i] if i < len(self._state.divider_fractions) else 0.5
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

        self._on_state_change_requested(
            EditorAreaState(
                groups=tuple(new_groups),
                divider_fractions=self._state.divider_fractions,
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
        fractions = list(self._state.divider_fractions)[:expected]
        while len(fractions) < expected:
            fractions.append(0.5)

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
