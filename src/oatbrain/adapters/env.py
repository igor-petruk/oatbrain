import os
from pathlib import Path
from oatbrain.core.ports.env import Env


class StdlibEnv:
    """Standard library implementation of the Env port (SPEC §23.2)."""

    def get_xdg_config_home(self) -> Path:
        res = os.environ.get("XDG_CONFIG_HOME")
        if res:
            return Path(res)
        return Path.home() / ".config"

    def get_xdg_state_home(self) -> Path:
        res = os.environ.get("XDG_STATE_HOME")
        if res:
            return Path(res)
        return Path.home() / ".local" / "state"

    def get_xdg_data_home(self) -> Path:
        res = os.environ.get("XDG_DATA_HOME")
        if res:
            return Path(res)
        return Path.home() / ".local" / "share"

    def get_xdg_cache_home(self) -> Path:
        res = os.environ.get("XDG_CACHE_HOME")
        if res:
            return Path(res)
        return Path.home() / ".cache"
