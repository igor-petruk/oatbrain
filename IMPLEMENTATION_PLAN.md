# Multi-Tab + Horizontal Split Groups — Implementation Plan (Finalized)

## Overview

Replace the single-`Editor` widget with a **tab + split-group** layout. Each tab
is an independent `Editor` in either **editor** or **preview** mode. Tabs live inside
**groups** arranged horizontally with resizable dividers. All decisions below are
locked based on user review.

---

## Locked Decisions

| # | Question | Answer |
|---|---|---|
| Q1 | Split button | **Removed.** Tab toggle: Editor | Preview only. Side-by-side = two groups. |
| Q2 | Close tab | **Remove tab entirely from its group.** |
| Q2b | Open file | **Always open in the currently focused tab.** |
| Q3a | New tab | **Duplicates the focused tab** (same file + mode); user navigates from there. |
| Q3b | Tab title | **VSCode-style minimal disambiguating path** (e.g. `file.md  ../Notes`). Disambiguating folder segment rendered in a muted color. |
| Q3c | Dirty marker | **Different text color** on the tab title (no bullet/asterisk). |
| Q4 | Create group | **Split-Right button** in group header + **keyboard shortcut** + **command-palette entry**. No drag-and-drop. |
| Q5 | Group deletion | Empty non-last group **auto-deleted**. Last group always keeps at least one tab (blank). |
| Q6 | Divider persistence | **Fraction of total editor-area width.** |
| Q7 | Command routing | **Last-focused tab** (editor *or* preview WebView) receives all targeted commands. Pre-palette focus is remembered. |
| Q8 | StatusBar stats | **Re-queries focused tab on every focus-change** (Option B). |
| Q9 | Rename routing | Each `Editor` handles its own rename internally; emits `TabPathChanged` event for persistence. |
| Q10 | Stale cleanup | Empty groups after cleanup are **deleted**. Final fallback: one group, one blank tab. |
| Q11 | Blank tab design | Distinct centered layout with keyboard-shortcut hints (like current placeholder but richer). |
| Q12 | Zen mode | Hides tree + terminal only. **All groups remain visible.** |

---

## Data Model Changes

### `core/state.py`

```python
@dataclass(frozen=True)
class TabState:
    tab_id: str                          # stable UUID, assigned at creation
    open_file: Optional[VaultPath] = None
    mode: str = "editor"                 # "editor" | "preview"
    zoom: float = 1.0
    preview_zoom: float = 1.0

@dataclass(frozen=True)
class GroupState:
    group_id: str                        # stable UUID, assigned at creation
    tabs: tuple[TabState, ...] = ()
    active_tab_index: int = 0

@dataclass(frozen=True)
class EditorAreaState:
    groups: tuple[GroupState, ...] = ()
    divider_fractions: tuple[float, ...] = ()  # len == len(groups) - 1
    focused_group_index: int = 0
```

`AppState.editor: EditorState` is **replaced** by `AppState.editor_area: EditorAreaState`.

`EditorState` and `split_mode` are **deleted**.

---

## Persistence Format (`adapters/state.py`)

```toml
[editor_area]
focused_group = 0
divider_fractions = [0.5]

[[editor_area.groups]]
group_id = "g1"
active_tab = 0

[[editor_area.groups.tabs]]
tab_id  = "t1"
open_file = "notes/foo.md"
mode = "editor"
zoom = 1.0
preview_zoom = 1.0

[[editor_area.groups]]
group_id = "g2"
active_tab = 0

[[editor_area.groups.tabs]]
tab_id  = "t2"
open_file = "notes/foo.md"
mode = "preview"
```

### Startup stale-file cleanup (in `load()`)

1. For each `TabState` where `open_file` exists:  
   check `(vault_root / str(open_file)).exists()`.  
   If missing → drop that `TabState`.
2. If a `GroupState` becomes empty → **delete the group**.
3. If all groups are deleted → insert one `GroupState` with one blank `TabState`.

---

## UI Architecture

```
AdwAppShell
 └─ main_paned (H)
     ├─ FileTree
     └─ right_paned (H)
         ├─ EditorArea        ← new  (ui/editor_area.py)
         │   (Gtk.Paned tree of GroupPane widgets)
         └─ Terminal
```

### `ui/editor_area.py` (new)

Responsibilities:
- Owns a list of `GroupPane` widgets joined by `Gtk.Paned(HORIZONTAL)` instances.
- Tracks `_focused_editor: Optional[Editor]` by subscribing to GTK
  `notify::has-focus` on every `Editor.view` and `Preview._wv`.
- Before a `Palette` dialog is shown, snapshot the focused editor; restore intent
  after palette close.
- Command handlers: `OpenFile`, `CloseFile`, `ToggleMode`, `RefreshFile`,
  `Zoom(editor/preview)` forward to `_focused_editor`.
- `new_group_right_of(group)` — inserts a new `GroupPane` with a duplicate tab.
- `update_from_state(editor_area_state)` — syncs all groups.
- Saves divider fractions to state on `Gtk.Paned::notify::position`.

### `ui/group_pane.py` (new)

Responsibilities:
- Wraps `Gtk.Notebook` with `scrollable=True`, `show_tabs=True`.
- Tab label widget: two `Gtk.Label` side-by-side—filename in normal color,
  disambiguating folder segment in muted alpha. Dirty state changes the filename
  label's CSS class (e.g. `tab-dirty` with a distinct color token).
