from dataclasses import dataclass
from pathlib import Path
from oatbrain.core.state.app_state import AppState, EditorState
from oatbrain.core.bus import EventBus, CommandRouter

@dataclass(frozen=True)
class OpenFile:
    path: str

@dataclass(frozen=True)
class StateUpdated:
    state: AppState

def test_command_updates_state_and_emits_event():
    initial_state = AppState(vault_root=Path("/vault"))
    event_bus = EventBus()
    router = CommandRouter()
    
    current_state = initial_state
    received_events = []
    
    def on_state_updated(event: StateUpdated):
        nonlocal current_state
        current_state = event.state
        received_events.append(event)
        
    event_bus.subscribe(StateUpdated, on_state_updated)
    
    def handle_open_file(cmd: OpenFile):
        nonlocal current_state
        # In real app, this would be more complex
        new_editor = EditorState(open_file=cmd.path) # type: ignore
        current_state = AppState(
            vault_root=current_state.vault_root,
            editor=new_editor
        )
        event_bus.publish(StateUpdated(current_state))
        
    router.register(OpenFile, handle_open_file)
    
    # Act
    router.dispatch(OpenFile("daily.md"))
    
    # Assert
    assert current_state.editor.open_file == "daily.md"
    assert len(received_events) == 1
    assert received_events[0].state == current_state
