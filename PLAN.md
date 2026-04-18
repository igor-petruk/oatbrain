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

## Phase 6: Markdown Preview (Read Mode)
Goal: Render Markdown to HTML.

### Step 6.1: Basic Renderer
- **Task**: Implement `markdown-it-py` adapter (§11.2).
- **Action**:
    - Implement `adapters/renderer/markdown_it.py`.
    - Support basic CommonMark and required extensions.
- **Verification**: Unit test: Markdown string -> HTML string.

### Step 6.2: WebKitGTK Preview & Toggle
- **Task**: Show rendered HTML and implement mode toggle (§10.2, §11).
- **Action**:
    - Implement `ui/preview.py` wrapping `WebKitWebView`.
    - Implement floating Edit/Read toggle buttons in the top-right of the editor pane (§8.1).
    - Implement `Ctrl+E` toggle logic with "best-effort scroll jump".
- **Verification**: Pressing `Ctrl+E` or clicking buttons flips between source and rendered view.

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

### Step 8.1: Theme Engine
- **Task**: Implement TOML themes and CSS generation (§20).
- **Action**:
    - Implement `core/theme/` token resolution.
    - Load and apply theme CSS to both GTK and WebKit.
- **Verification**: Switching theme in header bar updates app styles.

---

## Phase 9: Advanced Markdown & Wikilinks
Goal: Vault-aware rendering.

### Step 9.1: Wikilink Resolution
- **Task**: Parse and resolve `[[Name]]` (§13).
- **Action**:
    - Implement `core/wikilink/` logic to find targets in `FileStore`.
    - Update Renderer to use the resolver.
- **Verification**: Unit tests with various vault structures; Preview shows links.

### Step 9.2: Transclusion
- **Task**: Implement `![[Name]]` (§14).
- **Action**:
    - Update Renderer to resolve transclusions by reading via `FileStore`.
- **Verification**: Preview shows content of embedded notes.

---

## Phase 10: Fuzzy Palette & Commands
Goal: Global navigation and command execution.

### Step 10.1: Palette UI & Search
- **Task**: Implement the fuzzy search overlay (§17).
- **Action**:
    - Implement `ui/palette.py` as a centered overlay.
    - Implement `Ctrl+P` (files) and `Ctrl+Shift+P` (commands).
- **Verification**: `Ctrl+P` opens palette; typing filters vault files.

---

## Phase 11: Packaging & CI
Goal: Distribution-ready.

### Step 11.1: Debian Packaging
- **Task**: Create `debian/` packaging metadata (§3).
### Step 11.2: GitHub Actions
- **Task**: Finalize CI pipeline (§31).
