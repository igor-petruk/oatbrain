from typing import Protocol
from pathlib import Path


class Env(Protocol):
    def get_xdg_config_home(self) -> Path:
        ...

    def get_xdg_state_home(self) -> Path:
        ...

    def get_xdg_data_home(self) -> Path:
        ...
