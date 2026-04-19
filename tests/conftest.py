import signal
import pytest
from typing import Generator


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
