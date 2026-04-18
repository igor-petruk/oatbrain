from unittest.mock import MagicMock
from oatbrain.core.bus import CommandRouter
from oatbrain.core.commands.theme import SetTheme
from oatbrain.core.commands.editor import ToggleMode

def test_command_router_list_commands_includes_palette_variants() -> None:
    router = CommandRouter()
    
    # Register a command with palette variants
    router.register(SetTheme, MagicMock(), "Set Theme")
    # Register a command with single variant
    router.register(ToggleMode, MagicMock(), "Toggle Mode")
    
    commands = router.list_commands()
    
    # Convert to names for easier assertion
    names = [name for _, name in commands]
    
    # Check for SetTheme variants
    assert "Set Theme: Solarized Light" in names
    assert "Set Theme: Monokai Dark" in names
    assert "Set Theme: High Contrast Dark" in names
    
    # Check for ToggleMode variant
    assert "Toggle Read Mode" in names
    
    # Ensure instances are correct
    theme_cmd = next(
        cmd for cmd, name in commands if name == "Set Theme: Solarized Light"
    )
    assert isinstance(theme_cmd, SetTheme)
    assert theme_cmd.theme_id == "solarized-light"
