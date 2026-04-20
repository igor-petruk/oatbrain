# oatbrain Implementation Plan

This plan follows the Research -> Strategy -> Execution lifecycle. Each step is designed to be verifiable. We do not proceed to the next step until the current one is implemented and verified.

**Note**: This plan is kept in sync with GitHub Projects and Issues, which serve as the primary tracking tools for the project.

## Phase 1: Foundation & Project Structure [DONE]
Goal: Set up the repository structure, build system, and basic "Hello World" GTK application.

### Step 1.1: Project Skeleton [DONE]
### Step 1.2: Composition Root & CLI Entry [DONE]
### Step 1.3: Core Architecture & Linting [DONE]

---

## Phase 2: Core Domain - File & State Management [DONE]
Goal: Implement the "Brain" of oatbrain without any UI.

### Step 2.1: FileStore & Vault Resolution [DONE]
### Step 2.2: AppState & Command Bus [DONE]
### Step 2.3: Persistent State (state.toml) [DONE]

---

## Phase 3: Basic UI & Layout [DONE]
Goal: Build the main window layout with placeholder panes.

### Step 3.1: Main Window Layout [DONE]
### Step 3.2: Header Bar & Status Bar [DONE]
### Step 3.3: GUI Smoke Test [DONE]

---

## Phase 4: File Tree & Navigation [DONE]
Goal: Explore the vault.

### Step 4.1: File Tree Component [DONE]
### Step 4.2: File Selection & Opening [DONE]

---

## Phase 5: Markdown Editor (Source Mode)
Goal: Edit files with syntax highlighting and Vim mode.

### Step 5.1: GtkSourceView Integration [DONE]
- **Task**: Embed the editor widget.
- **Action**: 
    - Implement `ui/editor.py` wrapping `GtkSourceView`.
    - Enable Markdown highlighting.
- **Verification**: Opening a `.md` file shows highlighted source code.

