from dataclasses import dataclass
from oatbrain.core.state.app_state import AppState

@dataclass(frozen=True)
class StateUpdated:
    """Emitted whenever the global AppState changes."""
    state: AppState
