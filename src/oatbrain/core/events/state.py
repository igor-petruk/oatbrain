from dataclasses import dataclass
from oatbrain.core.state import AppState


@dataclass(frozen=True)
class StateUpdated:
    """Emitted whenever the global AppState changes."""

    state: AppState
