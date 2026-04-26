import pytest
import gi
import os
from gi.repository import GLib
from oatbrain.app.bootstrap import build_app

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")


def _run_loop(loop: GLib.MainLoop, iterations: int = 10) -> None:
    for _ in range(iterations):
        GLib.idle_add(loop.quit)
        loop.run()


@pytest.fixture
def app_and_loop(tmp_path):
    # Use a temporary state file to avoid interference from/to local dev state
    os.environ["XDG_STATE_HOME"] = str(tmp_path)

    app, _ = build_app([])
    app.set_application_id(f"org.oatbrain.Test{os.getpid()}")
    app.register()
    app.emit("startup")
    app.activate()

    loop = GLib.MainLoop()
    _run_loop(loop)

    yield app, loop

    for window in app.get_windows():
        window.close()
    app.emit("shutdown")
