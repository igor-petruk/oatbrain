from typing import Protocol
from oatbrain.core.state.app_state import AppState


class StateStore(Protocol):
    """Port for persistent state storage."""

    def save(self, state: AppState) -> None:
        ...

    def load(self) -> AppState:
        ...
