# oatbrain Implementation Audit Report

This report identifies missing features and usability improvements in the oatbrain codebase.

## 1. Missing Features (MVP Scope)

Based on the `PLAN.md` and `SPEC.md` (excluding explicitly deferred items), the following features are not yet implemented or are incomplete:

*   **Privacy Mode / Read-Only Files (SPEC §21)**:
    *   No read-only detection (SPEC §21.1) or UI indication (lock icon, banner) (SPEC §21.2) seems fully wired beyond the initial UI placeholders.
    *   "Privacy mode" (`.oatbrain-private` marker) is not implemented. Private files are not excluded from fuzzy search (SPEC §21.6).
*   **Desktop Notifications (SPEC §16.10 / §23.2)**:
    *   The `Notifier` port and `libnotify` adapter are missing.
*   **Live-update IPC Mechanism for Terminal Context (SPEC §16.3)**:
    *   While `OATBRAIN_VAULT` is injected, the live-update mechanism (sidecar file + socket) for `OATBRAIN_CURRENT_FILE` and `OATBRAIN_SELECTION` is not implemented.
*   **Packaging (Phase 11)**:
    *   Debian packaging (`debian/` directory) is missing.

## 2. Recommended Next Steps

### Priority 1: Live-update IPC Mechanism for Terminal Context (SPEC §16.3)
*   **Why**: The core premise of the terminal pane is to keep an AI CLI reachable *alongside* the note. Passing `OATBRAIN_CURRENT_FILE` and `OATBRAIN_SELECTION` via a sidecar file or IPC allows the AI in the terminal to have instant context of what the user is looking at or selecting in the editor, significantly boosting productivity.

### Priority 2: Privacy Mode (SPEC §21)
*   **Why**: If users are keeping personal or sensitive information in their vaults, especially when using an AI CLI that might read the vault, having a robust way to exclude certain directories (`.oatbrain-private`) from being scanned or searched is a crucial usability and security feature.

### Priority 3: Debian Packaging (Phase 11)
*   **Why**: The primary distribution target is Debian testing (trixie). Setting up the `debian/` packaging metadata is required to fulfill the MVP release goal.
