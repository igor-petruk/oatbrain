from typing import Any
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw  # noqa: E402

class AdwAppShell(Adw.Application):  # type: ignore[misc]
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.connect('activate', self.on_activate)

    def on_activate(self, app: Adw.Application) -> None:
        win = Adw.ApplicationWindow(application=app)
        win.set_title("Hello World")
        win.set_default_size(800, 600)
        win.present()
