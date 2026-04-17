import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gio  # noqa: E402
from oatbrain.ui.window import AdwAppShell  # noqa: E402

def build_app(argv: list[str]) -> Adw.Application:
    app = AdwAppShell(
        application_id="app.oatbar.Oatbrain", flags=Gio.ApplicationFlags.FLAGS_NONE
    )
    return app
