from typing import Protocol, List
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PaletteConfig:
    ai_commands: List[str] = field(default_factory=list)
    ai_commands_fetcher: str = ""


@dataclass(frozen=True)
class AppConfig:
    palette: PaletteConfig = field(default_factory=PaletteConfig)


class ConfigStore(Protocol):
    def load(self) -> AppConfig:
        ...
