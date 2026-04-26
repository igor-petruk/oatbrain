from oatbrain.core.state import EditorAreaState, GroupState, TabState
from oatbrain.core.ports.filestore import VaultPath
from oatbrain.ui.editor_area import compute_tab_titles


def _tab(path: str) -> TabState:
    return TabState(open_file=VaultPath.from_str(path))


def _blank() -> TabState:
    return TabState(open_file=None)


def test_single_tab_no_conflict() -> None:
    ea = EditorAreaState(groups=(GroupState(tabs=(_tab("notes/foo.md"),)),))
    titles = compute_tab_titles(ea)
    assert list(titles.values()) == ["foo.md"]


def test_blank_tab_shows_untitled() -> None:
    ea = EditorAreaState(groups=(GroupState(tabs=(_blank(),)),))
    titles = compute_tab_titles(ea)
    assert list(titles.values()) == ["Untitled"]


def test_two_tabs_same_basename_disambiguated() -> None:
    t1 = _tab("work/notes.md")
    t2 = _tab("home/notes.md")
    ea = EditorAreaState(groups=(GroupState(tabs=(t1, t2)),))
    titles = compute_tab_titles(ea)
    assert titles[t1.tab_id] == "notes.md [work]"
    assert titles[t2.tab_id] == "notes.md [home]"


def test_three_tabs_two_share_basename() -> None:
    t1 = _tab("work/notes.md")
    t2 = _tab("home/notes.md")
    t3 = _tab("home/todo.md")
    ea = EditorAreaState(groups=(GroupState(tabs=(t1, t2, t3)),))
    titles = compute_tab_titles(ea)
    assert titles[t1.tab_id] == "notes.md [work]"
    assert titles[t2.tab_id] == "notes.md [home]"
    assert titles[t3.tab_id] == "todo.md"


def test_same_basename_across_groups() -> None:
    t1 = _tab("a/foo.md")
    t2 = _tab("b/foo.md")
    g1 = GroupState(tabs=(t1,))
    g2 = GroupState(tabs=(t2,))
    ea = EditorAreaState(groups=(g1, g2))
    titles = compute_tab_titles(ea)
    assert titles[t1.tab_id] == "foo.md [a]"
    assert titles[t2.tab_id] == "foo.md [b]"


def test_root_level_file_no_parent_hint() -> None:
    # File at vault root has "." as parent; no bracket suffix added.
    t1 = _tab("notes.md")
    t2 = _tab("notes.md")  # same file twice (unusual but must not crash)
    ea = EditorAreaState(groups=(GroupState(tabs=(t1, t2)),))
    titles = compute_tab_titles(ea)
    # Both have same basename and parent is "." so no disambiguation possible
    assert titles[t1.tab_id] == "notes.md"
    assert titles[t2.tab_id] == "notes.md"
