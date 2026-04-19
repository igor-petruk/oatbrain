from markdown_it import MarkdownIt
from markdown_it.rules_inline import StateInline


def mark_plugin(md: MarkdownIt) -> None:
    """A markdown-it-py plugin for ==highlight==."""

    def tokenize(state: StateInline, silent: bool) -> bool:
        start = state.pos
        if state.src[start : start + 2] != "==":
            return False

        # Find the closing ==
        pos = start + 2
        while pos < len(state.src) - 1:
            if state.src[pos : pos + 2] == "==":
                if not silent:
                    token = state.push("mark_open", "mark", 1)
                    token.markup = "=="
                    
                    # Store original posMax and restrict it to the closing ==
                    curr_max = state.posMax
                    state.pos += 2
                    state.posMax = pos
                    state.md.inline.tokenize(state)
                    state.posMax = curr_max
                    
                    token = state.push("mark_close", "mark", -1)
                    token.markup = "=="
                
                state.pos = pos + 2
                return True
            pos += 1
        
        return False

    md.inline.ruler.before("emphasis", "mark", tokenize)
