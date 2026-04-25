from pathlib import Path
from oatbrain.core.vault import VaultResolver


def test_resolve_with_marker(tmp_path: Path):
    vault_root = tmp_path / "my_vault"
    vault_root.mkdir()
    (vault_root / ".oatbrain").mkdir()

    deep_path = vault_root / "notes" / "daily"
    deep_path.mkdir(parents=True)

    resolver = VaultResolver(lambda p: f"store_for_{p.name}")
    vault = resolver.resolve(deep_path)

    assert vault.root == vault_root
    assert vault.store == "store_for_my_vault"


def test_resolve_without_marker_uses_given_path(tmp_path: Path):
    some_dir = tmp_path / "normal_dir"
    some_dir.mkdir()

    resolver = VaultResolver(lambda p: "dummy")
    vault = resolver.resolve(some_dir)

    assert vault.root == some_dir.resolve()
