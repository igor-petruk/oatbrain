# File Watcher Implementation Plan — Phase 13.2/13.3

## Current State

Step 13.1 is done (committed). Three new untracked files exist as a skeleton for 13.2, plus a partially modified `window.py`. Several issues need fixing before wiring proceeds.

---

## Problem Inventory

**`core/events/watcher.py`** — has a duplicate `FileWatcher` Protocol at lines 38–48. Protocols belong in `core/ports/`, not `core/events/`. That block must be removed, leaving only the four dataclass event types plus `Unsubscribe`.

**`core/ports/watcher.py`** — imports `Unsubscribe` from events (fine) and defines `FileWatcher` (correct). Should also explicitly re-export `Unsubscribe` so adapters only need one import point.

**`adapters/watcher.py`** — `WatchdogFileWatcher.__init__` accepts `event_bus: EventBus` but never uses it. The watcher's job is to fire callbacks; bridging to the bus is the composition root's job. Remove that parameter.

**`ui/window.py`** — references `FileWatcher` as a type annotation but never imports it. Will cause a `NameError` at import time. Also the `watcher` parameter has no default, which breaks all existing tests that construct `AdwAppShell` without it.

**`app/bootstrap.py`** — never creates a `WatchdogFileWatcher` and never passes `watcher` to `AdwAppShell`. The app would crash on startup.

---

## Integration Architecture

The watcher fires watchdog callbacks on a background thread. `_publish_event` already marshals each event onto the GLib main loop via `GLib.idle_add`. In bootstrap, a single subscribe call bridges the watcher into the shared EventBus:

```
watchdog thread
  → watcher._publish_event(FileEvent)
    → GLib.idle_add(lambda: event_bus.publish(event))
      → tree._on_file_event(FileCreated | FileDeleted | FileRenamed)
      → editor._on_file_modified(FileModified)
      → window._handle_file_deleted(FileDeleted)  [prune tree_expanded]
```

No component needs to know about `watchdog`; they all see plain `FileEvent` objects on the EventBus.

---

## Step-by-Step Execution

### Step A — Fix `core/events/watcher.py`
Remove lines 38–48 (the duplicate `FileWatcher` Protocol). File should only export `Unsubscribe`, `FileEvent`, `FileCreated`, `FileDeleted`, `FileModified`, `FileRenamed`.

### Step B — Fix `adapters/watcher.py`
- Remove `EventBus` import and `event_bus` constructor parameter.
- `_publish_event` already calls `GLib.idle_add` — keep that; the lambda passed to it should call each subscriber callback.
- The `subscribe` / `unsubscribe` design is good — keep it.

### Step C — Fix `ui/window.py`
- Add `from oatbrain.core.ports.watcher import FileWatcher` to imports.
- Make `watcher` **optional** (`watcher: Optional[FileWatcher] = None`) so existing tests that build `AdwAppShell` without it don't break.
- In `on_activate`, after building the window, wire the watcher to the EventBus and start it:
  ```python
  if self._watcher:
      self._watcher.subscribe(lambda e: self._event_bus.publish(e))
      self._watcher.start(self._state.vault_root)
  ```
- In `_on_shutdown`, the existing `self._watcher.stop()` is correct; guard it with `if self._watcher`.
- Subscribe directly on EventBus to prune `tree_expanded`:
  ```python
  self._event_bus.subscribe(FileDeleted, self._on_file_deleted)
  self._event_bus.subscribe(FileRenamed, self._on_file_renamed)
  ```
  `_on_file_deleted` removes the path from `state.tree_expanded` and persists. `_on_file_renamed` swaps old → new path.

### Step D — Fix `app/bootstrap.py`
- Import `WatchdogFileWatcher`.
- Instantiate it: `watcher = WatchdogFileWatcher()`.
- Pass `watcher=watcher` to `AdwAppShell`.

### Step E — Update `ui/tree.py` — react to file events
Subscribe to `FileCreated`, `FileDeleted`, `FileRenamed` on the EventBus in `__init__`.

**`FileCreated(path)`**: Find the parent directory row in the store. If it's currently loaded (no dummy child), insert a new row in sorted order. If the parent is collapsed (has a dummy child), do nothing — it will pick up the new file on next expand.

**`FileDeleted(path)`**: Walk the store to find the row with matching path. Remove it. If the deleted item was a directory, its children are already gone on disk; remove them from the store too (GTK removes children automatically when a parent is removed via `store.remove()`).

