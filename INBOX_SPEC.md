# oatbrain — Inbox & AI Categorization Specification

## 1. Inbox Folder
- **Location**: The inbox is a directory named `Inbox` at the root of the vault.
- **Tree View**:
  - **MUST** be pinned at the top of the file tree, above all other directories.
  - **MUST** use a distinct icon (e.g., `mail-unread-symbolic`).
  - **SHOULD** indicate if it's not empty (e.g., subtle badge or color change).
- **Filesystem**: If the `Inbox` directory does not exist, it **SHOULD** be created on first use (e.g., when "New Note" is triggered).

## 2. New Note Workflow
- **Global Shortcut**: `Ctrl+N` **MUST** create a new empty note in the `Inbox` directory.
- **Contextual Creation**: Right-clicking a directory in the tree and selecting "New Note" **MUST** create the note in that specific directory.
- **Tab Behavior**: A new note opens in a new tab in the currently focused editor group.
- **Naming & Saving**:
  - The tab **SHOULD** show a temporary name derived from the first `# Heading` in the file.
  - If no heading exists, it defaults to "Untitled".
  - **Actual File Persistence**: The file is NOT created on disk until the first save (`Ctrl+S`).
  - Upon first save, a filename dialog **MUST** appear, defaulting to the slugified version of the first heading or "Untitled.md".

## 3. Processing / AI Categorization
- **Feature Name**: "Process" (configurable label).
- **Command Prefix**: Configurable in `app.toml`, defaults to `Process`.
- **Workflow**:
  - **Shortcut**: `Ctrl+Shift+Enter` (when editor is focused).
  - **UI Elements**:
    - "Process" button in the editor headerbar (prominent).
    - "Process" item in the tree view right-click menu for files.
  - **Action**:
    - Sends the command `{prefix} {relative_path}` to the integrated terminal.
    - Example: `Process ./Inbox/my-new-note.md`.
    - Behaves exactly like slash commands in the command palette: inserts text and triggers execution if the terminal is ready.

## 4. Configuration
- `app.toml` extensions:
  ```toml
  [inbox]
  folder = "Inbox"
  process_prefix = "Process"
  ```

## 5. UI/UX
- The "Process" button in the headerbar should be visually distinct to highlight its importance for research/ingestion workflows.
