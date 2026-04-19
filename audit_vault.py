
import os
import re
import sys
from dataclasses import dataclass
from typing import Iterable, Optional, List, Dict

# Add src to sys.path to import oatbrain
sys.path.append('src')

from oatbrain.core.ports.filestore import VaultPath, FileEntry
from oatbrain.core.wikilink.resolver import WikilinkResolver

@dataclass
class AuditResult:
    source_file: str
    link_target: str
    resolved_path: Optional[str]
    status: str
    suggestion: Optional[str] = None

class FakeFileStore:
    def __init__(self, files: List[str]) -> None:
        self.files = set(files)
        self.all_files = files

    def exists(self, p: VaultPath) -> bool:
        return str(p) in self.files

    def walk(self, root: VaultPath) -> Iterable[FileEntry]:
        for f in self.all_files:
            yield FileEntry(
                path=VaultPath.from_str(f),
                is_dir=False,
                is_readonly=False,
                size=0,
                mtime=0.0,
            )

def extract_links(content: str) -> List[str]:
    # Regex to find [[target]] and ![[target]]
    return re.findall(r'!?\[\[([^\]|#]+)', content)

def audit_vault(vault_root: str):
    all_files = []
    for root, dirs, files in os.walk(vault_root):
        for file in files:
            full_path = os.path.join(root, file)
            # Skip broken symlinks but record them for the file tree
            rel_path = os.path.relpath(full_path, vault_root)
            all_files.append(rel_path)

    all_files.sort()
    
    # Store with only existing files for resolution
    existing_files = [f for f in all_files if os.path.exists(os.path.join(vault_root, f))]
    store = FakeFileStore(existing_files)
    resolver = WikilinkResolver(store)
    
    results: List[AuditResult] = []
    
    # Basename map for "Resolution Failure" detection
    basename_map: Dict[str, List[str]] = {}
    for f in existing_files:
        basename = os.path.basename(f)
        if basename not in basename_map:
            basename_map[basename] = []
        basename_map[basename].append(f)
        
        # Also map without .md extension
        if basename.endswith('.md'):
            name_without_ext = basename[:-3]
            if name_without_ext not in basename_map:
                basename_map[name_without_ext] = []
            if f not in basename_map[name_without_ext]:
                basename_map[name_without_ext].append(f)

    for rel_path in existing_files:
        if not rel_path.endswith('.md'):
            continue
            
        full_path = os.path.join(vault_root, rel_path)
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading {full_path}: {e}")
            continue
            
        links = extract_links(content)
        source_vpath = VaultPath.from_str(rel_path)
        
        for link in links:
            resolved = resolver.resolve(link, source_vpath)
            
            if resolved:
                resolved_str = str(resolved)
                if resolved_str in existing_files:
                    results.append(AuditResult(rel_path, link, resolved_str, 'OK'))
                else:
                    results.append(AuditResult(rel_path, link, resolved_str, 'Resolved to Non-Existent Path'))
            else:
                # Resolve failed
                # Instructions: If a link resolves to None, search the file tree for any file with a matching basename.
                link_basename = os.path.basename(link)
                # Try with and without .md
                potential_matches = basename_map.get(link_basename)
                if not potential_matches and not link_basename.endswith('.md'):
                    potential_matches = basename_map.get(f"{link_basename}.md")
                
                if potential_matches:
                    results.append(AuditResult(
                        rel_path, link, None, 'Resolution Failure', 
                        suggestion=f"Found matches: {', '.join(potential_matches)}"
                    ))
                else:
                    results.append(AuditResult(rel_path, link, None, 'Intentional Broken Link (TODO)'))

    # Group results
    report = {
        'OK': [],
        'Resolution Failure': [],
        'Intentional Broken Link (TODO)': [],
        'Resolved to Non-Existent Path': []
    }
    
    for res in results:
        report[res.status].append(res)
        
    print("# Vault Audit Report")
    
    print("\n## File Tree Map")
    for f in all_files:
        if f in existing_files:
            print(f"- {f}")
        else:
            print(f"- {f} (Broken Symlink)")
            
    print(f"\nTotal files in vault: {len(all_files)}")
    print(f"Total links audited: {len(results)}")
    
    for status, res_list in report.items():
        if not res_list:
            continue
        print(f"\n## {status} ({len(res_list)})")
        
        current_source = None
        for res in res_list:
            if res.source_file != current_source:
                current_source = res.source_file
                print(f"\nFile: `{res.source_file}`")
            
            line = f"  - `[[{res.link_target}]]`"
            if res.resolved_path:
                line += f" -> `{res.resolved_path}`"
            if res.suggestion:
                line += f" (Suggestion: {res.suggestion})"
            print(line)

if __name__ == "__main__":
    audit_vault('/home/user/Vault')
