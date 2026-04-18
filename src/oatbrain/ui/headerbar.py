from gi.repository import Adw, Gtk, GLib, Gio
from oatbrain.core.events.state import StateUpdated
from oatbrain.core.bus import EventBus


class HeaderBar:
    """Three-section header bar visually aligned to the three panes."""

    def __init__(self, event_bus: EventBus) -> None:
        self.widget = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.widget.add_css_class("oatbrain-headerbar-container")

        # --- Left header (tree pane) ---
        self._left_bar = Adw.HeaderBar()
        self._left_bar.set_show_start_title_buttons(False)
        self._left_bar.set_show_end_title_buttons(False)
        self._left_bar.add_css_class("oatbrain-headerbar")

        self._hamburger_btn = Gtk.MenuButton(icon_name="open-menu-symbolic")
        self._hamburger_btn.set_tooltip_text("Menu")

        self.menu = Gio.Menu()
        self.menu.append("Open config file", "app.open_config")
        theme_section = Gio.Menu()
        theme_section.append("Light Theme", "app.set_theme_light")
        theme_section.append("Dark Theme", "app.set_theme_dark")
        theme_section.append("High Contrast Dark", "app.set_theme_high_contrast")
        self.menu.append_section("Theme", theme_section)
        self._hamburger_btn.set_menu_model(self.menu)

        self.tree_toggle = Gtk.ToggleButton(icon_name="sidebar-show-symbolic")
        self.tree_toggle.set_active(True)
        self.tree_toggle.set_tooltip_text("Toggle File Tree (Ctrl+B)")

        self._new_note_btn = Gtk.Button(icon_name="document-new-symbolic")
        self._new_note_btn.set_tooltip_text("New Note (Ctrl+N)")

        left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        left_box.append(self._hamburger_btn)
        left_box.append(self.tree_toggle)
        left_box.append(self._new_note_btn)
        self._left_bar.pack_start(left_box)
        self._left_bar.set_title_widget(Gtk.Box())  # suppress default title

        # --- Middle header (editor pane) ---
        self._middle_bar = Adw.HeaderBar()
        self._middle_bar.set_show_start_title_buttons(False)
        self._middle_bar.set_show_end_title_buttons(False)
        self._middle_bar.set_hexpand(True)
        self._middle_bar.add_css_class("oatbrain-headerbar")

        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title_box.set_halign(Gtk.Align.CENTER)

        self._title_label = Gtk.Label(label="oatbrain")
        self._title_label.add_css_class("title")

        self._unsaved_dot = Gtk.Label(label="●")
        self._unsaved_dot.set_visible(False)
        self._unsaved_dot.set_tooltip_text("Unsaved changes")

        self._readonly_lock = Gtk.Image.new_from_icon_name("changes-prevent-symbolic")
        self._readonly_lock.set_visible(False)
        self._readonly_lock.set_tooltip_text("Read-only")

        title_box.append(self._title_label)
        title_box.append(self._unsaved_dot)
        title_box.append(self._readonly_lock)
        self._middle_bar.set_title_widget(title_box)

        # Terminal toggle in middle bar — visible when terminal is open
        self.terminal_toggle = Gtk.ToggleButton(icon_name="utilities-terminal-symbolic")
        self.terminal_toggle.set_active(True)
        self.terminal_toggle.set_tooltip_text("Toggle Terminal (Ctrl+`)")
        self._middle_bar.pack_end(self.terminal_toggle)

        # --- Right header (terminal pane) — always visible, owns window controls ---
        self._right_bar = Adw.HeaderBar()
        self._right_bar.set_show_start_title_buttons(False)
        self._right_bar.set_show_end_title_buttons(True)
        self._right_bar.set_decoration_layout(":minimize,maximize,close")
        self._right_bar.add_css_class("oatbrain-headerbar")
        self._right_bar.set_title_widget(Gtk.Box())  # suppress default title

        # Secondary terminal toggle in right bar — visible when terminal is collapsed
        self._right_terminal_toggle = Gtk.ToggleButton(
            icon_name="utilities-terminal-symbolic"
        )
        self._right_terminal_toggle.set_active(True)
        self._right_terminal_toggle.set_tooltip_text("Toggle Terminal (Ctrl+`)")
        self._right_terminal_toggle.set_visible(False)
        self._right_bar.pack_end(self._right_terminal_toggle)

        # Keep both toggles in sync
        self.terminal_toggle.connect("toggled", self._on_primary_toggled)
        self._right_terminal_toggle.connect("toggled", self._on_secondary_toggled)

        # Assemble
        self.widget.append(self._left_bar)
        self.widget.append(self._middle_bar)
        self.widget.append(self._right_bar)

        event_bus.subscribe(StateUpdated, self._on_state_updated)

    def _on_primary_toggled(self, btn: Gtk.ToggleButton) -> None:
        """Sync secondary toggle and swap visibility."""
        active = btn.get_active()
        self._right_terminal_toggle.handler_block_by_func(self._on_secondary_toggled)
        self._right_terminal_toggle.set_active(active)
        self._right_terminal_toggle.handler_unblock_by_func(self._on_secondary_toggled)
        # When terminal collapses, move toggle to right bar
        self.terminal_toggle.set_visible(active)
        self._right_terminal_toggle.set_visible(not active)

    def _on_secondary_toggled(self, btn: Gtk.ToggleButton) -> None:
        """Propagate secondary toggle to primary (which drives the real logic)."""
        self.terminal_toggle.handler_block_by_func(self._on_primary_toggled)
        self.terminal_toggle.set_active(btn.get_active())
        self.terminal_toggle.handler_unblock_by_func(self._on_primary_toggled)
        # Emit toggled on primary so window.py's signal fires
        self.terminal_toggle.emit("toggled")

    def sync_pane_widths(self, tree_width: int, terminal_width: int) -> None:
        """Resize left/right header sections to match pane widths."""
        self._left_bar.set_size_request(tree_width, -1)
        self._right_bar.set_size_request(terminal_width, -1)

    def _on_state_updated(self, event: StateUpdated) -> None:
        GLib.idle_add(self._update_ui, event)

    def _update_ui(self, event: StateUpdated) -> bool:
        state = event.state
        if state.editor.open_file:
            self._title_label.set_text(str(state.editor.open_file.path.name))
            self._unsaved_dot.set_visible(state.editor.is_dirty)
        else:
            self._title_label.set_text("oatbrain")
            self._unsaved_dot.set_visible(False)
            self._readonly_lock.set_visible(False)
        return bool(GLib.SOURCE_REMOVE)
