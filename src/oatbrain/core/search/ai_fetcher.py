import subprocess
from typing import List
from oatbrain.core.ports.config import PaletteConfig


class AICommandFetcher:
    def __init__(self, config: PaletteConfig):
        self._config = config

    def fetch(self) -> List[str]:
        commands = list(self._config.ai_commands)

        if self._config.ai_commands_fetcher:
            try:
                result = subprocess.run(
                    self._config.ai_commands_fetcher,
                    shell=True,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                dynamic_commands = [
                    line.strip() for line in result.stdout.splitlines() if line.strip()
                ]
                commands.extend(dynamic_commands)
            except Exception as e:
                print(f"Warning: Failed to fetch dynamic AI commands: {e}")

        return commands
