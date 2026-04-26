# Multi-Tab + Split Groups — Task Checklist

## Phase 1: Data Model
- [x] `core/state.py` — add `TabState`, `GroupState`, `EditorAreaState`; remove `EditorState`

## Phase 2: Commands & Events
- [x] `core/commands/editor.py` — add `NewTab`, `CloseTab`, `SplitGroupRight`; remove `ToggleSplit`
- [x] `core/commands/__init__.py` — update exports (remove `CloseFile` global, keep for internal)
- [x] `core/events/ui.py` — add `TabPathChanged`

## Phase 3: Persistence
- [x] `adapters/state.py` — rewrite `save`/`load` for `EditorAreaState`; add stale-file cleanup on load

## Phase 4: Editor Widget Refactor
- [x] `ui/editor.py` — remove split-mode (split paned, btn_split, ToggleSplit); two-button toggle only; add `on_focused` / `on_path_changed` callbacks; accept `TabState` in `update_from_state`

## Phase 5: New UI Widgets
- [x] `ui/group_pane.py` — [NEW] `Gtk.Notebook` wrapper, tab label widget (VSCode-style disambig + dirty color), Split-Right action button
- [x] `ui/editor_area.py` — [NEW] multi-group coordinator, Gtk.Paned tree, focused-editor tracking, command forwarding, divider fraction save/restore

## Phase 6: Window Wiring
- [/] `ui/window.py` — replace `self.editor` with `self.editor_area`; update all command handlers; update shortcuts (Ctrl+T, Ctrl+W, Ctrl+Tab, Ctrl+Shift+Tab, Ctrl+\)
- [x] `ui/statusbar.py` — re-query focused editor on focus-change

## Phase 7: Tests
- [ ] Unit tests: `TabState`/`GroupState`/`EditorAreaState` serialise round-trip
- [ ] Unit tests: stale-file cleanup logic
- [ ] Unit tests: tab title disambiguation algorithm
- [ ] Adapt `tests/gui/ui/test_editor_lifecycle.py` for new `EditorArea`

## Phase 8: Validation
- [ ] `cargo check` equivalent: `make lint`
- [ ] `make test`
- [ ] `make test-gui`
