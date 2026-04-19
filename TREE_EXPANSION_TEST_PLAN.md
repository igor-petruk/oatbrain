# Tree Expansion Test Harness — Plan

## Problem Statement

The expansion-state subsystem spans three components that form a feedback loop:

```
User action (expand/collapse)
  ↓
tree.py: on_row_expanded / on_row_collapsed
  ↓ dispatches SetTreeExpanded
window.py: _handle_set_tree_expanded
  ↓ updates state, publishes StateUpdated
tree.py: _on_state_updated → _sync_with_state
  ↓ calls tree_view.expand_row
  ↓ which fires on_row_expanded again  ← feedback loop!
```

File watcher events add another path:
```
WatchdogFileWatcher → EventBus
  ↓ FileCreated / FileDeleted / FileRenamed
window.py: _on_file_deleted / _on_file_renamed → prunes/remaps tree_expanded → StateUpdated
tree.py: _on_file_created / _on_file_deleted / _on_file_renamed → mutates TreeStore
```

Race conditions exist between these two paths.

## Known Bugs

### Bug 1: Collapse does not prune descendants (ROOT CAUSE of auto-expand)

`_handle_set_tree_expanded` only removes the exact path:
```python
elif not command.is_expanded and command.path in expanded:
    expanded.remove(command.path)   # ← does NOT remove "projects/sub1", etc.
```

Result: after collapsing "projects", state still has `["projects/sub1", "projects/sub2"]`.
Next `_sync_with_state` tries to expand "projects/sub1" → must expand "projects" first →
fires `on_row_expanded("projects")` → re-adds "projects" → infinite feedback loop.

### Bug 2: _sync_with_state calls _expand_path but never collapses rows

When state transitions from expanded=["a"] to expanded=[], `_sync_with_state` detects
a change but only calls `_expand_path` for items in `new_expanded`. It never collapses
rows that were in `_expanded_state` but are not in `new_expanded`.

### Bug 3: GLib.idle_add without cancellation (FIXED — stale idle)

Already fixed with `_sync_idle_id` tracking. Included in harness for regression coverage.

## Test Harness Architecture

### Components

**`FakeStateManager`** — simulates `window.py` state management:
- Wires `SetTreeExpanded` command to the event bus
- Initially replicates current (buggy) behavior: only removes exact path on collapse
- Tests written against the CORRECT behavior will fail → expose bugs
- Fixed incrementally until all tests pass

**`FakeGLib`** — eliminates async complexity:
- `idle_add(fn, *args)` → calls `fn(*args)` synchronously, returns id
- `source_remove(id)` → marks id as cancelled, skips pending call
- Allows linear test execution without a main loop

**`FakeFilestore`** — controllable directory contents:
- Maps `VaultPath → list[FileEntry]` for `list_dir`
- Mutatable during tests to simulate filesystem changes

**`TreeHarness`** — wires the system and provides test helpers:
- Creates `FileTree` with patched GLib
- Creates `FakeStateManager` wired to same `EventBus`
- Provides `simulate_expand(rel_path)`, `simulate_collapse(rel_path)`
- Provides `expanded_state()`, `store_paths(parent=None)`, `row_is_dir(rel_path)`

### Signal Simulation Strategy

GTK signals (`row-expanded`, `row-collapsed`) require a realized widget. Instead:
- Call `tree.on_row_expanded(None, iter_, path)` / `tree.on_row_collapsed(...)` directly
- These are the public signal handlers — calling them directly is equivalent
- `tree_view.expand_row` / `collapse_row` calls inside `_sync_with_state` are patched
  to record calls and optionally fire `on_row_expanded` / `on_row_collapsed` back

### Sync Strategy

`GLib.idle_add` is patched to run synchronously in tests. This means:
- `_on_state_updated` → cancels previous idle → adds new idle → runs immediately
- `_on_file_created` etc. → idle added → runs immediately

## Test Scenarios

### Group A: State Manager — Collapse Pruning (tests current window.py behavior)