**`FileRenamed(old_path, new_path)`**: Treat as delete old + insert new. Update `COL_PATH` values on all descendant rows if the renamed item is a directory (prefix replacement on `old_path → new_path`).

All three handlers run on the GLib main loop (guaranteed by the watcher's `GLib.idle_add`), so no extra threading is needed.

### Step F — Update `ui/editor.py` — auto-reload on external change
Subscribe to `FileModified` on the EventBus in `__init__`. Pass `vault_root: Path` to the editor constructor so it can resolve absolute paths for comparison.

```python
def _on_file_modified(self, event: FileModified) -> None:
    GLib.idle_add(self._reload_if_clean, event.path)

def _reload_if_clean(self, path: str) -> bool:
    if self._current_path is None:
        return GLib.SOURCE_REMOVE
    if Path(path) != self._vault_root / str(self._current_path):
        return GLib.SOURCE_REMOVE
    if self._is_dirty:
        return GLib.SOURCE_REMOVE  # user wins; no silent overwrite
    content = self._filestore.read_text(self._current_path)
    self._loading = True
    self.buffer.set_text(content)
    self._current_content = content
    self._loading = False
    return GLib.SOURCE_REMOVE
```

The `is_dirty` guard prevents silently discarding unsaved user edits.

### Step G — Fix Mermaid image width (`ui/preview.py`)
In `_wrap_html`, change the `.mermaid` CSS rule from:
```css
display: inline-block; margin: 0 auto; max-width: 100%;
```
to:
```css
display: block; width: 100%; box-sizing: border-box;
```
And change `.mermaid svg` to:
```css
width: 100%; height: auto;
```

### Step H — Tests
- **`tests/unit/adapters/test_watcher.py`**: Unit-test `WatchdogFileWatcher.subscribe/unsubscribe`. Mock the watchdog `Observer`. Verify `on_created`, `on_deleted`, `on_modified`, `on_moved` call the registered callback with the correct event type. Verify `unsubscribe` removes the callback.
- **`tests/unit/ui/test_editor_reload.py`**: Test `_reload_if_clean` — file matches + not dirty → buffer updated; file matches + dirty → buffer unchanged; file doesn't match → buffer unchanged.
- **`tests/unit/ui/test_tree_file_events.py`**: Test that `FileCreated`, `FileDeleted`, `FileRenamed` events update the tree store correctly (use a fake FileStore).
- **`tests/unit/ui/test_watcher_integration.py`**: Test the EventBus bridge — that a FileEvent published to the bus reaches a subscribed listener.

---

## Suggested Improvements

1. **Debounce rapid events**: Text editors and git often emit a burst of `FileModified` events. Add a per-path debounce (e.g., 200ms GLib timeout, cancel and restart on each event) before triggering a reload. Otherwise a `git pull` touching many files floods the main loop.

2. **Conflict banner for dirty files**: When `FileModified` arrives for the open file and `is_dirty` is true, show an `Adw.Banner` ("File changed on disk — save to keep your edits or discard") with Save/Discard actions. This is the correct UX per SPEC §22.

3. **`GFileMonitor` adapter**: Define a `GFileMonitorWatcher` adapter alongside the watchdog one using `GLib.File.monitor_directory()`. This eliminates the cross-thread bridge entirely since GLib already integrates with its own main loop, and avoids any Debian packaging concerns with `watchdog`.

---

## File Change Summary

| File | Action |
|---|---|
| `core/events/watcher.py` | Remove duplicate `FileWatcher` Protocol |
| `adapters/watcher.py` | Remove unused `EventBus` param |
| `core/ports/watcher.py` | No change needed |
| `ui/window.py` | Add import, make `watcher` optional, wire start/stop, subscribe for tree_expanded pruning |
| `app/bootstrap.py` | Create and inject `WatchdogFileWatcher` |
| `ui/tree.py` | Subscribe to `FileCreated`, `FileDeleted`, `FileRenamed`; targeted store updates |
| `ui/editor.py` | Subscribe to `FileModified`; reload if not dirty; accept `vault_root` param |
| `ui/preview.py` | Fix Mermaid CSS for full-width SVG |
| `tests/unit/adapters/test_watcher.py` | New: watcher callback tests |
| `tests/unit/ui/test_editor_reload.py` | New: dirty-guard reload tests |
| `tests/unit/ui/test_tree_file_events.py` | New: tree store update tests |
| `tests/unit/ui/test_watcher_integration.py` | New: EventBus bridge test |
