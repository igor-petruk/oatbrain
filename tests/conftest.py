import os
import signal
import pytest
from pathlib import Path
from typing import Generator


@pytest.fixture(autouse=True)
def isolate_xdg(tmp_path: Path) -> Generator[None, None, None]:
    """
    Isolate all tests from the user's real XDG directories.
    Prevents tests from reading or writing to ~/.config/oatbrain or ~/.local/state/oatbrain.
    """
    config_dir = tmp_path / "config"
    state_dir = tmp_path / "state"
    data_dir = tmp_path / "data"
    cache_dir = tmp_path / "cache"

    config_dir.mkdir()
    state_dir.mkdir()
    data_dir.mkdir()
    cache_dir.mkdir()

    # Monkeypatch environment variables
    # We use os.environ directly to ensure it propagates to child processes/threads
    # if any, though build_app reads it immediately.
    old_config = os.environ.get("XDG_CONFIG_HOME")
    old_state = os.environ.get("XDG_STATE_HOME")
    old_data = os.environ.get("XDG_DATA_HOME")
    old_cache = os.environ.get("XDG_CACHE_HOME")

    os.environ["XDG_CONFIG_HOME"] = str(config_dir)
    os.environ["XDG_STATE_HOME"] = str(state_dir)
    os.environ["XDG_DATA_HOME"] = str(data_dir)
    os.environ["XDG_CACHE_HOME"] = str(cache_dir)

    yield

    if old_config is not None:
        os.environ["XDG_CONFIG_HOME"] = old_config
    else:
        del os.environ["XDG_CONFIG_HOME"]

    if old_state is not None:
        os.environ["XDG_STATE_HOME"] = old_state
    else:
        del os.environ["XDG_STATE_HOME"]

    if old_data is not None:
        os.environ["XDG_DATA_HOME"] = old_data
    else:
        del os.environ["XDG_DATA_HOME"]

    if old_cache is not None:
        os.environ["XDG_CACHE_HOME"] = old_cache
    else:
        del os.environ["XDG_CACHE_HOME"]


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(
    item: pytest.Item, nextitem: object
) -> Generator[None, None, None]:
    """
    Sets a 3-second alarm for each test to prevent hangs.
    Only works on Unix-like systems.
    """

    def handler(signum: int, frame: object) -> None:
        raise TimeoutError(f"Test timed out after 3 seconds: {item.nodeid}")

    # Set the signal handler and the 3-second alarm
    old_handler = signal.signal(signal.SIGALRM, handler)
    signal.alarm(3)
    try:
        yield
    finally:
        # Disable the alarm and restore the old handler
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
