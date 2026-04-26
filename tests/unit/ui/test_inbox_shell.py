import pytest
from unittest.mock import MagicMock
from pathlib import Path
from oatbrain.ui.window import AdwAppShell
from oatbrain.core.bus import EventBus, CommandRouter
from oatbrain.core.state import AppState
from oatbrain.core.ports.filestore import FileStore
from oatbrain.core.ports.config import AppConfig, InboxConfig
from oatbrain.core.ports.env import Env
from oatbrain.core.commands.ui import SendToTerminal, ProcessFile

@pytest.fixture
def shell_deps():
    bus = EventBus()
    router = CommandRouter()
    filestore = MagicMock(spec=FileStore)
    state_store = MagicMock()
    config = AppConfig(inbox=InboxConfig(folder="Inbox", process_prefix="Process"))
    state = AppState(vault_root=Path("/tmp/vault"))
    env = MagicMock(spec=Env)
    return bus, router, filestore, state_store, config, state, env

def test_slugify(shell_deps):
    bus, router, filestore, state_store, config, state, env = shell_deps
    shell = AdwAppShell(bus, router, state, filestore, state_store, config, env)
    
    assert shell._slugify("Hello World") == "hello-world"
    assert shell._slugify("Testing 123!@#") == "testing-123"
    assert shell._slugify("---Multiple---Dashes---") == "multiple-dashes"

def test_process_command_formatting(shell_deps):
    bus, router, filestore, state_store, config, state, env = shell_deps
    shell = AdwAppShell(bus, router, state, filestore, state_store, config, env)
    
    captured_commands = []
    router.register(SendToTerminal, captured_commands.append)
    
    shell._handle_process_file(ProcessFile(path="Inbox/test.md"))
    
    assert len(captured_commands) == 1
    # Check that it is now quoted
    assert captured_commands[0].text == "Process './Inbox/test.md'"
