from typing import Protocol, List
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PaletteConfig:
    ai_commands: List[str] = field(default_factory=list)
    ai_commands_fetcher: str = ""
    shell_commands: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class InboxConfig:
    folder: str = "Inbox"
    process_prefix: str = "Process"


@dataclass(frozen=True)
class AppConfig:
    palette: PaletteConfig = field(default_factory=PaletteConfig)
    inbox: InboxConfig = field(default_factory=InboxConfig)


class ConfigStore(Protocol):
    def load(self) -> AppConfig:
        ...
