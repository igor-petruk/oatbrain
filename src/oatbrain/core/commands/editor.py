from dataclasses import dataclass

@dataclass(frozen=True)
class UpdateWordCount:
    """Command to update word count in state."""
    count: int

@dataclass(frozen=True)
class SetDirty:
    """Command to mark the editor buffer as dirty or clean."""
    dirty: bool

