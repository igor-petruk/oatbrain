# oatbrain: Project Plan

## Phase 1: Foundation & Core Ports [DONE]
- [x] SPEC.md and AGENTS.md initialization.
- [x] Makefile with lint/test targets.
- [x] core/ports/ definitions (FileStore, Env, State, Watcher, Renderer).

## Phase 2: Adapters & Local IO [DONE]
- [x] LocalFileStore implementation + sandboxing.
- [x] Watcher implementation (GioFileWatcher).
- [x] Markdown-it renderer adapter.

## Phase 3: Event Bus & Command Router [DONE]
- [x] Synchronous EventBus for core decoupling.
- [x] CommandRouter for UI -> Core actions.

## Phase 4: Application State & Persistence [DONE]
- [x] AppState models (dataclasses).
- [x] TOML-based persistence for state.

## Phase 5: Main Loop & App Shell [DONE]
- [x] GObject/Adwaita main loop integration.
- [x] Multi-pane layout (Adw.ApplicationWindow).

## Phase 6: HeaderBar & Global Actions [DONE]
- [x] Toggle Tree/Terminal buttons.
- [x] Command Palette invocation.

## Phase 7: Status Bar & Context [DONE]
- [x] File path, Word count, Dirty indicator.
- [x] Read-only / Vim mode indicators.

## Phase 8: File Tree & Navigation [DONE]
- [x] Gtk.TreeView with vault hierarchy.
- [x] File selection -> OpenFile command.

## Phase 9: Markdown Editor (Edit Mode) [DONE]
- [x] GtkSourceView with Markdown highlighting.
- [x] Vim mode (GtkSourceVimIMContext).

## Phase 10: Markdown Preview (Read Mode) [DONE]
- [x] WebKitGTK integration.
- [x] Wikilink resolution + navigation.
- [x] Transclusion support.

## Phase 11: Fuzzy Search Palette [DONE]
- [x] Files mode (FZF algorithm).
- [x] Commands mode.

## Phase 12: Terminal Pane [DONE]
- [x] VTE-based terminal.
- [x] Editor-to-Terminal text pipe.

## Phase 13: Themes & Styling [DONE]
- [x] Token-based theme engine.
- [x] Solarized Light / Monokai Dark defaults.

---

## Phase 14: Zoom Support [DONE]
Goal: Implement per-component zoom levels with persistence.

### Step 14.1: Individual Component Zoom [DONE]
- **Task**: Implement Ctrl+/- and Ctrl+MouseScroll zooming (§19).
- **Action**:
    - Added `tree_zoom`, `terminal_zoom`, `editor_zoom`, `preview_zoom` to state.
    - Implemented `Zoom` command and global shortcuts in `window.py`.
    - Wired zooming for Tree (CSS), Editor (CSS + WebKit), and Terminal (Font size).
    - Updated `TomlStateStore` for persistence.
- **Verification**: `tests/unit/core/test_zoom.py` passed; zoom levels remembered across restarts.

---

## Phase 15: Terminal Improvements [IN PROGRESS]
Goal: Improve terminal reliability and usability.

### Step 15.1: Terminal Lifecycle & Restart Button [IN PROGRESS]
- **Task**: Implement shell auto-restart and a manual restart button (§16.12).
- **Action**:
    - Connect to `child-exited` signal and restart after delay.
    - Implement flood protection for fast-crashing shells.
    - Added `RestartTerminal` command and header bar button.
    - Implemented buffer clearing in `terminal.restart()` via `Vte.reset(True, True)`.
- **Verification**: Shell restarts automatically after `exit`; header button clears buffer and spawns new shell.

---

### Verification Scenarios (Tree Expansion & Watcher)
The following scenarios are verified by `tests/gui/ui/test_tree_expansion_harness.py`:

| Group | Category | Scenario | Result |
|-------|----------|----------|--------|
| **A** | **Pruning** | A1: Exact path removal; A2-A3: Recursive descendant pruning on collapse. | **PASS** |
| **B** | **Sync** | B1: External state expansion; B6: External state collapse reflection. | **PASS** |
| **C** | **Stability**| C1-C3: Collapse stability (no auto-re-expand loops); C5: Rapid toggle race conditions. | **PASS** |
| **D** | **Watcher** | D1-D2: File/Dir creation adds rows; D4: Deletion prunes state; D6: Rename remaps state. | **PASS** |
| **E** | **Load** | E1-E2: Correct expansion order and depth during app startup. | **PASS** |

---

## Phase 16: Syntax Highlighting [DONE]
Goal: Implement programming language highlighting in Markdown code blocks.
Details: See [PLAN_HIGHLIGHT.md](PLAN_HIGHLIGHT.md)
- [x] Update dependencies in `pyproject.toml`.
- [x] Integrate Pygments into `MarkdownItRenderer`.
- [x] Inject CSS styles into `Preview`.
- [x] Add unit tests for highlighting.

