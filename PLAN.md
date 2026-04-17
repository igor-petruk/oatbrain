# oatbrain Implementation Plan

This plan follows the Research -> Strategy -> Execution lifecycle. Each step is designed to be verifiable. We do not proceed to the next step until the current one is implemented and verified.

**Note**: This plan is kept in sync with GitHub Projects and Issues, which serve as the primary tracking tools for the project.

## Phase 1: Foundation & Project Structure
Goal: Set up the repository structure, build system, and basic "Hello World" GTK application.

### Step 1.1: Project Skeleton
- **Task**: Create the directory structure as specified in SPEC §4.
- **Action**: 
    - Initialize `pyproject.toml` with dependencies from SPEC §2.2.
    - Create `src/oatbrain/` with `__init__.py` and `__main__.py`.
    - Create `Makefile` with basic targets (`clean`, `lint`).
- **Verification**: `ls -R` matches SPEC §4; `python3 -m oatbrain` runs (even if it does nothing yet).

### Step 1.2: Composition Root & CLI Entry
- **Task**: Implement the basic CLI entry point and bootstrap logic.
- **Action**:
    - Implement `src/oatbrain/__main__.py` to handle `argv`.
    - Implement a minimal `src/oatbrain/app/bootstrap.py`.
    - Implement a "Hello World" `AdwApplication` in `src/oatbrain/ui/window.py`.
- **Verification**: `python3 -m oatbrain` opens an empty Libadwaita window.

### Step 1.3: Core Architecture & Linting
- **Task**: Set up `tach` and basic ports.
- **Action**:
    - Add `tach.toml` for architecture enforcement (SPEC §23.4).
    - Create `src/oatbrain/core/ports/` with initial `FileStore` and `Env` protocols.
    - Implement `tests/unit/test_imports.py` to verify core isolation.
- **Verification**: `tach check` passes; `pytest tests/unit/test_imports.py` passes.

---

## Phase 2: Core Domain - File & State Management
Goal: Implement the "Brain" of oatbrain without any UI.

### Step 2.1: FileStore & Vault Resolution
- **Task**: Implement `LocalFileStore` and vault discovery logic.
- **Action**:
    - Implement `adapters/filestore/local.py`.
    - Implement vault resolution logic in `core/` (SPEC §5.1).
- **Verification**: Unit tests for `LocalFileStore` using `pyfakefs`.

### Step 2.2: AppState & Command Bus
- **Task**: Implement the single source of truth and command routing.
- **Action**:
    - Define `AppState` dataclass in `core/state/`.
    - Implement a simple `EventBus` and `CommandRouter` in `core/`.
- **Verification**: Unit tests: dispatching a command updates `AppState` and emits an event.

### Step 2.3: Persistent State (state.toml)
- **Task**: Load and save session state.
- **Action**:
    - Implement `adapters/state/toml_store.py` (SPEC §27).
- **Verification**: Round-trip test: `AppState` -> `state.toml` -> `AppState` matches.

---

## Phase 3: Basic UI & Layout
Goal: Build the main window layout with placeholder panes.

### Step 3.1: Main Window Layout
- **Task**: Implement the three-pane layout (Tree, Editor, Terminal).
- **Action**:
    - Update `ui/window.py` with `AdwHeaderBar` and a multi-pane container (likely `Gtk.Paned`).
    - Use placeholders for Tree and Terminal.
- **Verification**: Window shows three distinct areas with correct default proportions (SPEC §6.2).

### Step 3.2: Header Bar & Status Bar
- **Task**: Implement the chrome elements.
- **Action**:
    - Implement `ui/headerbar.py` and `ui/statusbar.py`.
    - Wire them to `AppState` via the `EventBus`.
- **Verification**: Header bar shows icons; status bar shows dummy path/word count.

### Step 3.3: GUI Smoke Test
- **Task**: Verify application layout and widget hierarchy.
- **Action**:
    - Implement `tests/gui/test_smoke.py`.
    - Use `xvfb-run` to verify that the app launches and contains the expected nested panes.
- **Verification**: `make test-gui` passes.

---

## Phase 4: File Tree & Navigation
Goal: Explore the vault.

### Step 4.1: File Tree Component
- **Task**: Implement the hierarchical tree view.
- **Action**:
    - Implement `ui/tree.py` using GTK 4 `Gtk.TreeView` or `Gtk.ColumnView`.
    - Populated from `FileStore`.
