# Sub-Plan: Mermaid Diagram Support

This plan details Phase 12 of the implementation, focusing on offline-first Mermaid diagram rendering.

## Overview
Mermaid diagrams are written in Markdown code blocks (````mermaid`). To render them in the WebKit preview without relying on a constant internet connection, we will fetch `mermaid.min.js` on startup and cache it locally.

---

## Phase 1: Asset Management & Caching
Goal: Fetch and cache the Mermaid library in the background.

### Step 1.1: Async Fetcher
- **Task**: Implement a background downloader for `mermaid.min.js`.
- **Action**:
    - Add a function to download `https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js`.
    - Save it to `~/.cache/oatbrain/mermaid.min.js`.
    - Run this asynchronously (e.g., using `ThreadPoolExecutor` and `urllib`) during app startup in `AdwAppShell.on_activate`.
    - Emit an event (e.g., `MermaidFetchResult`) indicating success or failure.

---

## Phase 2: State & UI Notifications
Goal: Warn the user if the asset cannot be fetched, allowing them to dismiss it.

### Step 2.1: AppState Updates
- **Task**: Track dismissal state persistently.
- **Action**:
    - Add `mermaid_dismissed: bool = False` to `AppState`.
    - Ensure it is serialized/deserialized in `TomlStateStore`.
    - Create a `DismissMermaidWarning` command to set this to `True`.

### Step 2.2: Adw.Banner Notification
- **Task**: Display a non-intrusive warning in the UI.
- **Action**:
    - Listen for the `MermaidFetchResult` event in `ui/window.py`.
    - If the fetch fails AND the cached file does not exist AND `mermaid_dismissed` is False:
        - Show an `Adw.Banner` at the top of the window: "Mermaid support requires an internet connection to download its library once. Code blocks will not render."
        - Provide a "Dismiss" button on the banner that dispatches `DismissMermaidWarning`.

---

## Phase 3: Markdown & Preview Integration
Goal: Transform the Markdown code block and initialize the JS library.

### Step 3.1: Markdown-it Plugin
- **Task**: Intercept ````mermaid` blocks.
- **Action**:
    - Update `MarkdownItRenderer` to parse fenced code blocks.
    - If the language is `mermaid`, output `<div class="mermaid">...</div>` instead of standard `<pre><code>`.

### Step 3.2: WebKit Injection
- **Task**: Load the cached JS file into the preview.
- **Action**:
    - In `Preview._wrap_html`, check if the cached `mermaid.min.js` exists.
    - If it does, inject `<script src="file:///home/user/.cache/oatbrain/mermaid.min.js"></script>` and `<script>mermaid.initialize({startOnLoad:true});</script>` into the HTML.
