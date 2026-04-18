# oatbrain — Specification

| Field        | Value                                    |
|--------------|------------------------------------------|
| Version      | 0.1 (pre-MVP)                            |
| Owner        | Igor Petruk                              |
| License      | Apache-2.0                               |
| Status       | Authoritative spec. Source of truth.     |
| Last updated | 2026-04-17                               |

This document is the implementation contract. When it conflicts with a reader's
intuition, the document wins. When the spec is silent on a decision, prefer the
simplest implementation that keeps the testability and architecture rules in
§23 and §28 intact.

Key word convention: **MUST**, **MUST NOT**, **SHOULD**, **MAY** follow RFC 2119.

---

## Table of Contents

0. [Vision](#0-vision)
1. [MVP Scope](#1-mvp-scope)
2. [Technical Stack](#2-technical-stack)
3. [Packaging & Distribution](#3-packaging--distribution)
4. [Project Layout](#4-project-layout)
5. [Launch & Vault Model](#5-launch--vault-model)
6. [Window & Layout](#6-window--layout)
7. [Panes](#7-panes)
8. [Header Bar](#8-header-bar)
9. [File Tree](#9-file-tree)
10. [Editor](#10-editor)
11. [Preview](#11-preview)
12. [Markdown Dialect](#12-markdown-dialect)
13. [Wikilinks & Vault Resolution](#13-wikilinks--vault-resolution)
14. [Transclusion](#14-transclusion)
15. [Mermaid](#15-mermaid)
16. [Terminal](#16-terminal)
17. [Fuzzy Search Palette](#17-fuzzy-search-palette)
18. [Keyboard Shortcuts](#18-keyboard-shortcuts)
19. [Typography](#19-typography)
20. [Themes & Styling](#20-themes--styling)
21. [Read-only Files & Privacy Mode](#21-read-only-files--privacy-mode)
22. [Filesystem Behavior](#22-filesystem-behavior)
23. [Architecture](#23-architecture)
24. [State Management](#24-state-management)
25. [Concurrency & Main Loop](#25-concurrency--main-loop)
26. [Configuration](#26-configuration)
27. [Persistent State](#27-persistent-state)
28. [Logging](#28-logging)
29. [Error Handling](#29-error-handling)
30. [Testing Strategy](#30-testing-strategy)
31. [Continuous Integration](#31-continuous-integration)
32. [Accessibility](#32-accessibility)
33. [Constants Cheatsheet](#33-constants-cheatsheet)
34. [Appendix A — Data Flow Diagram](#appendix-a--data-flow-diagram)
35. [Appendix B — Glossary](#appendix-b--glossary)

---

## 0. Vision

oatbrain is a single-window, local-first desktop app for a personal Markdown
vault. It presents three panes:

1. A **file tree** rooted at the vault directory.
2. An **editor / preview** pane that flips between source-markdown editing and a
   rendered read mode.
3. A **terminal** emulator — a first-class peer of the editor, intended to keep
   an AI CLI (e.g. `claude`, `codex`, `aider`) always reachable alongside the
   note being edited.

One vault per window. No tabs. No split editors. No browser. Linux-first; Unix-
portable by default.

Primary audience: public release. Primary platform: Debian testing (trixie).

---

## 1. MVP Scope

### 1.1 In MVP

- Launch: `oatbrain <vault-path>`, or `oatbrain` to reopen the last vault.
- File tree (collapse/expand, select-to-open, resize, hide/show).
- Editor on `.md` files with GtkSourceView syntax highlighting and vim mode.
- Read-mode preview in WebKitGTK.
- Edit↔read flip via two small buttons in the pane's top-right corner, or
  `Ctrl+E`.
- Wikilink rendering in preview (`[[Name]]`, `[[Name|Alias]]`,
  `[[Name#Heading]]`, `[[Name#^block-id]]`). Click to follow. Broken links
  rendered red.
- Transclusion (`![[Name]]`, `![[Name#Heading]]`, `![[image.png]]`) resolved
  server-side during render.
- Mermaid diagrams in preview (via cached `mermaid.js`, CDN-loaded on first
  render then cached on disk).
- Terminal pane with `$SHELL` (configurable) rooted at the vault.
- Filesystem watcher: reload externally-changed files automatically unless the
  buffer is dirty; warn otherwise.
- Save on blur and pane-leave; explicit `Ctrl+S` / `:w`.
- Header bar: hamburger · tree-toggle · new-note (left) ·
  filename · unsaved-dot · read-only-lock (centre) · terminal-toggle · theme
  switcher · window controls (right).
- Fuzzy filename finder (`Ctrl+P`). Command palette (`Ctrl+Shift+P`) as the same
  widget in a different prefix mode.
- Three built-in themes: Solarized Light, Monokai Dark, high-contrast dark.
  System light/dark preference picks between the first two.
- Zen mode (`Ctrl+Shift+Z`): collapses tree and terminal, widens editor margins
  for distraction-free writing. Toggle button in the header bar restores previous
  layout on exit. Zen mode is not persisted across sessions.
- Config in `$XDG_CONFIG_HOME/oatbrain/config.toml`. Session state persisted
  separately in `$XDG_STATE_HOME/oatbrain/state.toml`.

### 1.2 Deferred beyond MVP

- Outline pane (headings of current note).
- Backlinks pane and backlink indexing.
- Global Search Results pane and fuzzy content search (`Ctrl+Shift+F`).
- Click-to-toggle task checkboxes in preview.
- KaTeX math rendering.
- Theme hot-reload.
- VSCode-style breadcrumb path in the file tree.
- Graph view, daily notes, calendar, templates, tag browser.
- Plugin system.
- Presentation mode.
- Git / sync integration.
- Data export / import.
- Crash-recovery journal for unsaved buffers.
- Spellcheck.
- Word count / reading time.
- Which-key popup.
- Zettelkasten timestamp IDs.
- Auto-enable privacy mode on screen-share detection.
- Terminal scrollback search.
- Pane zoom / per-pane maximize.
- Ligature opt-out / per-language fonts.

### 1.3 Out of scope forever

- Multi-window UI.
- Tabs within a pane.
- Detachable panes.
- Multi-vault UI (one vault per process).
- Mobile companion.
- Multi-user / real-time collaboration.
- Hand-rolled parsers for complex languages — the app relies on libraries.
- Data encryption (user handles via filesystem / git-crypt / Syncthing).
- Telemetry.
- In-app auto-update (apt handles updates).
- Pixel-exact visual regression tests.

---

## 2. Technical Stack

### 2.1 Runtime

- **Python** ≥ 3.12 (Debian trixie default).
- **GUI**: GTK 4 via `python3-gi` introspection bindings.
- **Chrome**: libadwaita (`AdwApplicationWindow`, `AdwHeaderBar`, `AdwStyleManager`).
- **Editor widget**: GtkSourceView 5 (syntax highlighting, vim IM context).
- **Preview**: WebKitGTK 6.
- **Terminal**: VTE for GTK 4.
- **Markdown parser**: `markdown-it-py`.
- **Diagrams**: `mermaid.js`, loaded from CDN on first render, cached under
  `$XDG_CACHE_HOME/oatbrain/`.
- **Async model**: GLib main loop only. Off-main-thread work via
  `concurrent.futures.ThreadPoolExecutor`, results posted back with
  `GLib.idle_add`. The app MUST NOT depend on `asyncio` in its event loop.
  (Rationale: `asyncio`↔GLib bridges such as `gbulb` are not packaged for
  Debian; we have a pure-apt constraint.)
- **Config format**: TOML (stdlib `tomllib` for read; `tomli_w` or hand-emitted
  for write — read/write separated, see §26).

### 2.2 Runtime dependencies (Debian packages)

Exact package names MUST be confirmed at packaging time against `apt-cache`. The
authoritative list:

```
python3                (≥ 3.12)
python3-gi
gir1.2-gtk-4.0
gir1.2-adw-1
gir1.2-vte-3.91
gir1.2-webkit-6.0
gir1.2-gtksource-5
python3-markdown-it
python3-mdit-py-plugins
python3-yaml
python3-tomli-w
python3-watchdog         (for FileWatcher adapter — GLib-only fallback acceptable)
```

If a listed package turns out not to be in Debian testing, the app MAY NOT
silently ship without it. A broken-dependency error at packaging time is the
correct failure.

### 2.3 Development & test dependencies

```
python3-pytest
python3-pytest-cov
python3-hypothesis
python3-mypy
python3-ruff               (or any lint package available)
tach                       (architecture linter; MUST be run from a virtual
                            environment as it is not packaged for Debian. This
                            is the ONLY permitted exception for `pip` usage,
                            restricted to development/test only.)
python3-syrupy             (snapshot tests)
python3-pyfakefs           (fake FS for unit tests)
xvfb                       (headless display for widget tests + smoke test)
at-spi2-core               (accessibility bus for dogtail)
python3-dogtail            (GUI automation via AT-SPI, optional)
```

### 2.4 Packaging

- Native Debian package: `oatbrain_0.1.0-1_all.deb`.
- Built with `dh_python3` + `pybuild` (`debian/rules` boilerplate).
- All runtime dependencies declared as `python3-*` / `gir1.2-*` in
  `debian/control`.
- **No** `pip install` at runtime. **No** venv at runtime. **No** vendored
  wheels. (Exception: `tach` is permitted via `pip` in dev/CI environments
  only to enforce architecture boundaries).
- `.desktop` file installed under `/usr/share/applications/oatbrain.desktop`.
- Icon SVG installed under `/usr/share/icons/hicolor/scalable/apps/`.
- Binary entry point under `/usr/bin/oatbrain` (from `pyproject.toml`
  `[project.scripts]`).

---

## 3. Packaging & Distribution

- Target: `.deb` for Debian testing (trixie). The package MUST install cleanly
  on a fresh trixie system with no manual steps beyond `apt install`.
- Target architecture: `all` (pure Python + platform-agnostic resources).
- The source tree follows `src/` layout (see §4).
- A `Makefile` target `make deb` produces the package locally.
- No binary releases, no snap, no flatpak, no AppImage in v1.

---

## 4. Project Layout

```
oatbrain/
├── debian/                          # Debian packaging
├── docs/
│   └── architecture.md              # referenced by SPEC §23
├── pyproject.toml
├── Makefile
├── SPEC.md                          # this document
├── PLAN.md                          # implementation plan (written later)
├── tach.toml                        # architecture lint config
├── src/
│   └── oatbrain/
│       ├── __init__.py
│       ├── __main__.py              # CLI entry point
│       ├── app/
│       │   └── bootstrap.py         # composition root (DI wiring)
│       ├── core/                    # pure domain (MUST NOT import gi, gtk, webkit, vte)
│       │   ├── __init__.py
│       │   ├── ports/               # Protocol definitions
│       │   ├── markdown/            # parser + custom plugins
│       │   ├── wikilink/            # parsing + vault resolution
│       │   ├── search/              # palette matching + ranking
│       │   ├── keymap/              # chord resolution
│       │   ├── state/               # state slices + root AppState
│       │   ├── theme/               # token loading and CSS variable generation
│       │   ├── events.py            # event classes (typed)
│       │   └── errors.py
│       ├── adapters/                # all gi / gtk / filesystem / process code
│       │   ├── filestore/
│       │   ├── watcher/
│       │   ├── process/
│       │   ├── renderer/            # markdown-it-py wrapper
│       │   ├── config/
│       │   ├── state/
│       │   ├── clock.py
│       │   ├── random.py
│       │   └── env.py
│       ├── ui/                      # GTK widgets
│       │   ├── window.py            # AdwApplicationWindow
│       │   ├── headerbar.py
│       │   ├── tree.py
│       │   ├── editor.py            # GtkSourceView wrapper
│       │   ├── preview.py           # WebKitGTK wrapper
│       │   ├── terminal.py          # VTE wrapper
│       │   ├── palette.py           # fuzzy search overlay
│       │   └── css/
│       │       ├── default.gtk.css
│       │       └── default.preview.css
│       └── resources/
│           ├── themes/              # bundled TOML theme token files
│           ├── icons/
│           └── mermaid/             # cached mermaid.js (populated at runtime)
├── tests/
│   ├── unit/                        # core only; no display; no FS; fast
│   ├── integration/                 # real FS via tmp_path; no display
│   ├── gui/                         # GtkSourceView etc. under Xvfb
│   ├── smoke/                       # app launch via subprocess
│   ├── data/                        # fixture vaults
│   └── fakes/                       # in-memory FileStore, scripted ProcessLauncher, etc.
└── README.md
```

`core/` MUST NOT import from `adapters/` or `ui/`. `adapters/` MUST NOT import
from `ui/`. Both rules are enforced by `tach` (§23.4).

---

## 5. Launch & Vault Model

### 5.1 Command line

```
oatbrain [<vault-path>]
```

- `<vault-path>` explicit → open that vault; remember it as the last vault.
- No argument → reopen the last vault recorded in persistent state (§27).
- No argument AND no last vault recorded → show a libadwaita vault-picker
  dialog rooted at `$HOME`.
- `<vault-path>` does not exist → error exit with a human-readable message.
- `<vault-path>` exists but is not a directory → error exit.
- A second invocation while an instance is already open for the same vault
  MUST focus the existing window (single-instance via Unix socket at
  `$XDG_RUNTIME_DIR/oatbrain.<vault-hash>.sock`). A second invocation for a
  different vault MUST be rejected with a message — one vault per process.

### 5.2 Vault semantics

- A vault is a directory tree. The tree's root is authoritative.
- There is no vault-level metadata directory required for first use.
- Optional per-directory marker file `.oatbrain-private` switches §21 privacy
  behavior on for that subtree.

---

## 6. Window & Layout

### 6.1 Window

- `AdwApplicationWindow`. No custom titlebar beyond the libadwaita header bar.
- Single window. No multi-window, no always-on-top, no multi-monitor awareness.
- Fullscreen via `F11`.
- Window position and size are persisted (§27).

### 6.2 Layout

```
┌──────────────────── AdwHeaderBar ─────────────────────┐
├──────┬──────────────────────────┬─────────────────────┤
│      │                          │                     │
│ Tree │   Editor / Preview       │     Terminal        │
│      │                          │                     │
├──────┴──────────────────────────┴─────────────────────┤
│                    Status Bar                         │
└───────────────────────────────────────────────────────┘
```

- Fixed layout. No drag-to-reorder. No detach. No splits inside panes.
- Default proportions: Tree 15% · Editor/Preview remainder · Terminal 30%.
- Tree and Terminal may be resized by dragging the splitter. Editor/Preview
  always takes what remains.
- Tree and Terminal may be hidden (§7.3). Editor/Preview, header, and status
  bar are always visible.

### 6.3 Status bar

Persistent single-line footer. Displays, in order:
- Current file's vault-relative path.
- Unsaved indicator (a dot) when the editor is dirty.
- Read-only lock icon when the current file is read-only (§21).
- Word count for the current file.
- Active vim mode label (e.g. `NORMAL`, `INSERT`, `VISUAL`) when editor has focus.
- Current theme name.

### 6.4 Minimum window size

No hard pixel minimum. When the window becomes narrow enough that Tree +
Editor + Terminal cannot coexist, the user-controlled visibility governs:
panes stay at their saved widths; Editor/Preview may scroll horizontally.
Auto-collapse on narrow window is **out of scope** for MVP.

### 6.5 Named layouts

Out of scope for MVP. Deferred.

---

## 7. Panes

### 7.1 Inventory (MVP)

| Pane          | First-class? | Focusable? | Hideable? | Multi-instance? |
|---------------|:---:|:---:|:---:|:---:|
| File Tree     | yes | yes | yes | no |
| Editor/Preview| yes | yes | no  | no |
| Terminal      | yes | yes | yes | no |
| Palette overlay | no  | yes (when open) | n/a | no |

Outline, Backlinks, Global Search Results, Tag browser, Graph — deferred (§1.2).

### 7.2 Pane linking (hardcoded)

- Selecting a file in the Tree opens it in Editor/Preview in the same mode as
  before.
- Flipping between Edit and Read in the pane performs a best-effort scroll jump
  to the same vertical position. There is **no** continuous scroll sync.
- Clicking a wikilink in Preview opens the target in Editor/Preview, in the
  same pane, without opening a new view.
- Fuzzy-search and palette-selection open in Editor/Preview.

### 7.3 Hiding

- Tree toggled by header-bar button and `Ctrl+B`.
- Terminal toggled by header-bar button and `` Ctrl+` ``.
- Hidden panes retain their saved width and collapse state, and still receive
  background updates (file watcher events, etc.).
- Hide animation: snappy slide if free from GTK core; otherwise instant. Don't
  implement a custom animation.

### 7.4 Empty-pane placeholder

When Editor/Preview has no open file, show a short keyboard-shortcut hint
block (e.g., "`Ctrl+P` — find file · `Ctrl+N` — new note") centered in the
pane.

### 7.5 Zen Mode

A distraction-free writing mode toggled by `Ctrl+Shift+Z` or the zen button
in the header bar.

- **Entering Zen**: hides the file tree and terminal pane; expands the editor's
  left/right margins to ~80 px and hides line numbers, centering prose in a
  comfortable column.
- **Exiting Zen**: restores tree and terminal to their pre-zen visibility; resets
  margins and line-number display.
- Pre-zen layout is held in memory only; Zen mode is never persisted across
  sessions (the session always opens in normal layout).
- The header bar zen toggle reflects current state and can activate or
  deactivate Zen mode independently of the keyboard shortcut.

### 7.5 Pane zoom / maximize

Deferred beyond MVP.

---

## 8. Header Bar

### 8.1 Layout (AdwHeaderBar)

- **Left**: hamburger (app menu) · toggle-tree · new-note.
- **Centre (title area)**: current filename · unsaved dot · read-only lock
  (conditional). Right edge of centre bar: zen-toggle · toggle-terminal.
- **Right**: window controls.

The **edit/read toggle** MUST NOT live in the header. Two small buttons float
in the top-right corner of the Editor/Preview pane body itself.

### 8.2 Icons only

All header buttons are icon-only. No text labels. Tooltips spelt out on hover.

### 8.3 Overflow

Default libadwaita overflow behavior when the header width is insufficient.
No custom overflow menu beyond that.

### 8.4 Right-click

No secondary actions on right-click. Right-clicking a header button is a
no-op.

### 8.5 App Menu (Hamburger)

The hamburger menu provides an "Open config file" entry that opens `config.toml` in the editor, and a theme switcher toggle (Light/Dark). There is no separate settings dialog in MVP.

---

## 9. File Tree

### 9.1 Rendering

- Hierarchical tree of the vault directory. Files and subdirectories only; no
  symlink traversal beyond the vault root.
- Collapsed folders render with a folder icon. Open folders show their children
  indented.
- Files with unsaved buffer state in Editor/Preview render with a dot on the
  row.
- Files matching §21 privacy rules are hidden (not greyed, not listed) while
  privacy mode is on.

### 9.2 Interactions

- Click: select.
- Double-click OR `Enter` when row focused: open in Editor/Preview.
- `Right-arrow` / `Left-arrow`: expand / collapse directory.
- Right-click: context menu — `New Note`, `New Folder`, `Rename`, `Delete`.
- `Delete` key: move-to-trash after confirmation (§22.4).
- Drag-and-drop: not supported in MVP.

### 9.3 Behavior under external change

- New file detected by watcher → appears in tree without collapsing parent
  folder or shifting scroll position.
- Deleted file detected by watcher → removed from tree. If it was open in the
  editor, see §22.2.
- The tree MUST NOT flicker, collapse, or lose its active row when the
  watcher delivers events.

### 9.4 Breadcrumbs

Deferred beyond MVP. Post-MVP plan: a VSCode-style clickable path segment
row at the top of the editor pane.

---

## 10. Editor

### 10.1 Widget

`GtkSourceView 5`. Buffer ownership: the `GtkSourceBuffer` is authoritative.
Tests that need buffer semantics run against a real GtkSourceView under
Xvfb. Other logic (parsing, wikilink rewrite, ranking, resolvers) is pure
functions that take text in and give text out and do not touch a buffer.

### 10.2 Modes

Two modes, mutually exclusive at any given moment:

| Mode   | Widget | Content             |
|--------|--------|---------------------|
| Source | GtkSourceView | raw markdown, syntax highlighted |
| Read   | WebKitGTK     | rendered HTML (read-only caret) |

There is no split mode. There is no live-preview / typewriter mode.

- Default mode on open: the mode the pane was last in for the current session;
  at app launch, Source mode.
- Mode is not persisted per-file.
- Toggle via the two small buttons in the pane's top-right corner, or `Ctrl+E`.
- Flipping MUST attempt a best-effort scroll-to-same-place jump.

### 10.3 Save triggers

- Explicit save: `Ctrl+S` and `:w` (vim command-line) flush immediately.
- Implicit save:
  - On window blur.
  - When focus moves out of Editor/Preview (e.g., to Terminal or Tree).
- Save is atomic: write to a hidden temp file in the same directory, then
  `rename` into place (guarantees same-filesystem atomicity; temp name is
  dot-prefixed so the filesystem watcher can filter it trivially).

> **Future**: idle debounce (5 s after last keystroke) will be added once the
> filesystem watcher (§22) is in place to avoid re-triggering reload loops.

### 10.4 Vim mode

- Enabled by default via `GtkSourceVimIMContext`.
- Active only inside the editor buffer. Palette and other modal overlays use
  their own standard bindings (see §17, §18).
- `:w`, `:wq`, `:q`, `:q!` supported via GtkSourceView's vim context.
- `Ctrl+S` works in all vim modes and is equivalent to `:w`.
- Escape leaves insert mode.
- Vim mode may be disabled globally in config (`[editor] vim = false`).

### 10.5 Undo

- Per-file undo stack.
- Stack is **not** persisted across sessions.
- `Ctrl+Z` / `Ctrl+Shift+Z`. In vim normal mode, `u` / `Ctrl+R` also work.

### 10.6 Find/replace

- `Ctrl+F` opens in-editor find bar. Find only; no replace in MVP.
- `Esc` closes the bar.
- `Enter` / `Shift+Enter` cycle next/previous match.

### 10.7 Status indicators

The editor reports its state to the status bar via published events:
unsaved dot, word count, current vim mode.

### 10.8 Code-block execution

Out of scope forever. Runnable code blocks are not supported.

---

## 11. Preview

### 11.1 Widget

WebKitGTK 6 `WebView`. The view is read-only — the WebKit caret is hidden;
text selection is enabled for copy.

### 11.2 Rendering pipeline

```
markdown (str)
  │
  ▼
Renderer port      (core defines; markdown-it-py adapter implements)
  │
  ▼
HTML (str) + per-block metadata
  │
  ▼
WebKitGTK load_html(...) with a stable base URI for relative asset resolution
```

The Renderer:
- MUST be side-effect free and fully unit-testable without any display.
- MUST resolve transclusion (§14) by reading referenced files via the
  `FileStore` port; the port MUST be injected.
- MUST emit a stable HTML shape per input; snapshot tests (syrupy) protect
  regressions.
- SHOULD cache parsed tokens for the active file to keep mode-switching fast;
  invalidation on file content change is required.

### 11.3 CSS

Preview CSS is §20. The WebView MUST consume the generated CSS custom
properties so theme changes take effect on re-render.

### 11.4 Mermaid

See §15.

### 11.5 Scroll sync

None while both modes are open (they are not both open simultaneously).
Mode-switch jumps to the closest heading or line number — best effort only.

---

## 12. Markdown Dialect

oatbrain parses an extended CommonMark:

### 12.1 Frontmatter

- YAML only, fenced by `---` at the start of the file.
- TOML (`+++`) and JSON frontmatter are **not** supported.
- If frontmatter is present and parseable, the renderer MAY use known fields
  (title, tags, aliases) but never fails rendering on unknown fields.

### 12.2 Syntax extensions supported

| Feature | Syntax | Notes |
|---|---|---|
| GFM tables | pipe tables | autoalign on save; opt-out via config |
| Task lists | `- [ ]`, `- [x]`, `- [/]` | `- [/]` = in progress; click-to-toggle deferred |
| Strikethrough | `~~text~~` | |
| Highlight | `==text==` | |
| Subscript / superscript | `H~2~O`, `x^2^` | |
| Footnotes | `[^1]` + `[^1]: body` | |
| Definition lists | standard | |
| Callouts / admonitions | `> [!note] ... ` | |
| Auto-link | bare URLs | see §12.5 |
| Code block titles | ``` ```lang title="foo.py" ``` ``` | |
| Image sizing | wikilink-embed form only | see §12.3 |
| HTML passthrough | raw `<div>` etc. | allowed; the renderer does not sanitise |
| Smart typography | basic (`...` → `…`, `--` → `–`, `---` → `—`) | |
| Wikilinks | `[[Name]]` etc. | see §13 |
| Transclusion | `![[...]]` | see §14 |
| Mermaid | fenced code block with `mermaid` lang | see §15 |
| Block references | `^block-id` at end of line, referenced via `[[Name#^block-id]]` | |

Math rendering (`$inline$`, `$$block$$`) is **deferred**. Parser MAY recognise
the fences and render them as a neutral placeholder in MVP.

### 12.3 Image sizing

- Wikilink-embed form only: `![[image.png|300]]` or `![[image.png|300x200]]`.
- The number is CSS pixels. If two numbers are given, the second is the
  pixel height.
- Plain-markdown `![alt|300](...)` is **not** supported.

### 12.4 Paste behavior

- **Image from clipboard**: save next to the currently open note. Filename
  pattern: `pasted_<UTC-ISO-8601-compact>_<4-hex>.png`. Insert a wikilink
  embed (`![[<filename>]]`) at the cursor.
- **URL paste**: bare URL inserted as-is. No automatic link expansion.

### 12.5 Auto-linking of bare strings

- Bare URLs (`http://`, `https://`, `mailto:`) become links.
- User-configurable prefix list in `config.toml` maps prefixes to a base URL.
  Example:

  ```toml
  [markdown.autolink]
  "go/" = "http://go/"
  "b/"  = "http://b/"
  ```

  A bare word like `go/project-plan` in prose is rendered as a link to
  `http://go/project-plan`. Target URL **MUST** be `http://`, not `https://`,
  because the prefix is a host-relative shortcut and a full domain is unknown.

- Auto-linking does **not** apply inside code blocks or inside wikilinks.

---

## 13. Wikilinks & Vault Resolution

### 13.1 Syntax

| Form | Meaning |
|---|---|
| `[[Name]]` | link to note named `Name` |
| `[[Name\|Alias]]` | link to `Name`, render `Alias` as text |
| `[[Name#Heading]]` | link to heading inside `Name` |
| `[[Name#^block-id]]` | link to block reference inside `Name` |
| `[[../folder/Name]]` | relative path; see resolution rules |

### 13.2 Resolution

- **Name-only** (`[[Name]]`): scan the vault for a file whose basename (minus
  `.md`) equals `Name`. If there is exactly one match, it wins. If there are
  many, prefer the closest ancestor shared with the current file, then
  alphabetically first. If there is none, the link is broken.
- **Path-bearing** (`[[folder/Name]]` or `[[../x/Name]]`): resolve as vault-
  relative first. If it does not exist, try file-relative (relative to the
  directory of the linking note). Whichever hits first wins.
- Paths are matched case-sensitively on Linux.
- `.md` extension is implied and MAY be omitted.
- Unresolved links render in red (broken-link color token).

### 13.3 Click on a broken link

Opens a dialog: "Create note at `<resolved-path>`?" The resolved path uses the
same rules as §13.2 but for a new file; default location is next to the
linking note.

### 13.4 Rename propagation

When a note is renamed via the Tree (right-click → Rename) or `mv` inside the
vault:
- Every wikilink in every `.md` file in the vault is rewritten from the old
  name to the new name.
- Block references (`[[Name#^block-id]]`) are rewritten too.
- Transclusions (`![[Name]]`, `![[Name#...]]`) are rewritten too.
- Rewrites are atomic per file (temp-write + rename).

### 13.5 Tags

- `#tag` in prose is rendered as a tag chip. Clicking a tag in preview is a
  no-op in MVP (tag browser deferred).

---

## 14. Transclusion

- `![[Name]]` inlines the full content of the target note.
- `![[Name#Heading]]` inlines only the section under that heading (until the
  next heading of the same or higher level).
- `![[Name#^block-id]]` inlines only the referenced block.
- `![[image.png]]` inlines the image. Sizing via `|W` or `|WxH` (§12.3).
- Transclusion is resolved at render time by the Renderer via the `FileStore`
  port. Cycles MUST be detected; a cyclic transclusion renders as an inline
  error, not a crash.
- Depth limit: 6 levels. Beyond that, render an inline error.

---

## 15. Mermaid

### 15.1 Inclusion

- Fenced code blocks with `mermaid` language tag are rendered as diagrams.
- `mermaid.js` is fetched from CDN on first render and cached under
  `$XDG_CACHE_HOME/oatbrain/mermaid/<version>/mermaid.min.js`. Subsequent
  renders use the cached copy, fully offline.
- Rendering is done inside the WebKitGTK preview (WebKit runs the JS).

### 15.2 Diagram types

Whatever the bundled `mermaid.js` supports out of the box — no subset. If
mermaid emits an error, the error text is displayed inline where the diagram
would be.

### 15.3 Live preview

Mermaid is rendered only in read mode. There is no live-while-typing preview.

### 15.4 Theme

Use mermaid's built-in theme. Per-diagram override via frontmatter or code-
block params is deferred.

### 15.5 User actions

- Click-to-enlarge: opens a modal with a larger rendered SVG.
- Right-click → Save as SVG / PNG / PDF. Right-click → Copy as image.
- Implementation note: export uses mermaid's own SVG output; rasterization
  to PNG/PDF is via WebKit's print-to-file, not a separate library.

### 15.6 Other diagram dialects

PlantUML, D2, Graphviz — deferred beyond MVP.

---

## 16. Terminal

### 16.1 Widget

VTE for GTK 4. Single terminal. No tabs, no splits (users who want more can
run `tmux`).

### 16.2 Shell and initial command

- Default shell: `$SHELL`.
- Configurable per vault in `config.toml`:

  ```toml
  [terminal]
  shell = "/bin/bash"
  initial_command = ""           # e.g. "claude" to auto-launch an AI CLI
  cwd = "vault-root"             # or "current-note-dir" (later feature)
  scrollback_lines = 10000
  ```

- Initial CWD: vault root.

### 16.3 Environment

The app MUST inject `OATBRAIN_VAULT` into the terminal's environment at spawn:

| Variable         | Meaning                         |
|------------------|---------------------------------|
| `OATBRAIN_VAULT` | absolute path to the vault root |

> **Future**: `OATBRAIN_CURRENT_FILE` (path of the open file, updated on
> change) and `OATBRAIN_SELECTION` (current editor selection) will be added
> once a live-update IPC mechanism is in place. The planned approach is a
> sidecar file at `$XDG_RUNTIME_DIR/oatbrain.<pid>.env` plus a Unix-socket
> push; simpler shells can ignore the socket and poll the file.

### 16.4 Clipboard

- Copy: configurable — `ctrl-shift-c` or auto-copy on selection. Default:
  `ctrl-shift-c`.
- Paste: `ctrl-shift-v` and middle-click.
- **OSC 52** (remote-clipboard escape) is enabled. Remote programs over SSH
  (vim, tmux, claude) can write to the local clipboard via
  `ESC ]52;c;<base64>\a`.

### 16.5 Colors and fonts

- Font: same as editor (§19).
- Palette: VTE's 16 ANSI slots are set via `VteTerminal.set_colors` from the
  active theme's token map. Fallbacks: Solarized palette for Solarized Light,
  Monokai palette for Monokai Dark.
- True-color (24-bit): enabled if GTK+VTE supports it without further work.

### 16.6 Hyperlinks (OSC 8)

Clicking a hyperlink inside terminal output opens in the system browser via
`xdg-open`. The app does not interpret OSC 8 URLs beyond that.

### 16.7 Kill & close

- No kill confirmation. Closing the window kills the terminal process.
- Terminal does not persist across restarts. Users who want persistence use
  `tmux` or `dtach` themselves.

### 16.8 Readline

The app stays out of the terminal's way. VTE forwards keys to the shell; the
shell's readline / zle owns line editing. The app only intercepts the
configured bindings (§18), and those bindings are chosen to avoid common
readline and tmux conflicts.

### 16.9 Bi-directional context with editor

- **Send file path to terminal**: `Ctrl+Shift+Y` writes
  `$OATBRAIN_CURRENT_FILE` to the terminal's stdin as a literal path. This
  does not submit a newline; the user chooses how to use it.
- **Send selection to terminal**: `Ctrl+Shift+U` writes the current editor
  selection to the terminal's stdin, as a quoted single-shot heredoc.
- **AI writes a file in the vault**: the watcher (§22.1) detects the change;
  if the buffer is clean, it reloads. If the buffer is dirty, it warns.
- **AI reads the current editor buffer**: reads the file directly from disk.
  This works because a save fires on focus leaving the editor (§10.3), so
  moving focus to the terminal flushes.

### 16.10 Notifications

When a foreground terminal process exits, the app SHOULD emit a desktop
notification via `libnotify` if simple to implement. Not a hard requirement.

### 16.11 Binding arbitration

When a key combination is claimed by both the app and the terminal (e.g.
`Ctrl+B` = toggle tree; `Ctrl+B` = tmux prefix for a user inside tmux), the
app wins. Users inside tmux should rebind their tmux prefix if they want to
reach tmux from within oatbrain. The default app bindings (§18) are chosen to
minimise clashes.

---

## 17. Fuzzy Search Palette

### 17.1 Single widget, four modes

The palette is a modal overlay, centered, ~50% window width. One widget, prefix modes determine the source:

| First char of query | Mode | Source |
|---|---|---|
| (none) | files | fuzzy matching (FZF algorithm) |
| `#` | tags | tag list |
| `%` | full text | fuzzy search index |
| `>` | app commands | registered command list |
| `/` | AI commands | `config.toml` list or dynamic command |

Backspacing past the prefix reverts to files.

### 17.2 Invocation

- `Ctrl+P` opens in files mode.
- `Ctrl+Shift+P` opens in commands mode (`>` prepended automatically).
- `F1` opens in help mode.

### 17.3 Matching

- Algorithm: fuzzy subsequence match with smart case (FZF algorithm).
- AI commands (`/`): populated by `[palette.ai_commands]` in `config.toml` (list of static strings) or `[palette]` key `ai_commands_fetcher` (command to list commands).
- No regex mode in MVP.
- Paths in files mode match against the vault-relative path, not only basename.
- Result ranking: match-quality score. Recency, frequency, and backlink count — deferred.

### 17.4 Empty query

- Files mode: show recent files (MRU, last 10).
- Commands mode: show all registered commands.
- Help mode: show the current effective keybindings.

### 17.5 Keybindings in the palette

| Key | Action |
|---|---|
| `↑` / `↓`, `Ctrl+K` / `Ctrl+J`, `Ctrl+N` / `Ctrl+P` | move selection |
| `Enter` | open/run in the current pane |
| `Esc` | close |

No split / new-tab variants — the app has neither.

### 17.6 Open target

Always the current Editor/Preview pane. There are no alternate open targets.

### 17.7 History

The palette does not keep a per-session query history in MVP.

### 17.8 Privacy interaction

In privacy mode (§21), files in private subtrees are excluded from files-mode
results.

---

## 18. Keyboard Shortcuts

### 18.1 Philosophy

- Native OS conventions where there's a clear expectation (`Ctrl+S` saves;
  `Ctrl+F` finds).
- Vim-style inside the editor buffer (`:w`, `u`, `gg`, etc.).
- `Ctrl+S` **also** works inside vim insert and normal mode.
- All app-level bindings are remappable in `config.toml`.

### 18.2 Default bindings

| Key | Scope | Action |
|---|---|---|
| `Ctrl+N` | app | New note — creates `untitled-<n>.md` in vault root |
| `Ctrl+O` | app | Alias for `Ctrl+P` |
| `Ctrl+P` | app | Palette, files mode |
| `Ctrl+Shift+P` | app | Palette, commands mode |
| `Ctrl+S` | editor | Save |
| `Ctrl+F` | editor | Find in file |
| `Ctrl+Shift+F` | app | Find in vault — deferred |
| `Ctrl+E` | editor/preview | Toggle edit ↔ read |
| `Ctrl+,` | app | Open `config.toml` in editor |
| `Ctrl+B` | app | Toggle tree |
| `` Ctrl+` `` | app | Toggle terminal |
| `Ctrl+K V` | editor | Open preview of current file (chord) — see §18.3 |
| `Ctrl+1` | app | Focus tree |
| `Ctrl+2` | app | Focus editor/preview |
| `Ctrl+3` | app | Focus terminal |
| `Alt+Left` | app | History back |
| `Alt+Right` | app | History forward |
| `F11` | app | Toggle fullscreen |
| `F1`, `?` | app | Cheatsheet (palette in help mode) |
| `Ctrl+Tab` | app | Cycle focus: tree → editor → terminal → tree |
| `Escape` | editor | Leave insert mode (vim) |
| `Ctrl+Shift+Y` | app | Send current file path to terminal stdin |
| `Ctrl+Shift+U` | app | Send editor selection to terminal stdin |
| `Ctrl+Shift+Z` | app | Toggle Zen mode (§7.5) |

Focus targets above are `tree`, `editor/preview` (same slot, whichever mode),
`terminal`. There is no fourth focusable zone in steady state; the palette
takes focus only while open and returns it on close.

### 18.3 Conflict resolution

App bindings always take priority over terminal / shell bindings when the
focus is inside the relevant pane AND the binding is registered at the app
scope. Bindings at the editor scope lose to GtkSourceView's internal
handling only when GtkSourceView explicitly claims the keystroke (e.g. vim
commands in normal mode).

### 18.5 Leader key

`Space` in vim normal mode. Unused outside vim. Overridable in config.

### 18.6 Remapping

```toml
[keymap]
"Ctrl+E" = "editor.toggle_mode"
"Ctrl+Alt+P" = "palette.open_files"
```

Remapping MUST validate action names at load time and report unknown
actions via the logger, not silently drop.

### 18.7 Accessibility — keyboard-only operation

All MVP actions MUST be reachable via keyboard. Full accessibility audit
deferred to §32.

---

## 19. Typography

All values are defaults; each can be overridden in `config.toml`. Editor,
preview and terminal each remember their zoom level across restarts (§27).

| Context | Family | Size | Line height |
|---|---|---|---|
| Editor  | monospace (probe order: **Cousine** → JetBrains Mono → Fira Code → DejaVu Sans Mono → system `monospace`) | 13 pt | 1.3 |
| UI chrome | **Arimo** → libadwaita default (Cantarell / Adwaita Sans) | default | default |
| Preview body | **Arimo** → system sans | 14 pt | 1.45 |
| Preview code blocks | **Cousine** → same as editor | 13 pt | 1.3 |
| Terminal | **Cousine** → same as editor | 13 pt | 1.0 |

- Size range: 8 – 32 pt.
- Heading scale (preview): `h1=2em`, `h2=1.6em`, `h3=1.3em`, `h4=1.15em`,
  `h5=1.05em`, `h6=1em`.
- Paragraph spacing: `0.8em`.
- Max line width in preview: `72ch`.
- Ligatures: on, if free via the font. No custom shaping work.
- No font bundling. Fonts are system-provided.
- Per-language fonts: deferred.
- Editor proportional mode: no. Monospace only.
- Zoom: `Ctrl++` / `Ctrl+-` / `Ctrl+0` per pane, remembered.

---

## 20. Themes & Styling

### 20.1 Model

A theme is a small TOML file declaring a set of semantic tokens. Loading a
theme produces a CSS `:root` block that both `default.gtk.css` (app chrome)
and `default.preview.css` (WebKitGTK preview) consume via CSS custom
properties.

### 20.2 Tokens

Initial token set (non-exhaustive; add only when a default stylesheet uses
one):

```
--color-bg
--color-bg-alt
--color-fg
--color-fg-muted
--color-accent
--color-accent-muted
--color-border
--color-selection
--color-link
--color-link-broken        /* red for unresolved wikilinks */
--color-code-bg
--color-code-fg
--color-warning
--color-error
--font-ui
--font-mono
--font-sans
--radius
--spacing
--spacing-lg
```

Terminal palette slots (ANSI 16) are their own namespace:

```
--ansi-0 through --ansi-15
--ansi-bg, --ansi-fg, --ansi-cursor
```

VTE is set from `--ansi-*` via `VteTerminal.set_colors` at theme load.

### 20.3 Theme file format

```toml
name = "Solarized Light"
kind = "light"           # light | dark | high-contrast-dark

[tokens]
"color-bg" = "#fdf6e3"
"color-fg" = "#586e75"
"color-accent" = "#268bd2"
# ...

[ansi]
"0" = "#073642"
"1" = "#dc322f"
# ...
```

### 20.4 Shipped themes (MVP)

- Solarized Light (light).
- Monokai Dark (dark).
- High-contrast dark (accessibility).

User themes go in `$XDG_CONFIG_HOME/oatbrain/themes/`. The app lists bundled
themes + user themes in the theme switcher.

### 20.5 Light / dark pairing

The user assigns one "light theme" and one "dark theme" in
`config.toml`. The theme switcher button toggles between the pair. By
default, the active choice follows the system light/dark preference
(`AdwStyleManager.color_scheme`); the user may override per session.

### 20.6 Accent color

Follows the system accent (`AdwStyleManager.accent_color`) unless a theme
explicitly sets `--color-accent` to a fixed value.

### 20.7 Hot reload

Deferred beyond MVP. Theme changes take effect on theme switch only; not on
file modification.

### 20.8 Power-user override

Users MAY drop a `user.gtk.css` and/or `user.preview.css` into
`$XDG_CONFIG_HOME/oatbrain/`. These files are appended **after** the default
stylesheets at load time and can override any rule.

Caveat: GTK CSS is a subset of web CSS. `calc()`, advanced pseudo-classes,
transforms and animations work only in `user.preview.css`, not in
`user.gtk.css`. The SPEC is explicit so users' expectations are calibrated.

### 20.9 Scope

All panes — including header bar, tree, editor (via its theme scheme),
preview and terminal — consume the same token set.

---

## 21. Read-only Files & Privacy Mode

### 21.1 Read-only detection

- A file is read-only iff its filesystem bits disallow write for the running
  user (e.g., `chmod -w`).
- No app-level "lock" state.

### 21.2 UI indication

- Lock icon in the header-bar centre.
- Lock icon in the status bar.
- Editor shows a subtle banner overlay on the pane: "Read only — `<reason>`".

### 21.3 Attempting to edit

When the user types into a read-only file, a dialog offers:
- "Make writable" (runs `chmod u+w` on the file; no elevation).
- "Save as..." (opens a file-save dialog; keyboard-only via palette path).
- "Cancel".

### 21.4 Scope of read-only

Read-only blocks **typing / buffer edits**. Rename, move, delete, create and
fuzzy-search indexing remain available; the OS surfaces permission errors if
they actually fail.

### 21.5 Presenting (out of scope for MVP)

Global read-only / presentation mode deferred.

### 21.6 Privacy mode

A directory is private iff it contains a marker file named
`.oatbrain-private` (empty file; TOML-shaped reserved for future options).
The marker applies to the directory and all descendants. A subtree with
the marker may itself contain a child with the marker; re-declaration is
harmless.

With privacy mode **on**:
- Private files MUST be excluded from fuzzy-search results.
- Private files MUST be excluded from the indexer (once §1.2 indexing lands).
- Private files remain visible in the file tree. They open normally when
  explicitly clicked; this is intentional — privacy hides from scanning, not
  from targeted access.

Privacy mode is toggled:
- By a switch in the app-menu (hamburger).
- Remembered across restarts.
- Auto-enable on screen-share detection: deferred.

### 21.7 Terminal privacy

The terminal is a generic terminal. The app does not filter terminal
commands or file operations based on privacy state.

---

## 22. Filesystem Behavior

### 22.1 Watcher

- A `FileWatcher` port watches the entire vault for changes.
- Default adapter: `watchdog` if available; GLib `GFileMonitor` otherwise.
- Watcher events are typed and published into the event bus (§24.4):
  `FileCreated`, `FileDeleted`, `FileModified`, `FileRenamed`.

### 22.2 Conflicts

When a file on disk changes externally:

| Buffer state | Action |
|---|---|
| Not dirty, not open | Tree updates silently |
| Not dirty, open in editor | Auto-reload; scroll preserved |
| Dirty, open in editor | Modal warning: "`<path>` changed on disk. Keep my version / Reload disk version". No automatic merge. |

If a file is **deleted** externally while open with a dirty buffer, the same
dialog offers "Keep my version (re-create on save) / Discard". If the buffer
is clean, the pane falls back to the empty placeholder.

### 22.3 Rename / move

- Done through the Tree (right-click → Rename) or by external `mv`. Either way
  triggers the wikilink rewrite pass (§13.4).
- The pass runs synchronously for vaults up to ~1000 files and in the
  background thread pool otherwise. Progress is displayed in the status bar.

### 22.4 Delete

- Hard delete. A confirmation dialog is shown every time.
- No trash integration in MVP.

### 22.5 Drag-and-drop

Not supported in MVP.

### 22.6 Symlinks

The vault is walked without following symlinks outside the vault root.
Symlinks that stay inside the vault are followed once (no cycle chase).

### 22.7 Atomic writes

All writes from the app are atomic: write to `<file>.tmp` then rename.

### 22.8 External tools writing into the vault

AI CLIs and other external tools writing into the vault hit the normal
watcher path. No special trust channel, no integrity check, no locking.

---

## 23. Architecture

### 23.1 Style

Hexagonal (Ports & Adapters).

- `core/` defines **ports** (Python `Protocol` classes) and pure logic.
- `adapters/` and `ui/` implement the ports and talk to the outside world.
- `app/bootstrap.py` is the **composition root**: the single place where ports
  are bound to concrete adapters.

### 23.2 Port catalogue

| Port | Purpose | Primary adapter |
|---|---|---|
| `FileStore` | vault file I/O (read, write, list, stat, rename, delete) | local FS |
| `FileWatcher` | subscribe to external file events | watchdog / GFileMonitor |
| `ProcessLauncher` | spawn PTYs for the terminal | VTE |
| `Renderer` | markdown → HTML | markdown-it-py |
| `ConfigStore` | load `config.toml` (read-only from core's view) | tomllib |
| `SessionStateStore` | load/save `state.toml` | tomllib + tomli_w |
| `Clock` | `now()`, `monotonic()` | stdlib |
| `Random` | seeded RNG | stdlib |
| `Env` | environment vars, XDG dirs | stdlib |
| `Notifier` | desktop notifications | libnotify |
| `Clipboard` | clipboard read/write | GTK clipboard |
| `Opener` | open a URI externally | xdg-open |

### 23.3 Port signatures (indicative)

Full signatures live in `src/oatbrain/core/ports/`. The spec-level shape:

```python
from typing import Protocol, Iterable, Callable, Optional
from dataclasses import dataclass
from pathlib import PurePosixPath

@dataclass(frozen=True)
class VaultPath:
    """Vault-relative, forward-slash normalised."""
    value: str

@dataclass(frozen=True)
class FileEntry:
    path: VaultPath
    is_dir: bool
    is_readonly: bool
    size: int
    mtime: float

class FileStore(Protocol):
    def exists(self, p: VaultPath) -> bool: ...
    def stat(self, p: VaultPath) -> FileEntry: ...
    def read_text(self, p: VaultPath) -> str: ...
    def write_text(self, p: VaultPath, content: str) -> None: ...
    def list_dir(self, p: VaultPath) -> list[FileEntry]: ...
    def rename(self, src: VaultPath, dst: VaultPath) -> None: ...
    def delete(self, p: VaultPath) -> None: ...
    def walk(self, root: VaultPath) -> Iterable[FileEntry]: ...

class FileWatcher(Protocol):
    def subscribe(self, cb: Callable[["FileEvent"], None]) -> "Unsubscribe": ...

class Clock(Protocol):
    def now(self) -> float: ...
    def monotonic(self) -> float: ...

class Renderer(Protocol):
    def render(self, markdown: str, from_path: VaultPath) -> "RenderedDoc": ...

class ProcessLauncher(Protocol):
    def spawn_pty(
        self,
        argv: list[str],
        env: dict[str, str],
        cwd: PurePosixPath,
    ) -> "PtyHandle": ...
```

### 23.4 Boundaries & enforcement

- `core/` MUST NOT import `gi`, `Gtk`, `Adw`, `WebKit`, `Vte`, `GtkSource` or
  any `oatbrain.adapters.*` or `oatbrain.ui.*`.
- `adapters/` MUST NOT import `oatbrain.ui.*`.
- `ui/` MAY import from `core/` and `adapters/`. It SHOULD keep widgets thin
  and delegate logic back to core via ports and commands.
- Enforcement: `tach.toml` with three layers (`core`, `adapters`, `ui`). CI
  runs `tach check` on every pull request.
- A small architecture test (`tests/unit/test_imports.py`) does a belt-and-
  braces grep-style check that `core/*.py` does not reference GTK names, in
  case `tach` is unavailable.

### 23.5 Command / Event bus

Core exposes:
- `dispatch(Command)` — returns a `Result[None, Error]`.
- `subscribe(EventType, callback)` — returns an `Unsubscribe` callable.

Commands are typed dataclasses. Events are typed dataclasses.
See §24.

### 23.6 Composition root

`src/oatbrain/app/bootstrap.py` constructs the full graph:

```python
def build_app(argv: list[str]) -> AdwApplication:
    env = StdlibEnv()
    clock = StdlibClock()
    config = TomlConfigStore(env).load()
    file_store = LocalFileStore(vault_root=resolve_vault(argv, env, config))
    watcher = WatchdogFileWatcher(file_store)
    renderer = MarkdownItRenderer(file_store)
    session = TomlSessionStateStore(env)
    process_launcher = VteProcessLauncher()
    app_state = load_or_default(session)
    bus = EventBus()
    commands = CommandRouter(
        state=app_state, bus=bus, file_store=file_store, renderer=renderer,
        watcher=watcher, clock=clock, config=config, session=session,
    )
    return AdwAppShell(commands=commands, bus=bus, state=app_state,
                      launcher=process_launcher)
```

Tests swap any port at this boundary.

### 23.7 Feature module shape

A "major feature" (palette, renderer, wikilinks, terminal, theme) lives as a
subpackage under `core/` with its own `ports/`, `services/` and `tests/`
siblings where warranted. Small features may be a single module; use
judgement.

### 23.8 Plugin system

Deferred. The plugin surface, when it exists, MUST target ports and command
names, not widgets.

---

## 24. State Management

### 24.1 Single source of truth

One `AppState` dataclass holds everything. Slices:

| Slice | Contents |
|---|---|
| `EditorState` | open file path, mode (source/read), dirty, cursor, vim mode |
| `FileTreeState` | expanded folders, selected row, scroll position, width |
| `SearchState` | palette open?, mode (files/commands/help), query, result set, selected index |
| `TerminalState` | visible?, width, spawned process handle |
| `AppUIState` | window size, fullscreen, theme id, light/dark preference, privacy-mode on/off |

### 24.2 Mutation

- V1: direct attribute assignment through the `CommandRouter`. Commands are
  pure functions `(AppState, Command) -> AppState` where feasible, or
  `(AppState, Command) -> (AppState, list[Event])` when events must be
  emitted.
- Setters and observers may be introduced later; do not pre-build them.
- YAGNI is load-bearing.

### 24.3 Undo / redo

- Per-file editor undo is owned by `GtkSourceBuffer`.
- App-level undo (global store snapshots, e.g. for rename propagation) — not
  in MVP.

### 24.4 Observability

Core emits **events** after committing a state transition. The UI adapter
subscribes and translates events into GObject signals on relevant widgets.
Background tasks publish events back onto the event bus via a thread-safe
queue drained by `GLib.idle_add`.

### 24.5 Derived state

- Tree visibility filters (including privacy) are computed as pure functions
  on slice inputs. No memoization layer in MVP; revisit if cold-startup
  profiling demands it.
- File tree rendering MUST NOT flicker or lose collapse/active state when
  recomputed (§9.3).

### 24.6 Transactions

Multi-step mutations (e.g. rename + wikilink rewrite) are a single command
that runs atomically within the dispatch. The renderer cache is invalidated
once, after the whole command commits.

### 24.7 Threading

State lives on the GTK main thread. Background work produces events that are
posted back onto the main thread via `GLib.idle_add`. Reducers / command
handlers run only on the main thread.

### 24.8 Persistence

Session state (not config) persists across restarts — see §27.

---

## 25. Concurrency & Main Loop

### 25.1 Single loop

GTK 4's main loop (via libadwaita) is the only event loop. Core code is
synchronous. The app MUST NOT introduce `asyncio`.

### 25.2 Background work

CPU-bound or blocking I/O is offloaded to a `concurrent.futures.ThreadPoolExecutor`
with a bounded pool (default 4 workers). Results post back via
`GLib.idle_add(callback, result)`.

### 25.3 Long-running tasks

Long tasks (vault walk, rename propagation):
- Produce progress events periodically (`Progress(current, total, label)`).
- Are cancellable via a `Cancellable` token passed in at submission.
- Display progress in the status bar.

### 25.4 File watcher

Events from `watchdog` arrive on the watchdog thread and are marshalled onto
the main thread via a queue + `GLib.idle_add`. Reducers handle them like any
other event.

### 25.5 IPC single-instance

Unix-socket listener on the main thread; accept loop registered as a
`Gio.SocketService`.

### 25.6 Exit

- Clean shutdown saves session state to disk before returning from the main
  loop.
- Signal handlers (SIGTERM, SIGINT) call the same shutdown path.

---

## 26. Configuration

### 26.1 Files

| File | Purpose | Read by | Written by |
|---|---|---|---|
| `$XDG_CONFIG_HOME/oatbrain/config.toml` | user-editable configuration | app | user |
| `$XDG_CONFIG_HOME/oatbrain/themes/*.toml` | user themes | app | user |
| `$XDG_CONFIG_HOME/oatbrain/user.gtk.css` | override CSS for chrome | app | user |
| `$XDG_CONFIG_HOME/oatbrain/user.preview.css` | override CSS for preview | app | user |

The app MUST NOT write to `config.toml`. The app presents no settings GUI
that edits the file — preserving user comments and formatting is a
requirement. An explicit "Open config file" command opens it in the editor.

### 26.2 Schema (indicative)

```toml
[general]
last_vault = "/home/user/Vault"

[editor]
vim = true
font_family = "JetBrains Mono"
font_size = 13
line_height = 1.3

[preview]
font_family = "system-ui"
font_size = 14
line_height = 1.45
max_width_ch = 72

[terminal]
shell = "/bin/bash"
initial_command = ""
scrollback_lines = 10000

[theme]
light = "solarized-light"
dark = "monokai-dark"
follow_system = true

[keymap]
# "Ctrl+E" = "editor.toggle_mode"    # overrides only; defaults are in code

[markdown]
ligatures = true

[markdown.autolink]
# "go/" = "http://go/"

[privacy]
enabled = false
```

### 26.3 Validation

- Parse with `tomllib`; on syntax error, refuse to start with a clear
  filename+line message.
- Unknown keys: warn via logger, do not fail.
- Type mismatch on known keys: refuse to start with the specific offending
  key.

---

## 27. Persistent State

### 27.1 File

`$XDG_STATE_HOME/oatbrain/state.toml`. App owns it end-to-end (read and
write). Comments and exact formatting are not preserved — the file is
rewritten on each save.

### 27.2 Content

```toml
[general]
last_vault = "/home/user/Vault"

[window]
width = 1600
height = 900
fullscreen = false

[panes]
tree_width = 240
tree_visible = true
tree_expanded = ["Projects", "Projects/oatbrain", "Daily"]
terminal_width = 480
terminal_visible = true

[editor]
open_file = "Projects/oatbrain/SPEC.md"
mode = "source"
scroll_line = 120
vim_enabled = true
zoom = 1.0

[preview]
zoom = 1.0

[terminal]
zoom = 1.0

[theme]
active_is_dark = true

[privacy]
enabled = false

[mru_files]
paths = [
  "Projects/oatbrain/SPEC.md",
  "Daily/2026-04-17.md",
  # ...
]
```

### 27.3 Save triggers

- On clean shutdown (including SIGTERM, SIGINT).
- No save on every keystroke. No autosave of state during normal use.

### 27.4 Session recovery

On startup, the app:
1. Reads `state.toml`.
2. Resolves `last_vault`. If missing, falls back to §5.1 vault-picker.
3. Restores window size, pane visibilities, widths, expanded folders.
4. Reopens `open_file` if it still exists; otherwise picks the most recent
   entry from `mru_files` that exists; otherwise falls back to the empty
   placeholder.
5. Restores scroll position (best effort — if the file size changed, clamp).

### 27.5 No crash journal

Unsaved buffers are not journalled. A crash loses them. Explicit save
(`Ctrl+S` / `:w`) and focus-leave saves (§10.3) are the safety net.

---

## 28. Logging

### 28.1 Library

Python stdlib `logging`. Every module does:

```python
import logging
log = logging.getLogger(__name__)
```

No port. No monkey patching.

### 28.2 Configuration

- Default level: `INFO` for `oatbrain.*`, `WARNING` for everything else.
- `--debug` CLI flag sets `oatbrain.*` to `DEBUG`.
- Output: stderr, with format
  `%(asctime)s %(levelname)-5s %(name)s | %(message)s`.
- No file logging in MVP. Users can redirect.

### 28.3 In tests

Tests use `pytest`'s built-in `caplog` fixture to assert on log output. The
app does **not** install any global log-capture infrastructure for tests.

### 28.4 Sensitive data

Logs MUST NOT include:
- Full file contents.
- Entire terminal output.
- Environment variable values.

They MAY include paths, file sizes, event types, counts, durations.

---

## 29. Error Handling

### 29.1 Core boundary

Core functions MAY raise domain exceptions (`oatbrain.core.errors.*`).
Adapters convert adapter-native exceptions to core exceptions at the
boundary.

### 29.2 UI surface

The UI adapter catches all core exceptions at dispatch time and either:
- Surfaces a human-readable message via a toast (libadwaita
  `AdwToastOverlay`), OR
- Surfaces a modal dialog if the user must decide (conflict, missing file).

The UI MUST NOT swallow exceptions silently.

### 29.3 Unexpected crashes

Top-level uncaught exceptions are logged at `ERROR` level and then re-raised.
GTK's default crash behavior applies (the app dies). No crash dialog in MVP.

### 29.4 Fault tolerance

- Missing referenced file (wikilink, transclusion): inline error in preview;
  nothing else breaks.
- Malformed mermaid: mermaid's own error text inline.
- Malformed markdown: best-effort; the parser is strict CommonMark and
  forgives most ambiguities.

---

## 30. Testing Strategy

### 30.1 Pyramid

| Layer | % of count | Speed | Scope |
|---|---|---|---|
| Unit (core) | ~70% | ms each | Pure functions. No FS, no display, no subprocess. |
| Integration (adapters) | ~20% | < 1 s each | Real FS under `tmp_path`. No display, no network. |
| GUI / E2E | ~10% | up to 10 s each | `xvfb-run`, real GtkSourceView / WebKitGTK when needed. |

Overall coverage floor: **50%**. `core/` is not formally gated but should
trend much higher — it is the easiest thing to cover.

### 30.2 Unit tests — what MUST be covered

- Wikilink parse and vault resolution (§13).
- Transclusion resolution with cycle and depth-limit detection (§14).
- Rename propagation rewrite (§13.4).
- Tag extraction.
- Fuzzy palette ranking (§17.3).
- Chord keybinding resolution (§18.3).
- Markdown → AST / outline / HTML (snapshot-tested via syrupy).
- Task parsing (`- [ ]` / `- [x]` / `- [/]`).
- Palette query → mode classifier.
- Config parsing + validation.
- Theme token resolution.
- Read-only detection.
- Session state round-trip (load → save → load).
- Auto-link expansion.
- Editor command layer (insert / delete / undo / redo) — where the
  implementation permits testing without a `GtkSourceBuffer`.

### 30.3 Fakes vs. mocks

- **Prefer fakes** over `unittest.mock`. An in-memory `FileStore`, a
  controllable `Clock`, a seeded `Random`, a scripted `ProcessLauncher`.
- Fakes live under `tests/fakes/`.
- `unittest.mock` is permitted only at the adapter boundary, when writing
  one-off regression tests.

### 30.4 Contract tests

For every port with more than one adapter (or more than one meaningful
implementation path), a single parametrised test suite runs the **same
behaviours** against the real adapter and the fake. Example: `FileStore`
contract tests run against `LocalFileStore` (using `tmp_path`) and against
`InMemoryFileStore`.

### 30.5 Property-based tests

`hypothesis` is used for:
- Markdown → HTML round-trip invariants.
- Wikilink parser on random inputs.

### 30.6 Snapshot tests

`syrupy` is used for:
- Rendered-HTML output for a fixture vault of notes.
- Rendered-mermaid placeholder HTML (not the diagram itself).
- Outline extraction.

Snapshot updates require an explicit `--snapshot-update` invocation — the CI
gate is strict.

### 30.7 GUI tests under Xvfb

- Keep widgets thin. Most logic is testable without a display.
- For flows that genuinely need widgets (GtkSourceBuffer behaviour, vim IM
  context, VTE key forwarding): use `dogtail` for AT-SPI-driven interaction
  under `xvfb-run`.
- No pixel-diff screenshot comparison.

### 30.8 Smoke test

`tests/smoke/test_launch.py`:

1. `xvfb-run python -m oatbrain <tmp_vault>` in a subprocess.
2. Wait for the main window to be mapped (AT-SPI `document.frame` probe, or
   `wmctrl -l` polling).
3. Assert the process stays alive for ≥ 2 s.
4. Send SIGTERM; assert clean exit within 10 s.
5. Assert session state was written.

This is the single "launched without crashing" signal in CI.

### 30.9 Determinism

- `Clock` and `Random` are always injected in unit tests — never imported
  directly.
- Iteration over dicts / sets that affects output is converted to sorted
  iteration where order matters.
- Tests MUST NOT rely on wall-clock time, real RNG, or network.

### 30.10 Fault injection

Deferred beyond MVP.

### 30.11 What is explicitly not tested

- Pixel-exact rendering.
- OS-level clipboard plumbing.
- Mermaid's own output correctness.
- Screenshot diffs.
- Full end-to-end coverage of native-GTK widget behaviour beyond smoke.

### 30.12 Wall-clock budget

- Unit suite: < 30 s.
- Integration suite: < 2 min.
- GUI + smoke: < 2 min.

A change that pushes a suite past its budget is a regression.

---

## 31. Continuous Integration

### 31.1 Provider

GitHub Actions.

### 31.2 Jobs

| Job | Depends on | Runs |
|---|---|---|
| `lint` | — | `ruff check`, `mypy --strict src/oatbrain`, `tach check` |
| `test-unit` | `lint` | `pytest tests/unit tests/integration` |
| `test-gui` | `lint` | `xvfb-run pytest tests/gui` |
| `test-smoke` | `test-gui` | `xvfb-run pytest tests/smoke` |
| `build-deb` | all above | `make deb`; upload artifact |

### 31.3 Matrix

Single job per OS for MVP: `ubuntu-24.04`. Debian-specific packaging tests
run inside a Debian testing container. No cross-version matrix until a
second supported distro exists.

### 31.4 Pre-commit hooks

```
ruff check
mypy --strict src/oatbrain
tach check
pytest -m fast
```

`-m fast` excludes GUI and smoke tests.

### 31.5 Branch gate

PRs cannot merge unless `lint`, `test-unit`, `test-gui`, and `test-smoke`
are all green. `build-deb` is required.

### 31.6 Mutation testing, performance benchmarks, flaky-test quarantine

Deferred.

---

## 32. Accessibility

- Every MVP action is reachable by keyboard (§18.7).
- High-contrast dark theme is shipped (§20.4) as the accessibility baseline.
- Screen-reader support and a full WCAG audit are deferred; the app MUST
  not actively break AT-SPI (libadwaita gives us this for free — don't
  override default widget roles).

---

## 33. Constants Cheatsheet

A single table for AI-assisted implementation. These are the canonical
numbers; do not invent others.

| Constant | Value | Source |
|---|---|---|
| Python minimum | 3.12 | §2.1 |
| Tree pane default width | 15% of window | §6.2 |
| Terminal pane default width | 30% of window | §6.2 |
| Autosave idle debounce | future (post §22) | §10.3 |
| Smoke-test alive window | 2 s | §30.8 |
| Smoke-test shutdown budget | 10 s | §30.8 |
| Transclusion depth limit | 6 | §14 |
| MRU files kept | 10 | §17.4, §27.2 |
| Editor font size | 13 pt | §19 |
| Preview font size | 14 pt | §19 |
| Terminal font size | 13 pt | §19 |
| Font size range | 8–32 pt | §19 |
| Editor line height | 1.3 | §19 |
| Preview line height | 1.45 | §19 |
| Terminal line height | 1.0 | §19 |
| Preview max line width | 72 ch | §19 |
| Paragraph spacing | 0.8 em | §19 |
| Heading ratio | 1.22 | §19 |
| Terminal scrollback default | 10 000 lines | §16.2 |
| Thread pool size | 4 workers | §25.2 |
| Coverage floor | 50% overall | §30.1 |
| Unit suite budget | 30 s | §30.12 |
| Integration suite budget | 2 min | §30.12 |

---

## Appendix A — Data Flow Diagram

```
                    ┌─────────────────────────────────────────────┐
                    │                   ui/                        │
                    │  window · headerbar · tree · editor · prev. │
                    │      terminal · palette                      │
                    │                  ▲                           │
                    │        GObject signals                       │
                    └──────────────────┼───────────────────────────┘
                                       │  commands dispatched down
                                       │  events flow up
                                       ▼
                    ┌─────────────────────────────────────────────┐
                    │                  core/                       │
                    │  CommandRouter · EventBus · AppState         │
                    │  markdown · wikilink · keymap · search       │
                    │  theme · state · errors · events             │
                    │                                              │
                    │  depends only on ports (Protocols)           │
                    └──────┬─────────────┬───────────┬─────┬──────┘
                           │             │           │     │
                 FileStore │   Renderer  │  Clock    │ Env │ Random
                           ▼             ▼           ▼     ▼
                    ┌─────────────────────────────────────────────┐
                    │               adapters/                      │
                    │  LocalFileStore · WatchdogFileWatcher        │
                    │  MarkdownItRenderer · TomlConfigStore        │
                    │  TomlSessionStateStore · VteProcessLauncher  │
                    │  StdlibClock · StdlibRandom · StdlibEnv      │
                    └──────────────────────┬───────────────────────┘
                                           │  real world
                                           ▼
                                 filesystem · subprocess
                                 libnotify · xdg-open
```

Rules:
- arrows flow top → down for dependencies, bottom → up for data.
- `core` imports only from `core.ports`.
- `adapters` import from `core.ports` and the outside world.
- `ui` imports from `core` (for types, events) and, via the composition
  root, gets a wired `CommandRouter`.

---

## Appendix B — Glossary

| Term | Meaning |
|---|---|
| Vault | A directory tree; the unit of oatbrain's world. One vault per process. |
| Note | A `.md` file inside the vault. |
| Wikilink | `[[Name]]`-style link. See §13. |
| Transclusion | `![[Name]]`-style embed. See §14. |
| Block reference | `^block-id` at line end; linked via `[[Note#^block-id]]`. |
| Pane | A first-class UI area. File tree, editor/preview, terminal. |
| Palette | The modal fuzzy finder / command runner. §17. |
| Privacy mode | App-wide flag that hides private subtrees from search and indexing. §21.6. |
| Token (theme) | A named CSS custom property (e.g. `--color-accent`) set by a theme file. §20. |
| Port | A `Protocol` in `core/ports/` that core depends on. §23. |
| Adapter | A concrete implementation of a port. §23. |
| Composition root | `app/bootstrap.py`. Wires ports to adapters. §23.6. |
| MRU | "Most recently used" file list. §17.4, §27.2. |
Protocol` in `core/ports/` that core depends on. §23. |
| Adapter | A concrete implementation of a port. §23. |
| Composition root | `app/bootstrap.py`. Wires ports to adapters. §23.6. |
| MRU | "Most recently used" file list. §17.4, §27.2. |
 §18.3. |
trl+K V`). §18.3. |
 §18.3. |
