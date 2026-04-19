import re
from typing import Any
from markdown_it import MarkdownIt
from markdown_it.rules_inline import StateInline

# Regex to match [[Target]], [[Target|Alias]], 
# [[Target#Fragment]], [[Target#Fragment|Alias]]
# Group 1: Target (including path and fragments)
# Group 2: Alias (optional)
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def wikilink_plugin(md: MarkdownIt) -> None:
    """A markdown-it-py plugin for parsing wikilinks [[Target|Alias]]."""

    def wikilink_rule(state: StateInline, silent: bool) -> bool:
        match = WIKILINK_RE.match(state.src[state.pos :])
        if not match:
            return False

        if not silent:
            target_full = match.group(1).strip()
            alias = match.group(2).strip() if match.group(2) else None

            # Split target into path and fragment if present
            if "#" in target_full:
                target, fragment = target_full.split("#", 1)
            else:
                target, fragment = target_full, ""

            token = state.push("wikilink", "a", 0)
            token.attrs = {
                "class": "wikilink",
                "href": target_full,  # The full string is used for resolution later
                "data-target": target,
                "data-fragment": fragment,
            }
            token.content = alias if alias else target_full

        state.pos += match.end()
        return True

    md.inline.ruler.after("link", "wikilink", wikilink_rule)
    md.add_render_rule("wikilink", wikilink_renderer)


def wikilink_renderer(
    self: Any, tokens: Any, idx: int, options: Any, env: Any
) -> str:
    token = tokens[idx]
    label = token.content
    target_full = token.attrs.get("href", "")
    
    resolver = env.get("resolver")
    from_path = env.get("from_path")
    
    extra_class = ""
    if resolver and from_path:
        # Check fragment
        target = target_full.split("#")[0] if "#" in target_full else target_full
        resolved = resolver.resolve(target, from_path)
        if not resolved:
            extra_class = " broken"

    # Use oatbrain:// scheme to make it easy to intercept in WebKit
    href = f"oatbrain://vault/{target_full}"
    return f'<a class="wikilink{extra_class}" href="{href}">{label}</a>'
