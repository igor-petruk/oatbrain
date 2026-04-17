import os
import re
from pathlib import Path

def test_core_does_not_import_gi_or_gtk():
    core_dir = Path("src/oatbrain/core")
    if not core_dir.exists():
        return
    
    forbidden = re.compile(r"^\s*(import\s+(gi|Gtk|Adw|WebKit|Vte|GtkSource)|from\s+gi|from\s+oatbrain\.(adapters|ui))")
    
    for root, _, files in os.walk(core_dir):
        for f in files:
            if f.endswith(".py"):
                with open(os.path.join(root, f), "r") as file:
                    for line in file:
                        assert not forbidden.search(line), f"Forbidden import in {f}: {line.strip()}"
