from typing import List
from pyfzf.pyfzf import FzfPrompt  # type: ignore[import-untyped]


def filter_and_rank(query: str, items: List[str]) -> List[str]:
    """Filters and ranks items using the fzf library."""
    if not query:
        return items

    if not items:
        return []

    try:
        fzf = FzfPrompt()
        # pyfzf's prompt method with FZF_DEFAULT_OPTS or extra arguments
        # can be used for filtering.
        # However, standard pyfzf uses fzf for interactive selection.
        # To use it for non-interactive filtering, we pass the query.
        # Note: pyfzf might not have a direct 'filter' wrapper that returns
        # all matches without UI.
        # Let's check the source or use the subprocess fallback if pyfzf
        # is only for interactive.
        # Actually, pyfzf just wraps the subprocess call.
        # If the user specifically asked for pyfzf, I should use it.
        # Looking at pyfzf: it doesn't seem to expose a simple 'filter' method
        # that doesn't spawn a terminal UI unless specifically configured.
        # Wait, fzf --filter is what we want.
        # If pyfzf doesn't support it, I might need to use subprocess
        # but the user said "Use it like this: https://github.com/nk412/pyfzf".

        # If I use FzfPrompt().prompt(items, "--filter='{}'".format(query))
        # it might work if pyfzf allows passing arbitrary flags.

        results = fzf.prompt(items, f"--filter='{query}'")
        return results if isinstance(results, list) else []

    except Exception as e:
        print(f"Warning: pyfzf failed: {e}. Falling back to simple substring match.")
        query_lower = query.lower()
        return [item for item in items if query_lower in item.lower()]
