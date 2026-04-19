import re
from typing import Any
from markdown_it import MarkdownIt
from markdown_it.token import Token

# Regex to match [!type] or [!type]- (collapsible) or [!type]+ (expanded)
CALLOUT_RE = re.compile(r"^\[!(\w+)\]([-+])?(.*)$")


def callout_plugin(md: MarkdownIt) -> None:
    """A markdown-it-py plugin for Obsidian-style callouts.

    Transforms blockquotes starting with [!type] into callout divs/details.
    """

    def callout_rule(state: Any) -> None:
        tokens = state.tokens
        i = 0
        while i < len(tokens):
            if tokens[i].type == "blockquote_open":
                # Find the first inline token inside the blockquote
                j = i + 1
                inline_token = None
                while j < len(tokens) and tokens[j].type != "blockquote_close":
                    if tokens[j].type == "inline":
                        inline_token = tokens[j]
                        break
                    j += 1

                if inline_token and inline_token.content:
                    lines = inline_token.content.split("\n")
                    first_line = lines[0]
                    match = CALLOUT_RE.match(first_line)

                    if match:
                        callout_type = match.group(1).lower()
                        collapse_char = match.group(2)
                        title = match.group(3).strip()

                        is_collapsible = collapse_char in ("-", "+")
                        is_collapsed = collapse_char == "-"

                        if not title:
                            title = callout_type.capitalize()

                        # 1. Transform blockquote open/close
                        tokens[i].type = "callout_open"
                        tokens[i].tag = "details" if is_collapsible else "div"
                        tokens[i].attrs = {
                            "class": f"callout callout-{callout_type}",
                            "data-callout": callout_type,
                        }
                        if is_collapsible and not is_collapsed:
                            tokens[i].attrs["open"] = ""

                        # 2. Find blockquote close and transform it
                        k = i + 1
                        depth = 1
                        while k < len(tokens):
                            if tokens[k].type == "blockquote_open":
                                depth += 1
                            elif tokens[k].type == "blockquote_close":
                                depth -= 1
                                if depth == 0:
                                    tokens[k].type = "callout_close"
                                    tokens[k].tag = tokens[i].tag
                                    break
                            k += 1

                        # 3. Create Title/Summary tokens using Token class
                        title_tag = "summary" if is_collapsible else "div"
                        title_open = Token("callout_title_open", title_tag, 1)
                        title_open.attrs = {"class": "callout-title"}

                        title_inline = Token("inline", "", 0)
                        title_inline.content = title
                        title_inline.level = tokens[i].level + 1
                        title_inline.children = []  # core rule will handle this

                        title_close = Token("callout_title_close", title_tag, -1)

                        # 4. Remove the callout marker from the original content
                        if len(lines) > 1:
                            inline_token.content = "\n".join(lines[1:])
                        else:
                            inline_token.content = ""

                        # 5. Insert title tokens after callout_open
                        tokens[i + 1 : i + 1] = [title_open, title_inline, title_close]

                        # Skip processing the inner tokens of this callout
                        i = k + 3
                        continue

            i += 1

    md.core.ruler.after("block", "callout", callout_rule)
