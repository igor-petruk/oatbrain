import tomllib
from pathlib import Path
from oatbrain.core.ports.config import AppConfig, PaletteConfig, InboxConfig


class TomlConfigStore:
    def __init__(self, path: Path):
        self._path = path

    def load(self) -> AppConfig:
        if not self._path.exists():
            return AppConfig()

        with open(self._path, "rb") as f:
            data = tomllib.load(f)

        palette_data = data.get("palette", {})
        palette = PaletteConfig(
            ai_commands=palette_data.get("ai_commands", []),
            ai_commands_fetcher=palette_data.get("ai_commands_fetcher", ""),
            shell_commands=palette_data.get("shell_commands", []),
        )

        inbox_data = data.get("inbox", {})
        inbox = InboxConfig(
            folder=inbox_data.get("folder", "Inbox"),
            process_prefix=inbox_data.get("process_prefix", "Process"),
        )

        return AppConfig(palette=palette, inbox=inbox)
