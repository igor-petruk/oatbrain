# oatbrain Implementation Audit Report

This report compares the current state of the oatbrain codebase against the `PLAN.md` and `SPEC.md` documents to identify missing features and usability improvements.

## 1. Missing Features (MVP Scope)

Based on the `PLAN.md` and `SPEC.md` (excluding explicitly deferred items), the following features are not yet implemented or are incomplete:

*   **Filesystem Watcher (Phase 2 & Phase 5 & SPEC §22)**:
    *   There is no implementation of the `FileWatcher` port in `src/oatbrain/core/ports/`.
    *   There is no concrete adapter like `watchdog` or `GFileMonitor`.
    *   Auto-reload on external change and external conflict detection are missing.
    *   *Note*: This also affects the 5s autosave idle debounce (SPEC §10.3), which relies on the watcher to avoid reload loops.
*   **Privacy Mode / Read-Only Files (SPEC §21)**:
    *   No read-only detection (SPEC §21.1) or UI indication (lock icon, banner) (SPEC §21.2) seems fully wired beyond the initial UI placeholders.
    *   "Privacy mode" (`.oatbrain-private` marker) is not implemented. Private files are not excluded from fuzzy search (SPEC §21.6).
*   **Remote Clipboard (OSC 52) (SPEC §16.4)**:
    *   VTE terminal does not handle OSC 52 (remote clipboard escape sequences).
*   **Desktop Notifications (SPEC §16.10 / §23.2)**:
    *   The `Notifier` port and `libnotify` adapter are missing.
*   **OATBRAIN_CURRENT_FILE & OATBRAIN_SELECTION (SPEC §16.3)**:
    *   Only `OATBRAIN_VAULT` is injected into the terminal. Live-update IPC mechanism (sidecar file + socket) is not implemented.
*   **Terminal Keyboard Shortcuts (SPEC §16.9)**:
    *   `Ctrl+Shift+Y` (Send file path) and `Ctrl+Shift+U` (Send selection) are defined in commands (`SendToTerminal` in `ui.py`), but are not fully implemented.
*   **Packaging (Phase 11)**:
    *   Debian packaging (`debian/` directory) and GitHub Actions CI (`.github/workflows/ci.yml` exists, but might not be fully finalized for Debian building) are missing/incomplete.

## 2. Recommended Next Steps

Considering the vision of a local-first desktop app for a personal Markdown vault with an AI CLI peer, I recommend prioritizing the following features:

### Priority 1: Filesystem Watcher (SPEC §22)
*   **Why**: A local-first markdown vault *must* play well with external tools (like git, syncthing, or an AI CLI running in the terminal pane). Currently, if an AI modifies a file, the editor won't know. Implementing the `FileWatcher` port using `watchdog` is critical for data integrity and a seamless experience.

### Priority 2: Live-update IPC Mechanism for Terminal Context (SPEC §16.3)
*   **Why**: The core premise of the terminal pane is to keep an AI CLI reachable *alongside* the note. Passing `OATBRAIN_CURRENT_FILE` and `OATBRAIN_SELECTION` via a sidecar file or IPC allows the AI in the terminal to have instant context of what the user is looking at or selecting in the editor, significantly boosting productivity.

### Priority 3: Privacy Mode (SPEC §21)
*   **Why**: If users are keeping personal or sensitive information in their vaults, especially when using an AI CLI that might read the vault, having a robust way to exclude certain directories (`.oatbrain-private`) from being scanned or searched is a crucial usability and security feature.

### Priority 4: Debian Packaging (Phase 11)
*   **Why**: The primary distribution target is Debian testing (trixie). Setting up the `debian/` packaging metadata is required to fulfill the MVP release goal.

## 3. Discrepancies between PLAN and codebase

*   **Mermaid (Phase 12)**: The plan lists Mermaid support as a separate phase, but partial implementation (fetching, caching, UI notifications, modal) already exists in `src/oatbrain/ui/preview.py` and `window.py`.
