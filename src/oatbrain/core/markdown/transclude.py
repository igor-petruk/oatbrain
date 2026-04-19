import re
from typing import Any
from markdown_it import MarkdownIt
from markdown_it.rules_inline import StateInline

# Regex to match ![[Target]], ![[Target|Alias]]
TRANSCLUDE_RE = re.compile(r"!\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")

MAX_DEPTH = 6

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}


def transclude_plugin(md: MarkdownIt) -> None:
    """A markdown-it-py plugin for note and image transclusion ![[Target]]."""

    def transclude_rule(state: StateInline, silent: bool) -> bool:
        match = TRANSCLUDE_RE.match(state.src[state.pos :])
        if not match:
            return False

        if not silent:
            target_full = match.group(1).strip()
            alias = match.group(2).strip() if match.group(2) else ""

            token = state.push("transclusion", "div", 0)
            token.attrs = {
                "class": "transclusion",
                "data-target": target_full,
                "data-alias": alias,
            }

        state.pos += match.end()
        return True

    md.inline.ruler.after("wikilink", "transclusion", transclude_rule)
    md.add_render_rule("transclusion", transclude_renderer)


def extract_heading_content(content: str, heading_target: str) -> str:
    """Extracts content under a specific heading."""
    lines = content.split("\n")
    start_line = -1
    # Match heading exactly or starting with #s
    # e.g. "## Target" or "Target" if it's the text of any level heading
    pattern = re.compile(rf"^(#+)\s+{re.escape(heading_target)}\s*$")
    
    for i, line in enumerate(lines):
        match = pattern.match(line)
        if match:
            start_line = i
            level = len(match.group(1))
            break
    
    if start_line == -1:
        return content # Fallback to full content if heading not found
    
    extracted = []
    # Skip the heading itself? Usually Obsidian includes the heading.
    extracted.append(lines[start_line])
    
    for i in range(start_line + 1, len(lines)):
        line = lines[i]
        # Check if we hit another heading of same or higher level
        match = re.match(r"^(#+)\s+", line)
        if match:
            if len(match.group(1)) <= level:
                break
        extracted.append(line)
        
    return "\n".join(extracted)


def transclude_renderer(
    self: Any, tokens: Any, idx: int, options: Any, env: Any
) -> str:
    token = tokens[idx]
    target_full = token.attrs.get("data-target", "")
    alias = token.attrs.get("data-alias", "")

    resolver = env.get("resolver")
    filestore = env.get("filestore")
    from_path = env.get("from_path")

    if not resolver or not filestore or not from_path:
        return (
            '<div class="transclusion-error">'
            f"Error: Missing dependencies for {target_full}</div>"
        )

    # Handle fragments
    if "#" in target_full:
        target, fragment = target_full.split("#", 1)
    else:
        target, fragment = target_full, ""

    # Resolve target
    target_path = resolver.resolve(target, from_path)
    if not target_path:
        return (
            '<div class="transclusion-error">'
            f"Broken transclusion: [[{target_full}]]</div>"
        )

    # 1. Handle Images
    lower_path = str(target_path).lower()
    if any(lower_path.endswith(ext) for ext in IMAGE_EXTS):
        # We need the absolute path for WebKit to load it.
        # This currently relies on LocalFileStore having a _get_path method.
        # In a more robust implementation, the FileStore protocol would
        # provide a way to get a URL/Path for external display.
        try:
            if hasattr(filestore, "_get_path"):
                abs_path = filestore._get_path(target_path)
            else:
                # Fallback or error for other filestores
                abs_path = str(target_path)

            style = ""
            if alias.isdigit():
                style = f"width: {alias}px;"

            return f'<img src="file://{abs_path}" alt="{alias}" style="{style}">'
        except Exception:
            return (
                f'<div class="transclusion-error">'
                f"Error loading image: {target}</div>"
            )

    # 2. Handle Notes
    # Check for cycles and depth
    stack = env.get("transclude_stack", [])
    if str(target_path) in stack:
        return (
            '<div class="transclusion-error">'
            f"Circular transclusion detected: {target_full}</div>"
        )

    if len(stack) >= MAX_DEPTH:
        return (
            '<div class="transclusion-error">'
            f"Transclusion depth limit exceeded: {target_full}</div>"
        )

    # Read content
    try:
        content = filestore.read_text(target_path)
    except Exception as e:
        return f'<div class="transclusion-error">Error reading {target_full}: {e}</div>'

    # Handle heading fragment
    if fragment:
        content = extract_heading_content(content, fragment)

    # Recursive render
    new_stack = stack + [str(from_path)]
    new_env = env.copy()
    new_env["transclude_stack"] = new_stack
    new_env["from_path"] = target_path

    md = env.get("md_instance")
    if not md:
        return (
            '<div class="transclusion-error">Internal error: md_instance missing</div>'
        )

    # Strip frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            content = parts[2]

    rendered_content = md.render(content, env=new_env)

    return (
        f'<div class="transclusion" style="border-left: 3px solid var(--color-bg-alt); '
        "padding-left: 1em; margin: 0.5em 0; "
        'background: var(--color-bg-alt, rgba(0,0,0,0.05));">'
        f"{rendered_content}"
        "</div>"
    )
