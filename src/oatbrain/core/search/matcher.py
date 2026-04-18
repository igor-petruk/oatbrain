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
        results = fzf.prompt(items, f"--filter='{query}'")
        return results if isinstance(results, list) else []

    except Exception as e:
        print(f"Warning: pyfzf failed: {e}. Falling back to simple substring match.")
        query_lower = query.lower()
        return [item for item in items if query_lower in item.lower()]