- Header area: a "⊞ Split Right" icon button at the trailing edge of the tab bar
  (placed using `Gtk.Notebook.set_action_widget`).
- Signals wired to `EditorArea`:
  - `page-removed` → if last tab and non-last group → notify `EditorArea` to
    delete this group.
  - `page-removed` → if last tab and last group → insert blank tab instead.
  - `switch-page` → update `EditorArea._focused_editor`.

### `Editor` changes (ui/editor.py)

- Remove `_btn_split`, `_split_paned`, `ToggleSplit` wiring.
- Mode toggle: two-button group only (**Editor** \| **Preview**).
- `EditorState` → `TabState` as the state argument for `update_from_state`.
- Rename handling: instead of dispatching `UpdateOpenFilePath` globally, call an
  injected `on_path_changed: Callable[[VaultPath], None]` callback, which
  `GroupPane/EditorArea` connects to emit `TabPathChanged(tab_id, new_path)`.
- Focus signal: emit `on_focused: Callable[[Editor], None]` when `view` or `_wv`
  receives focus; `EditorArea` subscribes to set `_focused_editor`.

---

## Tab Title Algorithm (VSCode-style disambiguation)

Given a list of all open `TabState.open_file` paths across all groups:

1. For each path, the **base filename** is the proposed label.
2. If any two open tabs share the same filename:
   - Walk up one parent segment at a time until all labels are unique.
   - The disambiguating suffix (e.g. `../Notes`) is rendered in a separate
     `Gtk.Label` with CSS class `tab-path-hint` (muted alpha color).

This runs whenever a tab is added, removed, or its file changes.

---

## New Commands

### `core/commands/editor.py`

```python
@dataclass(frozen=True)
class NewTab:
    """Open a new tab (duplicate of focused) in the focused group."""

@dataclass(frozen=True)
class CloseTab:
    """Close the focused tab."""

@dataclass(frozen=True)
class SplitGroupRight:
    """Move the focused tab into a new group to the right."""
```

### `core/events/ui.py`

```python
@dataclass(frozen=True)
class TabPathChanged:
    """Emitted by an Editor when its file is renamed on disk."""
    tab_id: str
    new_path: VaultPath
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+T` | `NewTab` |
| `Ctrl+W` | `CloseTab` |
| `Ctrl+Tab` | Next tab in focused group |
| `Ctrl+Shift+Tab` | Previous tab in focused group |
| `Ctrl+\` | `SplitGroupRight` |
| `Ctrl+2` | Focus first group (as today) |

---

## What Is Removed

| Item | Fate |
|---|---|
| `EditorState` class | Deleted; replaced by `TabState` |
| `EditorState.split_mode` | Deleted |
| `ToggleSplit` command | Deleted |
| `Editor._btn_split` | Deleted |
| `Editor._split_paned` | Deleted |
| `AppState.editor: EditorState` | Replaced by `AppState.editor_area: EditorAreaState` |
| `window.py self.editor` | Replaced by `self.editor_area: EditorArea` |
| `_sync_editor_to_state` | Replaced by `EditorArea.update_from_state` |
| `_handle_open_file` in window | Replaced by forwarding to `EditorArea` |
| Global `UpdateOpenFilePath` dispatch in `Editor` | Replaced by `on_path_changed` callback |

---

## Files Changed

| File | Change |
|---|---|
| `core/state.py` | Add `TabState`, `GroupState`, `EditorAreaState`; remove `EditorState` |
| `core/commands/editor.py` | Add `NewTab`, `CloseTab`, `SplitGroupRight`; remove `ToggleSplit` |
| `core/commands/__init__.py` | Update exports |
| `core/events/ui.py` | Add `TabPathChanged` |
| `adapters/state.py` | Rewrite `save`/`load` for new layout; add stale cleanup |
| `ui/editor.py` | Remove split mode; add focus/path-changed callbacks; use `TabState` |
| `ui/editor_area.py` | **[NEW]** Multi-group coordinator |
| `ui/group_pane.py` | **[NEW]** `Gtk.Notebook` wrapper + tab label widget |
| `ui/window.py` | Replace `self.editor` with `self.editor_area`; update all command handlers |
| `ui/statusbar.py` | Subscribe to focus-change; re-query focused editor stats |
| `tests/gui/ui/test_editor_lifecycle.py` | Adapt to single-group single-tab `EditorArea` |

---

## Verification Plan

### Automated Tests
- `TabState` / `GroupState` / `EditorAreaState` serialise/deserialise round-trip.
- Stale-file cleanup: drops missing paths, deletes empty groups, inserts blank fallback.
- Tab title disambiguation algorithm (pure function, no GTK needed).
- Adapted `test_editor_lifecycle.py` for the new `EditorArea` wrapper.

### Manual Verification
1. Open two files side by side: two groups, one editor + one preview.
2. Rename a file on disk → the tab(s) having it update their path label.
3. Delete a file on disk → affected tab closes; others unaffected.
4. Kill + restart app → full layout (groups, tabs, dividers, modes) restored.
5. Delete the TOML state file → app boots with one group, one blank tab.
