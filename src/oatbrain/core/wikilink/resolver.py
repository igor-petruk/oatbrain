from typing import Optional
from oatbrain.core.ports.filestore import FileStore, VaultPath


class WikilinkResolver:
    """Resolves wikilink targets to vault paths (SPEC §13.2)."""

    def __init__(self, filestore: FileStore) -> None:
        self._filestore = filestore

    def resolve(self, target: str, source_path: VaultPath) -> Optional[VaultPath]:
        """Resolves a target string to a VaultPath.
        
        target: the string inside [[...]] (before any | or #)
        source_path: the path of the file containing the link
        """
        # 1. Path-bearing check (contains / or starts with ../)
        if "/" in target or target.startswith(".."):
            # Try vault-relative
            vault_rel = VaultPath.from_str(target)
            if self._filestore.exists(vault_rel):
                return vault_rel
            
            # Try file-relative
            source_parts = str(source_path).split("/")
            if len(source_parts) > 1:
                parent_dir = "/".join(source_parts[:-1])
                file_rel_str = f"{parent_dir}/{target}"
            else:
                file_rel_str = target
            
            file_rel = VaultPath.from_str(file_rel_str)
            if self._filestore.exists(file_rel):
                return file_rel
            
            # Implied .md for path-bearing
            if not target.endswith(".md"):
                md_target = target + ".md"
                vault_rel_md = VaultPath.from_str(md_target)
                if self._filestore.exists(vault_rel_md):
                    return vault_rel_md
                
                if len(source_parts) > 1:
                    file_rel_md_str = f"{parent_dir}/{md_target}"
                else:
                    file_rel_md_str = md_target
                file_rel_md = VaultPath.from_str(file_rel_md_str)
                if self._filestore.exists(file_rel_md):
                    return file_rel_md

            return None

        # 2. Name-only resolution (Global scan)
        matches = []
        for entry in self._filestore.walk(VaultPath.from_str("")):
            if entry.is_dir:
                continue
            
            path_str = str(entry.path)
            basename = path_str.split("/")[-1]
            if basename == target or basename == f"{target}.md":
                matches.append(entry.path)
        
        if not matches:
            return None
        
        if len(matches) == 1:
            return matches[0]
        
        # Multiple matches: Sort by:
        # 1. Depth (number of /) - shortest path from root wins
        # 2. Same folder as source (boolean tie-breaker)
        # 3. Alphabetical tie-breaker
        source_parts = str(source_path).split("/")
        source_dir = "/".join(source_parts[:-1]) if len(source_parts) > 1 else ""
        
        def sort_key(p: VaultPath):
            path_str = str(p)
            parts = path_str.split("/")
            depth = len(parts) - 1
            is_same_folder = "/".join(parts[:-1]) == source_dir if len(parts) > 1 else source_dir == ""
            return (depth, not is_same_folder, path_str)
            
        matches.sort(key=sort_key)
        return matches[0]