| # | Test | Asserts |
|---|------|---------|
| A1 | `test_collapse_removes_exact_path` | Collapsing "a" removes "a" from expanded |
| A2 | `test_collapse_prunes_direct_children` | **BUG**: Collapsing "a" also removes "a/b" |
| A3 | `test_collapse_prunes_deeply_nested` | Collapsing "a" removes "a/b/c/d" |
| A4 | `test_collapse_does_not_affect_sibling` | Collapsing "a" does not remove "b" |
| A5 | `test_expand_then_collapse_leaves_empty` | Full round-trip leaves expanded=[] |
| A6 | `test_expand_records_path` | Expanding "a" adds "a" to expanded |

### Group B: Tree Sync — _sync_with_state Logic

| # | Test | Asserts |
|---|------|---------|
| B1 | `test_sync_expands_paths_from_state` | StateUpdated(expanded=["a"]) expands "a" |
| B2 | `test_sync_noop_if_state_unchanged` | No tree_view.expand_row if expanded unchanged |
| B3 | `test_sync_cancels_stale_idle` | Second StateUpdated cancels first idle |
| B4 | `test_sync_does_not_reexpand_collapsed_row` | Collapse → StateUpdated(same) doesn't re-expand |
| B5 | `test_sync_with_children_in_state_no_loop` | **BUG**: expanded=["a/b"] without "a" doesn't loop |

### Group C: Full Feedback Loop — Collapse Stability

| # | Test | Asserts |
|---|------|---------|
| C1 | `test_collapse_dir_stays_collapsed` | Collapse "a" → state converges, "a" stays collapsed |
| C2 | `test_collapse_dir_with_expanded_children_stays_collapsed` | **BUG**: main regression |
| C3 | `test_collapse_deeply_nested_stays_collapsed` | Three levels deep |
| C4 | `test_multiple_dirs_collapse_one_other_stable` | Collapsing "a" doesn't affect "b" |
| C5 | `test_rapid_collapse_expand_collapse_final_is_collapsed` | Race condition |

### Group D: Watcher → Tree Sync

| # | Test | Asserts |
|---|------|---------|
| D1 | `test_file_created_adds_row` | FileCreated(file) → row appears in store |
| D2 | `test_dir_created_adds_row_with_dummy` | FileCreated(dir) → dir row + dummy child |
| D3 | `test_file_deleted_removes_row` | FileDeleted → row gone |
| D4 | `test_file_deleted_expanded_dir_prunes_state` | Delete expanded dir → removed from expanded |
| D5 | `test_file_renamed_updates_store` | FileRenamed → COL_NAME + COL_PATH updated |
| D6 | `test_file_renamed_updates_expanded_state` | Renaming expanded dir remaps paths |
| D7 | `test_file_created_in_collapsed_dir_not_added` | File inside collapsed (dummy) dir is ignored |
| D8 | `test_file_created_in_unloaded_root` | File created at root always added |

### Group E: Initial Load

| # | Test | Asserts |
|---|------|---------|
| E1 | `test_initial_state_expands_dirs` | AppState(expanded=["a"]) → "a" expanded on load |
| E2 | `test_initial_state_nested_expansion` | Nested dirs expand in correct order |
| E3 | `test_initial_state_missing_dir_is_noop` | Expanded path that doesn't exist is silently ignored |

## Implementation Plan

### Step 1: Create test harness infrastructure

File: `tests/unit/ui/test_tree_expansion_harness.py`

- `FakeGLib` class with synchronous `idle_add` / `source_remove`
- `FakeStateManager` mirroring current (buggy) `window.py` behavior
- `FakeFilestore` with mutable directory map
- `TreeHarness` class
- Helper assertions

### Step 2: Implement all test scenarios

Write all tests. Run them. Document which fail (expected).

### Step 3: Fix bugs one by one

For each failing group:

1. **Bug A2-A3, C2-C3** — Fix `_handle_set_tree_expanded` in `window.py`:
   - When `is_expanded=False`, also remove all paths with `path + "/"` prefix

2. **Bug B5, C1** — Fix `_sync_with_state` in `tree.py`:
   - When `new_expanded != _expanded_state`, also collapse rows that were removed
   - OR ensure the state manager prunes correctly so the tree never gets orphan children

3. **Any remaining** — Fix as discovered

## Files to Modify

- `tests/unit/ui/test_tree_expansion_harness.py` — new, comprehensive test harness
- `src/oatbrain/ui/window.py` — `_handle_set_tree_expanded`: prune descendants
- `src/oatbrain/ui/tree.py` — `_sync_with_state`: potentially collapse stale rows
