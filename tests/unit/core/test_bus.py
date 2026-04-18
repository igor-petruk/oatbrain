from pathlib import Path
from oatbrain.core.state.app_state import AppState, EditorState
from oatbrain.core.bus import EventBus, CommandRouter
from oatbrain.core.commands import OpenFile
from oatbrain.core.events.state import StateUpdated
from oatbrain.core.ports.filestore import VaultPath

def test_command_updates_state_and_emits_event() -> None:
    initial_state = AppState(vault_root=Path("/vault"))
    event_bus = EventBus()
    router = CommandRouter()
    
    current_state = initial_state
    received_events = []
    
    def on_state_updated(event: StateUpdated) -> None:
        nonlocal current_state
        current_state = event.state
        received_events.append(event)
        
    event_bus.subscribe(StateUpdated, on_state_updated)
    
    def handle_open_file(cmd: OpenFile) -> None:
        nonlocal current_state
        new_editor = EditorState(open_file=cmd.path)
        current_state = AppState(
            vault_root=current_state.vault_root,
            editor=new_editor
        )
        event_bus.publish(StateUpdated(current_state))
        
    router.register(OpenFile, handle_open_file)
    
    # Act
    path = VaultPath.from_str("daily.md")
    router.dispatch(OpenFile(path=path))
    
    # Assert
    assert current_state.editor.open_file == path
    assert len(received_events) == 1
    assert received_events[0].state == current_state
