"""Tests for Editor._reload_if_clean — external file modification handling."""
from pathlib import Path
from unittest.mock import MagicMock

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")

from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.commands.editor import SetDirty, UpdateWordCount  # noqa: E402
from oatbrain.core.ports.filestore import VaultPath  # noqa: E402
from oatbrain.ui.editor import Editor  # noqa: E402

VAULT = Path("/vault")
NOTE_REL = "note.md"
NOTE_ABS = str(VAULT / NOTE_REL)
NOTE_PATH = VaultPath.from_str(NOTE_REL)
INITIAL_CONTENT = "# Hello"
NEW_CONTENT = "# Hello\nNew line"


def _make_editor(vault_root: Path, filestore: MagicMock) -> Editor:
    event_bus = EventBus()
    command_router = CommandRouter()
    command_router.register(UpdateWordCount, lambda _: None, visible=False)
    command_router.register(SetDirty, lambda _: None, visible=False)

    return Editor(
        filestore=filestore,
        event_bus=event_bus,
        command_router=command_router,
        env=MagicMock(),
        vault_root=vault_root,
        vim_enabled=False,
    )


def _load_file(editor: Editor, filestore: MagicMock, content: str) -> None:
    """Simulate opening a file by setting internal state directly."""
    filestore.read_text.return_value = content
    editor._current_path = NOTE_PATH
    editor._loading = True
    editor.buffer.set_text(content)
    editor._current_content = content
    editor._loading = False


def test_reload_updates_buffer_when_clean() -> None:
    filestore = MagicMock()
    editor = _make_editor(VAULT, filestore)
    _load_file(editor, filestore, INITIAL_CONTENT)

    filestore.read_text.return_value = NEW_CONTENT
    editor._reload_if_clean(NOTE_ABS)

    start = editor.buffer.get_start_iter()
    end = editor.buffer.get_end_iter()
    assert editor.buffer.get_text(start, end, True) == NEW_CONTENT
    assert editor._current_content == NEW_CONTENT


def test_reload_skipped_when_buffer_is_dirty() -> None:
    filestore = MagicMock()
    editor = _make_editor(VAULT, filestore)
    _load_file(editor, filestore, INITIAL_CONTENT)

    # Simulate user edits: buffer diverges from _current_content
    editor._loading = True
    editor.buffer.set_text("User edited content")
    editor._loading = False
    # _current_content still holds the last-saved value

    filestore.read_text.return_value = NEW_CONTENT
    editor._reload_if_clean(NOTE_ABS)

    start = editor.buffer.get_start_iter()
    end = editor.buffer.get_end_iter()
    assert editor.buffer.get_text(start, end, True) == "User edited content"


def test_reload_skipped_for_different_file() -> None:
    filestore = MagicMock()
    editor = _make_editor(VAULT, filestore)
    _load_file(editor, filestore, INITIAL_CONTENT)

    filestore.read_text.return_value = NEW_CONTENT
    editor._reload_if_clean("/vault/other.md")

    start = editor.buffer.get_start_iter()
    end = editor.buffer.get_end_iter()
    assert editor.buffer.get_text(start, end, True) == INITIAL_CONTENT


def test_reload_skipped_when_no_file_open() -> None:
    filestore = MagicMock()
    editor = _make_editor(VAULT, filestore)
    # No file opened — _current_path is None

    editor._reload_if_clean(NOTE_ABS)

    filestore.read_text.assert_not_called()


def test_reload_skipped_when_no_vault_root() -> None:
    filestore = MagicMock()
    event_bus = EventBus()
    command_router = CommandRouter()
    command_router.register(UpdateWordCount, lambda _: None, visible=False)
    command_router.register(SetDirty, lambda _: None, visible=False)
    editor = Editor(
        filestore=filestore,
        event_bus=event_bus,
        command_router=command_router,
        env=MagicMock(),
        vault_root=None,
        vim_enabled=False,
    )
    editor._current_path = NOTE_PATH

    editor._reload_if_clean(NOTE_ABS)

    filestore.read_text.assert_not_called()


def test_reload_skipped_when_disk_matches_buffer() -> None:
    """No-op reload when disk content already matches the buffer."""
    filestore = MagicMock()
    editor = _make_editor(VAULT, filestore)
    _load_file(editor, filestore, INITIAL_CONTENT)

    filestore.read_text.return_value = INITIAL_CONTENT
    editor._reload_if_clean(NOTE_ABS)

    start = editor.buffer.get_start_iter()
    end = editor.buffer.get_end_iter()
    assert editor.buffer.get_text(start, end, True) == INITIAL_CONTENT
