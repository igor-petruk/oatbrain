import gi
import logging
from typing import Dict, Callable

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, GLib  # noqa: E402

from oatbrain.core.state import GroupState, AppState, TabState  # noqa: E402
from oatbrain.ui.editor import Editor  # noqa: E402

log = logging.getLogger(__name__)


class GroupPane:
    """Wraps a Gtk.Notebook to manage a collection of Editor tabs."""

    def __init__(
        self,
        group_id: str,
        on_tab_switched: Callable[[str, int], None],
        on_close_requested: Callable[[str, str], None],
        on_split_requested: Callable[[str, str], None],
        on_new_tab_requested: Callable[[str], None],
        on_editor_focused: Callable[[Editor], None],
    ) -> None:
        self.group_id = group_id
        self._on_tab_switched = on_tab_switched
        self._on_close_requested = on_close_requested
        self._on_split_requested = on_split_requested
        self._on_new_tab_requested = on_new_tab_requested
        self._on_editor_focused = on_editor_focused

        self.notebook = Gtk.Notebook()
        self.notebook.set_scrollable(True)
        self.notebook.set_show_border(False)
        self.notebook.add_css_class("oatbrain-group-pane")

        # Action area buttons (end of tab bar)
        self._action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        self._btn_new_tab = Gtk.Button.new_from_icon_name("list-add-symbolic")
        self._btn_new_tab.set_tooltip_text("New Tab")
        self._btn_new_tab.set_has_frame(False)
        self._btn_new_tab.connect(
            "clicked", lambda *_: self._on_new_tab_requested(self.group_id)
        )
        self._action_box.append(self._btn_new_tab)

        self._btn_split = Gtk.Button.new_from_icon_name("view-dual-symbolic")
        self._btn_split.set_tooltip_text("Split Group Right")
        self._btn_split.set_has_frame(False)
        self._btn_split.connect("clicked", self._on_split_clicked)
        self._action_box.append(self._btn_split)

        self.notebook.set_action_widget(self._action_box, Gtk.PackType.END)

        self.editors: Dict[str, Editor] = {}  # tab_id -> Editor
        self.widget = self.notebook

        self.notebook.connect("switch-page", self._on_notebook_switch)

    def _on_notebook_switch(
        self, _nb: Gtk.Notebook, _page: Gtk.Widget, index: int
    ) -> None:
        self._on_tab_switched(self.group_id, index)

    def _on_split_clicked(self, _btn: Gtk.Button) -> None:
        # Split the currently focused tab in THIS group
        idx = self.notebook.get_current_page()
        if idx >= 0:
            # We need the tab_id for the current page
            # We'll find it by matching the widget
            child = self.notebook.get_nth_page(idx)
            found_tid = None
            for tid, ed in self.editors.items():
                if ed.widget == child:
                    found_tid = tid
                    break

            if found_tid:
                self._on_split_requested(self.group_id, found_tid)
            else:
                log.warning(
                    f"Could not find tab_id for index {idx} in group {self.group_id}"
                )

    def update_from_state(
        self,
        group_state: GroupState,
        app_state: AppState,
        editor_factory: Callable[[TabState], Editor],
        titles: Dict[str, str],  # tab_id -> display title
        dirty_states: Dict[str, bool],  # tab_id -> is_dirty
    ) -> None:
        # 1. Remove editors that are no longer in state
        tab_ids_in_state = {t.tab_id for t in group_state.tabs}
        to_remove = [tid for tid in self.editors if tid not in tab_ids_in_state]
        for tid in to_remove:
            ed = self.editors.pop(tid)
            idx = self.notebook.page_num(ed.widget)
            if idx >= 0:
                self.notebook.remove_page(idx)
            ed.destroy()

        # 2. Add or update existing
        for i, tab_state in enumerate(group_state.tabs):
            tid = tab_state.tab_id
            title = titles.get(tid, "Untitled")
            is_dirty = dirty_states.get(tid, False)

            if tid not in self.editors:
                ed = editor_factory(tab_state)
                ed.on_focused = self._on_editor_focused
                # Store current label state on the editor for caching
                ed._last_label_title = title
                ed._last_label_dirty = is_dirty

                self.editors[tid] = ed

                label = self._create_tab_label(
                    tid,
                    title,
                    is_dirty,
                    on_close=lambda: self._on_close_requested(self.group_id, tid),
                )
                self.notebook.insert_page(ed.widget, label, i)
                self.notebook.set_tab_reorderable(ed.widget, True)
                self.notebook.set_tab_detachable(ed.widget, False)
            else:
                ed = self.editors[tid]
                ed.update_from_state(tab_state, app_state)

                # Only update label if something changed
                if ed._last_label_title != title or ed._last_label_dirty != is_dirty:
                    page = ed.widget
                    new_label = self._create_tab_label(
                        tid,
                        title,
                        is_dirty,
                        on_close=lambda: self._on_close_requested(self.group_id, tid),
                    )
                    self.notebook.set_tab_label(page, new_label)
                    ed._last_label_title = title
                    ed._last_label_dirty = is_dirty

                # Ensure correct order (rarely changes during split, but good to have)
                current_idx = self.notebook.page_num(ed.widget)
                if current_idx != i:
                    self.notebook.reorder_child(ed.widget, i)

        # 3. Ensure correct active tab
        if self.notebook.get_current_page() != group_state.active_tab_index:
            # Block signal to avoid re-triggering on_tab_switched
            # when we are syncing from state
            self.notebook.handler_block_by_func(self._on_notebook_switch)
            self.notebook.set_current_page(group_state.active_tab_index)
            self.notebook.handler_unblock_by_func(self._on_notebook_switch)

    @staticmethod
    def _create_tab_label(
        tab_id: str, title: str, is_dirty: bool, on_close: Callable[[], None]
    ) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        label = Gtk.Label()

        if " [" in title and title.endswith("]"):
            main_title, path_segment = title.rsplit(" [", 1)
            path_segment = path_segment[:-1]
            escaped_main = GLib.markup_escape_text(main_title)
            escaped_path = GLib.markup_escape_text(path_segment)
            color = "#e67e22" if is_dirty else None
            span_open = f"<span color='{color}'>" if color else "<span>"
            markup = (
                f"{span_open}{escaped_main}</span> "
                f"<span color='#888' size='small'>{escaped_path}</span>"
            )
            label.set_markup(markup)
        else:
            escaped = GLib.markup_escape_text(title)
            if is_dirty:
                label.set_markup(f"<span color='#e67e22'>{escaped}</span>")
            else:
                label.set_text(title)

        box.append(label)

        close_btn = Gtk.Button.new_from_icon_name("window-close-symbolic")
        close_btn.add_css_class("flat")
        close_btn.add_css_class("tab-close-button")
        close_btn.set_has_frame(False)
        close_btn.connect("clicked", lambda *_: on_close())
        box.append(close_btn)

        return box

    def destroy(self) -> None:
        """Cleanup all editors."""
        for ed in self.editors.values():
            ed.destroy()
        self.editors.clear()
