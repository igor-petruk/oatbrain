# Multi-Tab & Split-Screen Questionnaire

Please review the following questions regarding the implementation details of the multi-tab and split-screen features.

## 1. File Opening Policy (Tabs)
When clicking a file in the tree, how should tabs behave?
- [ ] **Temporary Tabs (VS Code style):** Single click replaces current tab, double click pins it.
- [ ] **Always New Tab:** Every click opens a new tab, but doesn't duplicate if already open.
- [x] **Explicit Tabs:** Only open new tabs via context menu or middle click.

## 2. Split-Screen Scrolling
For split-screen Edit/Preview, how should scrolling be handled?
- [x] **Synchronized Scrolling:** Both panes scroll together based on percentage/line.
- [ ] **Independent Scrolling:** Each pane scrolls completely independently.

## 3. Same File Multiple Tabs
How should we handle a user trying to open the same file in multiple tabs?
- [ ] **Share Buffer (Complex, safe):** Share the `GtkSource.Buffer` so edits in one tab instantly appear in the other.
- [x] **Prevent Duplicates (Simpler):** Disallow opening the exact same file in more than one tab (focus the existing tab instead).

## 4. Split Toggle UI
Where should the UI control to enable Split-Screen mode live?
- [x] **Editor Toolbar Toggle:** Add a "Split" toggle next to the existing "Read" and "Source" buttons.
- [ ] **Command/Shortcut Only:** Use a keyboard shortcut and global command menu action without cluttering the UI.

## 5. Live Preview Performance (Flickering)
Live previewing on every keystroke can cause the WebKit view to flicker. How should we mitigate this?
- [x] **Debouncing Only:** Delay rendering by ~300ms after the user stops typing.
- [ ] **DOM Diffing (Complex):** Investigate injecting JS (e.g., `morphdom`) into the WebKit view to update only changed HTML nodes.
- [ ] **Manual Refresh:** Require a manual action/shortcut to refresh the preview when in split mode.

## 6. Single vs. Global Zoom
How should zooming behave with multiple tabs?
- [x] **Global Zoom:** Zooming in one tab zooms all tabs.
- [ ] **Per-Tab Zoom:** Each tab maintains its own independent zoom level.
