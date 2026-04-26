"""Unit tests for EditorArea state-mutation helpers (no GTK required)."""
from typing import Optional
from oatbrain.core.state import EditorAreaState, GroupState, TabState
from oatbrain.core.ports.filestore import VaultPath


def _ea_with_one_tab(open_file: Optional[str] = "note.md") -> EditorAreaState:
    path = VaultPath.from_str(open_file) if open_file else None
    tab = TabState(open_file=path)
    return EditorAreaState(groups=(GroupState(tabs=(tab,)),))


def _split(
    ea: EditorAreaState, group_idx: int = 0, tab_idx: int = 0
) -> EditorAreaState:
    """Simulate _on_split_requested logic as a pure function for testing."""
    g = ea.groups[group_idx]
    source_tab = g.tabs[tab_idx]

    new_tab = TabState(
        open_file=source_tab.open_file,
        mode=source_tab.mode,
        zoom=source_tab.zoom,
        preview_zoom=source_tab.preview_zoom,
    )

    new_groups = []
    new_focus_idx = ea.focused_group_index
    for i, grp in enumerate(ea.groups):
        new_groups.append(grp)
        if grp.group_id == g.group_id:
            new_groups.append(GroupState(tabs=(new_tab,), active_tab_index=0))
            new_focus_idx = len(new_groups) - 1

    expected = len(new_groups) - 1
    # Balance widths equally among all groups (§17.2)
    fractions = [1.0 / (len(new_groups) - i) for i in range(expected)]

    return EditorAreaState(
        groups=tuple(new_groups),
        divider_fractions=tuple(fractions),
        focused_group_index=new_focus_idx,
    )


def test_split_produces_two_groups() -> None:
    ea = _ea_with_one_tab()
    result = _split(ea)
    assert len(result.groups) == 2


def test_split_preserves_source_tab() -> None:
    ea = _ea_with_one_tab()
    result = _split(ea)
    # Source group still has its tab
    assert len(result.groups[0].tabs) == 1
    assert result.groups[0].tabs[0].open_file == VaultPath.from_str("note.md")


def test_split_new_group_duplicates_tab() -> None:
    ea = _ea_with_one_tab()
    result = _split(ea)
    # New group has the same file
    assert result.groups[1].tabs[0].open_file == VaultPath.from_str("note.md")


def test_split_new_tab_has_different_id() -> None:
    ea = _ea_with_one_tab()
    original_id = ea.groups[0].tabs[0].tab_id
    result = _split(ea)
    assert result.groups[1].tabs[0].tab_id != original_id


def test_split_focus_moves_to_new_group() -> None:
    ea = _ea_with_one_tab()
    result = _split(ea)
    assert result.focused_group_index == 1


def test_split_divider_fractions_extended() -> None:
    ea = _ea_with_one_tab()
    result = _split(ea)
    # 2 groups → 1 divider
    assert len(result.divider_fractions) == 1
    assert result.divider_fractions[0] == 0.5


def test_split_from_two_groups_produces_three() -> None:
    t1 = TabState(open_file=VaultPath.from_str("a.md"))
    t2 = TabState(open_file=VaultPath.from_str("b.md"))
    g1 = GroupState(tabs=(t1,))
    g2 = GroupState(tabs=(t2,))
    ea = EditorAreaState(
        groups=(g1, g2), divider_fractions=(0.5,), focused_group_index=0
    )
    result = _split(ea, group_idx=0)
    assert len(result.groups) == 3
    # 3 groups → 2 dividers: [1/3, 1/2]
    assert len(result.divider_fractions) == 2
    assert result.divider_fractions[0] == 1.0 / 3.0
    assert result.divider_fractions[1] == 0.5


def test_focused_group_index_always_in_range() -> None:
    # Regression: split must never produce out-of-range focused_group_index.
    ea = _ea_with_one_tab()
    result = _split(ea)
    assert 0 <= result.focused_group_index < len(result.groups)
