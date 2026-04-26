import pytest
from pathlib import Path
from oatbrain.adapters.state import TomlStateStore
from oatbrain.core.state import AppState, EditorAreaState, GroupState, TabState
from oatbrain.core.ports.filestore import VaultPath


def test_toml_store_roundtrip(tmp_path: Path) -> None:
    # Create the actual file so stale-file cleanup doesn't drop it.
    (tmp_path / "note.md").write_text("hello")

    store_path = tmp_path / "state.toml"
    store = TomlStateStore(store_path)

    tab = TabState(
        open_file=VaultPath.from_str("note.md"),
        mode="preview",
        zoom=1.5,
        preview_zoom=0.9,
    )
    editor_area = EditorAreaState(
        groups=(GroupState(tabs=(tab,), active_tab_index=0),),
        divider_fractions=(0.5,),
        focused_group_index=0,
    )
    state = AppState(
        vault_root=tmp_path,
        tree_width=200,
        tree_visible=False,
        tree_zoom=1.2,
        terminal_width=300,
        terminal_zoom=0.8,
        editor_area=editor_area,
        theme_id="monokai-dark",
    )

    store.save(state)
    loaded = store.load()

    assert loaded.tree_width == 200
    assert loaded.tree_visible is False
    assert loaded.tree_zoom == 1.2
    assert loaded.terminal_width == 300
    assert loaded.terminal_zoom == 0.8

    assert len(loaded.editor_area.groups) == 1
    loaded_tab = loaded.editor_area.groups[0].tabs[0]
    assert loaded_tab.open_file == VaultPath.from_str("note.md")
    assert loaded_tab.mode == "preview"
    assert loaded_tab.zoom == 1.5
    assert loaded_tab.preview_zoom == 0.9
    # divider_fractions is clamped to (N_groups - 1) entries; single group → ()
    assert loaded.editor_area.divider_fractions == ()
    assert loaded.editor_area.focused_group_index == 0


def test_toml_store_load_missing_file(tmp_path: Path) -> None:
    store_path = tmp_path / "missing.toml"
    store = TomlStateStore(store_path)
    with pytest.raises(FileNotFoundError):
        store.load()


def test_toml_store_roundtrip_blank_tab(tmp_path: Path) -> None:
    store_path = tmp_path / "state_no_file.toml"
    store = TomlStateStore(store_path)

    state = AppState(
        vault_root=tmp_path,
        editor_area=EditorAreaState(
            groups=(GroupState(tabs=(TabState(open_file=None),), active_tab_index=0),)
        ),
    )

    store.save(state)
    loaded = store.load()
    assert loaded.editor_area.groups[0].tabs[0].open_file is None


def test_toml_store_stale_file_cleanup(tmp_path: Path) -> None:
    # Tab pointing to nonexistent file should be dropped; empty group removed;
    # fallback group with blank tab inserted.
    store_path = tmp_path / "state_stale.toml"
    store = TomlStateStore(store_path)

    tab = TabState(open_file=VaultPath.from_str("ghost.md"))
    state = AppState(
        vault_root=tmp_path,
        editor_area=EditorAreaState(groups=(GroupState(tabs=(tab,)),)),
    )

    store.save(state)
    loaded = store.load()

    # Ghost file doesn't exist → tab dropped → group removed → fallback inserted
    assert len(loaded.editor_area.groups) == 1
    assert loaded.editor_area.groups[0].tabs[0].open_file is None


def test_toml_store_stale_partial_cleanup(tmp_path: Path) -> None:
    # One tab exists, one doesn't; group kept with remaining tab.
    (tmp_path / "real.md").write_text("content")

    store_path = tmp_path / "state_partial.toml"
    store = TomlStateStore(store_path)

    real_tab = TabState(open_file=VaultPath.from_str("real.md"))
    ghost_tab = TabState(open_file=VaultPath.from_str("ghost.md"))
    state = AppState(
        vault_root=tmp_path,
        editor_area=EditorAreaState(
            groups=(GroupState(tabs=(real_tab, ghost_tab), active_tab_index=0),)
        ),
    )

    store.save(state)
    loaded = store.load()

    assert len(loaded.editor_area.groups) == 1
    assert len(loaded.editor_area.groups[0].tabs) == 1
    assert loaded.editor_area.groups[0].tabs[0].open_file == VaultPath.from_str(
        "real.md"
    )
