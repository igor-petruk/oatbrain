import os
import pytest
from pathlib import Path
from oatbrain.adapters.filestore.local import LocalFileStore, VaultPath

def test_local_filestore_lifecycle(tmp_path: Path) -> None:
    vault_root = tmp_path / "vault"
    vault_root.mkdir()
    store = LocalFileStore(vault_root)
    
    # Write
    p = VaultPath.from_str("note.md")
    store.write_text(p, "hello world")
    
    # Exists & Read
    assert store.exists(p)
    assert store.read_text(p) == "hello world"
    
    # Stat
    entry = store.stat(p)
    assert not entry.is_dir
    assert entry.size == 11
    
    # List
    entries = store.list_dir(VaultPath.from_str("."))
    assert len(entries) == 1
    assert entries[0].path == p
    
    # Rename
    p2 = VaultPath.from_str("new_note.md")
    store.rename(p, p2)
    assert not store.exists(p)
    assert store.exists(p2)
    
    # Walk
    subdir = vault_root / "sub"
    subdir.mkdir()
    (subdir / "other.md").write_text("other")
    
    all_entries = list(store.walk(VaultPath.from_str(".")))
    # sub, sub/other.md, new_note.md
    assert len(all_entries) == 3
    
    # Delete
    store.delete(p2)
    assert not store.exists(p2)

def test_symlink_name_preservation(tmp_path: Path) -> None:
    vault_root = tmp_path / "vault"
    vault_root.mkdir()
    store = LocalFileStore(vault_root)
    
    # Create target
    target = vault_root / "target.md"
    target.write_text("content")
    
    # Create symlink
    link = vault_root / "link.md"
    os.symlink("target.md", link)
    
    # List dir
    entries = store.list_dir(VaultPath.from_str("."))
    names = {e.path.path.name for e in entries}
    
    assert "link.md" in names
    assert "target.md" in names
    
    # Check specific entry for link.md
    link_entry = next(e for e in entries if e.path.path.name == "link.md")
    assert str(link_entry.path) == "link.md"

def test_sandboxing(tmp_path: Path) -> None:
    vault_root = tmp_path / "vault"
    vault_root.mkdir()
    store = LocalFileStore(vault_root)
    
    with pytest.raises(PermissionError):
        store.read_text(VaultPath.from_str("../outside.txt"))
