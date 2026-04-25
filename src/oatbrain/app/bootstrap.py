import logging
import sys
from pathlib import Path
from dataclasses import replace
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio  # noqa: E402

from oatbrain.ui.window import AdwAppShell  # noqa: E402
from oatbrain.core.bus import EventBus, CommandRouter  # noqa: E402
from oatbrain.core.state import AppState  # noqa: E402
from oatbrain.adapters.filestore import LocalFileStore  # noqa: E402
from oatbrain.adapters.state import TomlStateStore  # noqa: E402
from oatbrain.adapters.config import TomlConfigStore  # noqa: E402
from oatbrain.adapters.env import StdlibEnv  # noqa: E402
from oatbrain.adapters.renderer import MarkdownItRenderer  # noqa: E402
from oatbrain.core.wikilink import WikilinkResolver  # noqa: E402
from oatbrain.adapters.watcher import WatchdogFileWatcher  # noqa: E402


def build_app(argv: list[str]) -> Adw.Application:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )
    logger = logging.getLogger("oatbrain.bootstrap")
    logger.debug("Building application...")
    env = StdlibEnv()
    state_path = env.get_xdg_state_home() / "oatbrain" / "state.toml"
    state_store = TomlStateStore(state_path)

    config_path = env.get_xdg_config_home() / "oatbrain" / "config.toml"
    config_store = TomlConfigStore(config_path)
    config = config_store.load()

    try:
        initial_state = state_store.load()
    except Exception:
        # Fallback if no state file exists
        initial_state = AppState(vault_root=Path.cwd())

    # Override vault root if provided via CLI
    if len(argv) > 1:
        provided_path = Path(argv[1]).resolve()
        if provided_path.is_dir():
            initial_state = replace(initial_state, vault_root=provided_path)

    event_bus = EventBus()
    command_router = CommandRouter()
    filestore = LocalFileStore(initial_state.vault_root)
    resolver = WikilinkResolver(filestore)
    renderer = MarkdownItRenderer(filestore, resolver)
    watcher = WatchdogFileWatcher()

    app = AdwAppShell(
        application_id="app.oatbrain.App",
        flags=Gio.ApplicationFlags.FLAGS_NONE | Gio.ApplicationFlags.NON_UNIQUE,
        event_bus=event_bus,
        command_router=command_router,
        initial_state=initial_state,
        filestore=filestore,
        state_store=state_store,
        config=config,
        watcher=watcher,
        renderer=renderer,
        resolver=resolver,
        env=env,
    )
    return app
