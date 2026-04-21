# Simplification Plan: Robust & Lean Architecture

This plan aims to resolve the 100% CPU loop and simplify the codebase by reducing global state synchronization and eliminating complex UI logic.

## 1. Eliminate Ghost Subscriptions (Fix Memory Leaks)
**Issue:** `Editor` instances subscribe to the `EventBus` but never unsubscribe. When tabs are closed, "ghost" editors continue to process file events and trigger renders.
- **Action:** Add an `unsubscribe` mechanism to the `EventBus`.
- **Action:** Ensure `AdwAppShell` calls `unsubscribe` when closing a tab.

## 2. Localize Transient UI State
**Issue:** Minor updates like word counts and dirty flags are stored in the global `AppState`. This causes a `StateUpdated` broadcast on every keystroke, triggering redundant renders across the whole app.
- **Action:** Remove `word_count`, `is_dirty`, and `status_message` from `AppState` and `TabState`.
- **Action:** `Editor` manages its own `is_dirty` and `word_count`.
- **Action:** Use lightweight, non-state-persisting events (e.g., `WordCountChanged`, `StatusMessageRequested`) for communication with the `StatusBar`.

## 3. Simplify the Preview (The "Single Source of Truth" Preview)
**Issue:** Bidirectional scroll sync and multi-webview morphing are complex, CPU-intensive, and prone to feedback loops.
- **Action:** Remove the dual-WebView system and JavaScript "morphing" script. Use a single `WebKit.WebView`.
- **Action:** Drop bidirectional scroll sync. Support only **Source -> Preview** synchronization.
- **Action:** Replace complex scroll fraction calculations with a simple debounced update.

## 4. Manual Reload & Decoupled Watcher
**Issue:** The editor automatically reloads files on disk changes by comparing content. This is expensive and can conflict with autosave.
- **Action:** Remove the `FileModified` listener from the `Editor` component.
- **Action:** Add a "Reload File" command (bound to `Ctrl+R`) and a button in the UI.
- **Action:** The `FileWatcher` still updates the `FileTree`, but no longer forces editor reloads.

## 5. Simplified Tree Expansion
**Issue:** Syncing tree expansion through the global state on every click is signal-heavy.
- **Action:** Let `FileTree` manage its expansion state locally for the duration of the session.
- **Action:** Only persist the expansion state to the `StateStore` on application shutdown or specific "Save" events.

---

## Implementation Phases

### Phase A: Event Bus & Preview Cleanup
1. Implement `EventBus.unsubscribe`.
2. Refactor `Preview.py` to use a single WebView and remove morphing/bidirectional sync.
3. *Validation:* Run existing tests; verify that basic previewing still works.

### Phase B: State Decoupling
1. Remove `word_count` and `is_dirty` from `AppState`.
2. Update `Editor` to emit local events for word count and dirty state.
3. Update `StatusBar` to listen to these local events.
4. *Validation:* Verify that typing no longer triggers a global `StateUpdated` event.

### Phase C: Reload & Watcher Refactor
1. Remove auto-reload logic from `Editor`.
2. Implement `ReloadFile` command and UI trigger.
3. *Validation:* Verify that manual reload works and that CPU remains idle during file writes.

### Phase D: Tree Optimization
1. Decouple `FileTree` expansion signals from the global `AppState` update loop.
2. *Validation:* Verify that tree expansion is smooth and does not trigger global renders.
