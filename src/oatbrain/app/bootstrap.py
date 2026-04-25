import argparse
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


def build_app(argv: list[str]) -> tuple[Adw.Application, list[str]]:
    parser = argparse.ArgumentParser(prog="oatbrain")
    parser.add_argument("vault_path", nargs="?", help="Path to the vault directory")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args, unknown = parser.parse_known_args(argv[1:] if argv else [])

    filtered_argv = ([argv[0]] if argv else ["oatbrain"]) + unknown
    debug_mode = args.debug

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)-5s %(name)s:%(lineno)d | %(message)s",
        stream=sys.stderr,
    )
    logging.getLogger("oatbrain").setLevel(
        logging.DEBUG if debug_mode else logging.INFO
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
    if args.vault_path:
        provided_path = Path(args.vault_path).resolve()
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
    return app, filtered_argv
