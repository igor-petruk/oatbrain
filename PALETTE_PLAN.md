# Sub-Plan: Palette Implementation

This sub-plan breaks down Step 10.1 into verifiable increments, following the UI-first approach with mock data before dynamic integration.

## Phase 1: Palette UI Shell (Static Mock) [DONE]
Goal: Render the palette overlay and handle basic keyboard events.

### Step 1.1: Overlay Widget & Basic Keybindings [DONE]
### Step 1.2: Mode Switching & Mock Data [DONE]


---

## Phase 2: Core Integration & Search Engine [DONE]
Goal: Replace mocks with actual logic.

### Step 2.1: Fuzzy Matching (FZF) [DONE]
- **Task**: Integrate fzf library for file search.
- **Action**:
    - Use `python3-pyfzf` wrapper around `fzf` CLI. [DONE]
    - Hook the palette to the `FileStore` and `search` adapter. [DONE]
- **Verification**: Palette lists actual vault files and filters them correctly using FZF. [DONE]

### Step 2.2: Config-Driven AI Commands [DONE]
- **Task**: Implement AI command source.
- **Action**:
    - Add `palette` sections to `config.toml` parser. [DONE]
    - Implement `AICommandFetcher` (static list + dynamic command execution logic). [DONE]
- **Verification**: AI commands are populated in the palette based on `config.toml` or the result of the fetcher command. [DONE]


---

## Phase 3: Final Wiring & Terminal Interaction
Goal: End-to-end functionality.

### Step 3.1: Execution Logic
- **Task**: Wire action execution.
- **Action**:
    - Implement `Enter` key handlers:
        - Files: Open in editor.
        - AppCommands: Execute via `CommandRouter`.
        - AICommands: Paste string to terminal via `ui/terminal.py` (and press Enter).
- **Verification**: `Enter` on AI command pastes the string to terminal stdin.

### Step 3.2: Full Text & Tag Search (Bonus)
- **Task**: Connect remaining sources.
- **Action**:
    - Hook `%` mode to a simple fzf from the vault (deferred advanced indexer).
    - Hook `#` mode to a tag scanner via ripgrep from the root of the vault (update dependencies in README.md and in Github Actions).
- **Verification**: Tag/Text search returns relevant notes.
