import pytest
from unittest.mock import MagicMock
from oatbrain.ui.editor import Editor
from oatbrain.core.bus import EventBus, CommandRouter
from oatbrain.core.ports.env import Env
from oatbrain.core.events.ui import TabTitleChanged

@pytest.fixture
def bus():
    return EventBus()

@pytest.fixture
def router():
    return CommandRouter()

@pytest.fixture
def env():
    return MagicMock(spec=Env)

def test_heading_extraction(bus, router, env):
    editor = Editor(
        filestore=MagicMock(),
        event_bus=bus,
        command_router=router,
        env=env,
        vim_enabled=False
    )
    
    text = "# My Title\nSome content"
    assert editor._extract_heading(text) == "My Title"
    
    text = "No heading here"
    assert editor._extract_heading(text) is None
    
    text = "  # Spaced heading"
    assert editor._extract_heading(text) == "Spaced heading"

def test_title_update_event(bus, router, env):
    editor = Editor(
        filestore=MagicMock(),
        event_bus=bus,
        command_router=router,
        env=env,
        vim_enabled=False,
        tab_id="test-tab"
    )
    
    captured_events = []
    bus.subscribe(TabTitleChanged, captured_events.append)
    
    # Simulate buffer change with heading
    editor.buffer.set_text("# Hello World")
    editor._update_stats()
    
    assert len(captured_events) == 1
    assert captured_events[0].tab_id == "test-tab"
    assert captured_events[0].title == "Hello World"
