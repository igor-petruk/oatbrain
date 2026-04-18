import os
import re
from pathlib import Path


def test_core_does_not_import_gi_or_gtk():
    core_dir = Path("src/oatbrain/core")
    if not core_dir.exists():
        return

    forbidden_patterns = [
        r"^\s*(import\s+(gi|Gtk|Adw|WebKit|Vte|GtkSource))",
        r"^\s*(from\s+gi|from\s+oatbrain\.(adapters|ui))",
    ]
    forbidden = re.compile("|".join(forbidden_patterns))

    for root, _, files in os.walk(core_dir):
        for f in files:
            if f.endswith(".py"):
                file_path = os.path.join(root, f)
                with open(file_path, "r") as file:
                    for line in file:
                        msg = f"Forbidden import in {f}: {line.strip()}"
                        assert not forbidden.search(line), msg
