from oatbrain.core.search import filter_and_rank


def test_filter_and_rank_empty_query() -> None:
    items = ["apple", "banana", "cherry"]
    assert filter_and_rank("", items) == items


def test_filter_and_rank_no_items() -> None:
    assert filter_and_rank("query", []) == []


def test_filter_and_rank_matches() -> None:
    items = ["apple", "banana", "cherry"]
    # Depending on fzf availability, this will either use fzf or fallback
    results = filter_and_rank("ap", items)
    assert "apple" in results
    assert "banana" not in results
    assert "cherry" not in results