### Step 5.2: SPEC Compliance & Polish (intermediate) [DONE]
- **Task**: Bring existing UI into 100% compliance with SPEC §6, §8, §9.
- **Action**:
    - **Layout (§6.2)**: Set exact splitter proportions (15% Tree, 30% Terminal remainder).
    - **Header Bar (§8)**: Add hamburger menu; add actual toggle logic for Tree/Terminal; ensure icon-only buttons with tooltips.
    - **Status Bar (§6.3)**: Implement Unsaved dot, Read-only lock icon, and Theme name; wire Word count (placeholder logic is ok for now, but widget must exist).
    - **Tree (§9.1)**: Add folder/file icons; add unsaved dot indicator.
    - **Shortcuts (§18.2)**: Implement `Ctrl+B` (Toggle Tree), `` Ctrl+` `` (Toggle Terminal), `Ctrl+1/2/3` (Focus switching).
- **Verification**: Visual audit against SPEC screenshots/descriptions; Keyboard shortcuts working.

### Step 5.2.1: Final SPEC Alignment (intermediate) [DONE]
- **Task**: Address remaining deviations from MVP spec (Persistent state format, Tree interactions).
- **Action**:
    - Migrate `YamlStateStore` to `TomlStateStore` using TOML format for state per §27.
    - Implement Tree interactions (single click select+open, right-click menu, permanent delete on Del).
- **Verification**: TOML is written instead of YAML; Single click opens file in tree; Delete prompts for permanent deletion.

### Step 5.3: Vim Mode & Autosave [DONE]
- **Task**: Add Vim IM context and save logic (§10.3, §10.4).
- **Action**:
    - Enable `GtkSourceVimIMContext` in `ui/editor.py`.
    - Implement the 5s idle autosave logic in a background thread or GLib timeout.
    - Status Bar: Show active Vim mode label (`NORMAL`, `INSERT`, etc.).
- **Verification**: Vim keys work; status bar updates mode; waiting 5s after typing saves the file to disk (verified by `stat` or watcher).

---

## Phase 6: Markdown Preview (Read Mode) [DONE]
Goal: Render Markdown to HTML.

### Step 6.1: Basic Renderer [DONE]
### Step 6.2: WebKitGTK Preview & Toggle [DONE]

---

## Phase 7: Terminal Integration
Goal: The built-in terminal.

### Step 7.1: VTE Integration [DONE]
- **Task**: Embed VTE terminal (§16.1).
- **Action**:
    - Implement `ui/terminal.py` wrapping `Vte.Terminal`.
    - Set CWD to vault root.
- **Verification**: Terminal pane opens and runs `$SHELL`.

### Step 7.2: Terminal Context (OATBRAIN_*) [DONE]
- **Task**: Inject environment variables (§16.3).
- **Action**:
    - Implement environment injection (VAULT, CURRENT_FILE, etc.).
    - Implement sidecar update logic.
- **Verification**: `echo $OATBRAIN_VAULT` in terminal works.

---

## Phase 8: Themes & Polish
Goal: Visual identity and final touches.

### Step 8.1: Theme Engine [DONE]
- **Task**: Implement TOML themes and CSS generation (§20).
- **Action**:
    - Implement `core/theme/` token resolution.
    - Load and apply theme CSS to both GTK and WebKit.
- **Verification**: Switching theme in header bar updates app styles.

---

## Phase 9: Advanced Markdown & Wikilinks [DONE]
Goal: Vault-aware rendering.
See [WIKI_PLAN.md](WIKI_PLAN.md) for the detailed execution steps.

### Step 9.1: Wikilink Resolution [DONE]
### Step 9.2: Transclusion [DONE]


---

## Phase 10: Fuzzy Palette & Commands [DONE]
Goal: Global navigation and command execution.

### Step 10.1: Palette UI & Search [DONE]
- **Task**: Implement the fuzzy search overlay with prefix-based commands (§17).
- **Action**:
    - Implement `ui/palette.py` as a centered overlay. [DONE]
    - Implement `Ctrl+P` to trigger the palette. [DONE]
    - Implement command prefix logic: [DONE]
        - (no prefix): File search (powered by FZF-like fuzzy matching) [DONE]
        - `#`: Tags search (via ripgrep) [DONE]
        - `%`: Full text search (via ripgrep) [DONE]
        - `>`: App commands (visibility filtered) [DONE]
        - `/`: AI commands (pasted to terminal). [DONE]
        - `!`: Shell commands (executed in terminal). [DONE]
- **Verification**: `Ctrl+P` opens palette; prefixes filter the search list; terminal interaction is fully wired. [DONE]

---

## Phase 11: Packaging & CI
Goal: Distribution-ready.

### Step 11.1: Debian Packaging
- **Task**: Create `debian/` packaging metadata (§3).
### Step 11.2: GitHub Actions
- **Task**: Finalize CI pipeline (§31).

---

## Phase 12: Mermaid Support [DONE]
Goal: Offline-first diagram rendering.

### Step 12.1: Asset Caching [DONE]
### Step 12.2: UI Notifications [DONE]
### Step 12.3: Renderer Integration [DONE]
- **Task**: Simplified Click-to-Toggle and Escape support.
- **Action**: 
    - Made Mermaid diagrams clickable to expand into modal.
    - Removed explicit 'Expand' button widget.
    - Added click-anywhere-to-collapse for the Mermaid modal.
    - Added global 'Escape' key listener in preview to close the modal.
- **Verification**: Clicking a diagram expands it; `Esc` or clicking the modal closes it.

---

## Phase 13: File Watcher & Tree Expansion [DONE]
Goal: Ensure the app reacts instantly to external file changes and persists the tree expansion state across sessions.

### Step 13.1: Expansion State Persistence & Lazy-Load Sync [DONE]
### Step 13.2: Watcher Core & Adapter [DONE]
### Step 13.3: Watcher UI Integration [DONE]

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