- **Verification**: Tree displays files and folders of a test directory.

### Step 4.2: File Selection & Opening
- **Task**: Selecting a file updates the app state.
- **Action**:
    - Click/Enter in Tree dispatches `OpenFile` command.
    - Update `AppState.editor.open_file`.
- **Verification**: Selecting a file in the tree updates the path in the status bar.

---

## Phase 5: Markdown Editor (Source Mode)
Goal: Edit files with syntax highlighting and Vim mode.

### Step 5.1: GtkSourceView Integration
- **Task**: Embed the editor widget.
- **Action**:
    - Implement `ui/editor.py` wrapping `GtkSourceView`.
    - Enable Markdown highlighting.
- **Verification**: Opening a `.md` file shows highlighted source code.

### Step 5.2: Vim Mode & Autosave
- **Task**: Add Vim IM context and save logic.
- **Action**:
    - Enable `GtkSourceVimIMContext`.
    - Implement the 5s idle autosave (SPEC §10.3).
- **Verification**: Vim keys work; waiting 5s after typing saves the file to disk.

---

## Phase 6: Markdown Preview (Read Mode)
Goal: Render Markdown to HTML.

### Step 6.1: Basic Renderer
- **Task**: Implement `markdown-it-py` adapter.
- **Action**:
    - Implement `adapters/renderer/markdown_it.py`.
    - Support basic CommonMark.
- **Verification**: Unit test: Markdown string -> HTML string.

### Step 6.2: WebKitGTK Preview
- **Task**: Show rendered HTML in the UI.
- **Action**:
    - Implement `ui/preview.py` wrapping `WebKitWebView`.
    - Implement the Edit/Read toggle (Ctrl+E).
- **Verification**: Pressing Ctrl+E flips between source and a rendered view.

---

## Phase 7: Advanced Markdown & Wikilinks
Goal: Vault-aware rendering.

### Step 7.1: Wikilink Resolution
- **Task**: Parse and resolve `[[Name]]`.
- **Action**:
    - Implement `core/wikilink/` logic (SPEC §13).
- **Verification**: Unit tests with various vault structures and broken links.

### Step 7.2: Transclusion
- **Task**: Implement `![[Name]]`.
- **Action**:
    - Update Renderer to resolve transclusions (SPEC §14).
- **Verification**: Preview shows content of embedded notes.

---

## Phase 8: Terminal Integration
Goal: The built-in terminal.

### Step 8.1: VTE Integration
- **Task**: Embed VTE terminal.
- **Action**:
    - Implement `ui/terminal.py` wrapping `Vte.Terminal`.
    - Set CWD to vault root.
- **Verification**: Terminal pane opens and runs `$SHELL`.

### Step 8.2: Terminal Context (OATBRAIN_*)
- **Task**: Inject environment variables.
- **Action**:
    - Implement environment injection and sidecar update (SPEC §16.3).
- **Verification**: `echo $OATBRAIN_VAULT` in terminal works; updating file in editor updates `$OATBRAIN_CURRENT_FILE` in the sidecar.

---

## Phase 9: Fuzzy Palette & Commands
Goal: Global navigation and command execution.

### Step 9.1: Palette UI & Search
- **Task**: Implement the fuzzy search overlay.
- **Action**:
    - Implement `ui/palette.py`.
    - Implement `core/search/` fuzzy matching.
- **Verification**: `Ctrl+P` opens palette; typing filters vault files.

---

## Phase 10: Themes & Polish
Goal: Visual identity and final touches.

### Step 10.1: Theme Engine
- **Task**: Implement TOML themes and CSS generation.
- **Action**:
    - Implement `core/theme/` (SPEC §20).
    - Bundle Solarized and Monokai.
- **Verification**: Switching theme in header bar updates both app chrome and preview styles.

---

## Phase 11: Packaging & CI
Goal: Distribution-ready.

### Step 11.1: Debian Packaging
- **Task**: Create `debian/` directory and `Makefile` targets.
- **Action**:
    - Implement `make deb`.
- **Verification**: `dpkg -i oatbrain.deb` installs successfully on a clean system.

### Step 11.2: GitHub Actions
- **Task**: Set up CI pipeline.
- **Action**:
    - Create `.github/workflows/ci.yml`.
- **Verification**: PRs trigger linting, unit tests, and smoke tests.
