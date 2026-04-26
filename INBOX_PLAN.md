# Implementation Plan - Inbox & AI Categorization

## Research
- [ ] Identify tree view implementation (`src/oatbrain/ui/tree.py`) to handle pinning and icons.
- [ ] Locate "New Note" command logic and `Ctrl+N` binding.
- [ ] Investigate tab title logic (`src/oatbrain/ui/editor.py` or similar) for heading-based titles.
- [ ] Check terminal command injection logic (slash commands).
- [ ] Check `app.toml` parsing for new config fields.

## Strategy
1.  **Core/Ports**: Add `Inbox` configuration to `Config` port and adapter.
2.  **UI/Tree**:
    - Modify `FileTree` to sort `Inbox` at the top.
    - Add custom icon for `Inbox`.
    - Implement non-empty indicator.
3.  **UI/Editor**:
    - Update `Ctrl+N` handler to target `Inbox`.
    - Implement "Heading to Filename" logic for unsaved files.
    - Add "Process" button to headerbar.
4.  **UI/Terminal**:
    - Create a helper to send "Process" command to terminal.
5.  **Integration**:
    - Connect headerbar button and tree context menu to "Process" action.

## Execution (Iterative)
### Step 1: Config & Constants
- [ ] Add `inbox` section to `src/oatbrain/adapters/config.py` and `src/oatbrain/core/ports/config.py`.

### Step 2: Tree View Enhancements
- [ ] Modify `src/oatbrain/ui/tree.py` to pin `Inbox`.
- [ ] Add icon and "not empty" badge/style.

### Step 3: New Note & Save Workflow
- [ ] Update `src/oatbrain/ui/window.py` or `editor.py` for `Ctrl+N` behavior.
- [ ] Implement heading-based tab titles for unsaved files.
- [ ] Implement save-as dialog for first-time save in Inbox.

### Step 4: "Process" Command
- [ ] Add "Process" button to `src/oatbrain/ui/headerbar.py`.
- [ ] Implement `Ctrl+Shift+Enter` shortcut.
- [ ] Implement terminal command injection.

### Step 5: Verification
- [ ] Unit tests for Inbox sorting logic.
- [ ] Unit tests for heading-to-filename extraction.
- [ ] Smoke test for "Process" command injection.
