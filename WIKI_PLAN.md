# Sub-Plan: Wikilink Resolution & Advanced Markdown

This plan details Phase 9 of the implementation, focusing on vault-aware Markdown features: Wikilinks, Transclusions, Rename Propagation, and Callouts.

## Overview
Wikilinks (`[[Name]]`) and Transclusions (`![[Name]]`) transform a static Markdown renderer into a networked knowledge base. This requires the Renderer to interact with the `FileStore` to resolve paths and read content at render-time.

---

## Phase 1: Wikilink Syntax & Core Resolution [DONE]
Goal: Parse `[[Name]]` and resolve it to a vault path.

### Step 1.1: Markdown-it Plugin for Wikilinks [DONE]
- **Task**: Create a custom plugin for `markdown-it-py` to recognize `[[...]]` syntax.
- **Action**:
    - Implement a regex-based inline rule.
    - Support aliases: `[[Name|Alias]]`.
    - Support fragments: `[[Name#Heading]]`, `[[Name#^block-id]]`.
- **Verification**: `Renderer.render("[[Foo]]")` emits `<a class="wikilink" href="Foo">Foo</a>`.

### Step 1.2: Vault Resolver Logic (§13.2) [DONE]
- **Task**: Implement the `Resolver` in `core/wikilink/resolver.py`.
- **Logic**:
    - **Name-only**: Scan vault basenames. In case of ambiguity, resolve to the file whose vault-relative path is alphabetically first (absolute resolution).
    - **Path-bearing**: Try vault-relative, then file-relative.
- **Verification**: Unit tests with a mocked vault structure covering all edge cases in §13.2.

---

## Phase 2: Transclusion (Embeds) [IN PROGRESS]
Goal: Inline content from other notes using `![[Name]]`.

### Step 2.1: Basic Note Transclusion (§14) [DONE]
- **Task**: Update Renderer to fetch and inline target content.
- **Action**:
    - Detect `![[...] ]` (images vs notes).
    - If note: read via `FileStore`, recursively render, and inject.
    - **Styling**: Wrap transcluded content in a CSS class with a subtle border/background.
- **Complexity**: Cycles! MUST detect and render an error block instead of crashing.
- **Verification**: Rendering a note that embeds another note shows the child's content with visual indication.

### Step 2.2: Fragment Transclusion
- **Task**: Inline specific headings or block IDs.
- **Action**:
    - Implement "Heading Extractor": extract text between `## Target` and the next `##`.
    - Implement "Block Extractor": find lines ending with `^block-id`.
- **Verification**: Embed only a specific section of a target note.

---

## Phase 3: UI Integration & Navigation [DONE]
Goal: Make links clickable and handle broken links.

### Step 3.1: Preview Click Handling (§7.2, §13.3) [DONE]
- **Task**: Intercept link clicks in `WebKitWebView`.
- **Action**:
    - Emit an event when a wikilink is clicked.
    - Window handler: resolve path and dispatch `OpenFile`.
- **Broken Links**: If unresolved, render red (`--color-link-broken`) and show "Create note?" dialog on click.
- **Verification**: Clicking `[[NonExistent]]` prompts to create the file.

---

## Phase 4: Rename Propagation [COMPLEX & BUGGY]
Goal: Update all links in the vault when a file is moved or renamed.

### Step 4.1: Vault-wide Link Rewriting (§13.4, §22.3)
- **Task**: Implement a service that scans and updates files.
- **Action**:
    - Triggered by `FileRenamed` event or explicit `Rename` command.
    - Walk all `.md` files.
    - For each file, find links pointing to the old path/name and update them.
- **Complexity**: 
    - Regex matching of links across the whole vault is error-prone.
    - Performance: synchronous for <1000 files, background thread for large vaults.
    - Race conditions with active editing.
- **Verification**: Renaming `Foo.md` to `Bar.md` updates `[[Foo]]` to `[[Bar]]` in every other file.

---

## Phase 5: Markdown Extras [EASY]
Goal: Aesthetic and functional parity with Obsidian-style Markdown.

### Step 5.1: Callouts / Admonitions (§12.2)
- **Task**: Support `> [!note] Content` and collapsible variants.
- **Action**:
    - Use `markdown-it-py` plugin or custom block rule.
    - Render as `<div class="callout callout-note">...</div>`.
    - **Collapsible**: Support `> [!note]-` to render as a `<details>` block.
    - CSS: Apply distinct icons and colors per type (note, warning, error, info).
- **Verification**: `> [!warning]- Watch out` renders as a collapsed warning block.

### Step 5.2: Highlight & Sizing
- **Task**: Implement `==highlight==` and `![[image.png|300]]`.
- **Action**:
    - Add `markdown-it-mark` equivalent.
    - Update image renderer to parse size pipe.
- **Verification**: Images resize correctly in preview.

---

## Complex/Buggy Flags 🚩
1. **Rename Propagation (§13.4)**: Rewriting files in bulk can lead to data loss if not perfectly atomic. If a crash happens mid-write, the vault might be inconsistent.
2. **Block References (§12.2)**: Tracking `^block-id` across renames and edits requires a robust indexer or very clever regex.
3. **Fragment Transclusion (§14)**: Defining what "under that heading" means (level hierarchy) is subtle and easy to get wrong with overlapping levels.

---

## Questionaire
See `WIKI_QUESTIONAIRE.md` for open architectural decisions.
