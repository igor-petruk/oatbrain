# SPEC_MULTITAB: Multi-Tab & Split Edit/Preview Support

## Overview
This specification outlines the architecture and UX for adding multi-tab and split-screen capabilities to the oatbrain editor. Currently, the editor uses a `Gtk.Stack` to switch between a source view and a preview for a single file. The goal is to support:
1. **Multi-Tab Interface:** Multiple files open simultaneously in distinct tabs (`Adw.TabView`).
2. **Split-Screen Edit/Preview:** Viewing the source code and the rendered preview of a single file side-by-side.

## Mode 1: Multiple Tabs (`Adw.TabView`)
### Architecture
- **Widget:** Use `Adw.TabView` combined with `Adw.TabBar` in `window.py`.
- **State Management:** `app_state.py` must be updated. Instead of a single `editor` field, `AppState` should maintain a list of open tabs and the index/ID of the currently active tab.
- **Components:** Each tab will contain its own `Editor` instance.
- **Zoom Level:** **Global Zoom.** Zooming in one tab will update the zoom level for all open tabs.
- **Uniqueness:** **Prevent Duplicates.** A file cannot be opened in multiple tabs. If the user attempts to open an already open file, the existing tab will be focused.

### UX Behaviors
- **Opening Files:** **Explicit Tabs.** Single clicking in the tree will replace the content of the *current* tab. Opening a *new* tab requires an explicit action (e.g., Middle-click or Context Menu > Open in New Tab).
- **Vim Mode & State:** Each tab maintains its own Vim state and undo history via GTK `GtkSource.Buffer`.

## Mode 2: Split-Screen Edit & Preview
### Architecture
- **Widget:** Modify `Editor` in `editor.py` to use `Gtk.Paned` instead of `Gtk.Stack` when in "split mode".
- **Performance (Flickering Mitigation):** **Debouncing.** Rendering will be delayed by ~300ms after the last keystroke to prevent excessive flickering and CPU usage.

### UX Behaviors
- **Layout:** Side-by-side (source on left, preview on right).
- **Toggle UI:** **Editor Toolbar Toggle.** A "Split" toggle button will be added to the editor header/toolbar next to "Read" and "Source".
- **Synchronization:** **Synchronized Scrolling.** Scrolling the source view will automatically scroll the preview (and vice versa) using percentage-based or line-based mapping.

## Technical Implementation Details
1. **AppState Changes:**
   - Replace `editor: EditorState` with `tabs: List[TabState]` and `active_tab_index: int`.
   - `TabState` will contain the file path, editor state (zoom, read_mode, split_mode), and is_dirty flag.
2. **Window Component:**
   - Integrate `Adw.TabView` and `Adw.TabBar`.
   - Update command routing to target either the active tab or a specific tab ID.
3. **Editor Component:**
   - Replace `Gtk.Stack` with a structure that can swap between `Stack` (for Read/Source) and `Gtk.Paned` (for Split), or simply always use a `Gtk.Paned` and hide/show children.
