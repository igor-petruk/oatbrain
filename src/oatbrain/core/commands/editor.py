from dataclasses import dataclass

@dataclass(frozen=True)
class UpdateWordCount:
    """Command to update word count in state."""
    count: int
