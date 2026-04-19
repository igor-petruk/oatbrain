import re
from markdown_it import MarkdownIt
from markdown_it.rules_inline import StateInline
from oatbrain.core.ports.filestore import VaultPath

# Regex to match ![[Target]], ![[Target|Alias]]
TRANSCLUDE_RE = re.compile(r"!\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")

MAX_DEPTH = 6


def transclude_plugin(md: MarkdownIt) -> None:
    """A markdown-it-py plugin for note transclusion ![[Target]]."""

    def transclude_rule(state: StateInline, silent: bool) -> bool:
        match = TRANSCLUDE_RE.match(state.src[state.pos :])
        if not match:
            return False

        if not silent:
            target_full = match.group(1).strip()
            # Alias is mostly ignored for note transclusion but might be used for sizing later
            
            token = state.push("transclusion", "div", 0)
            token.attrs = {
                "class": "transclusion",
                "data-target": target_full,
            }

        state.pos += match.end()
        return True

    md.inline.ruler.after("wikilink", "transclusion", transclude_rule)
    md.add_render_rule("transclusion", transclude_renderer)


def transclude_renderer(self, tokens, idx, options, env):
    token = tokens[idx]
    target_full = token.attrs.get("data-target", "")
    
    resolver = env.get("resolver")
    filestore = env.get("filestore")
    from_path = env.get("from_path")
    
    if not resolver or not filestore or not from_path:
        return f'<div class="transclusion-error">Error: Missing dependencies for {target_full}</div>'

    # Handle fragments
    if "#" in target_full:
        target, fragment = target_full.split("#", 1)
    else:
        target, fragment = target_full, ""

    # Resolve target
    target_path = resolver.resolve(target, from_path)
    if not target_path:
        return f'<div class="transclusion-error">Broken transclusion: [[{target_full}]]</div>'

    # Check for cycles and depth
    stack = env.get("transclude_stack", [])
    if str(target_path) in stack:
        return f'<div class="transclusion-error">Circular transclusion detected: {target_full}</div>'
    
    if len(stack) >= MAX_DEPTH:
        return f'<div class="transclusion-error">Transclusion depth limit exceeded: {target_full}</div>'

    # Read content
    try:
        content = filestore.read_text(target_path)
    except Exception as e:
        return f'<div class="transclusion-error">Error reading {target_full}: {e}</div>'

    # Recursive render
    new_stack = stack + [str(from_path)]
    new_env = env.copy()
    new_env["transclude_stack"] = new_stack
    new_env["from_path"] = target_path # Update context for links inside transclusion
    
    # Note: we use self (the renderer) to call md.render via the options or similar?
    # Actually, MarkdownIt instance is available in self? No.
    # But we can get it from env if we put it there.
    
    md = env.get("md_instance")
    if not md:
         return f'<div class="transclusion-error">Internal error: md_instance missing</div>'

    # Strip frontmatter from transcluded content for cleaner look?
    # Usually Obsidian doesn't show frontmatter in embeds.
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            content = parts[2]

    rendered_content = md.render(content, env=new_env)
    
    return (
        f'<div class="transclusion" style="border-left: 3px solid var(--color-bg-alt); '
        'padding-left: 1em; margin: 0.5em 0; background: var(--color-bg-alt, rgba(0,0,0,0.05));">'
        f'{rendered_content}'
        '</div>'
    )
