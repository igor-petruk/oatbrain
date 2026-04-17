import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk  # noqa: E402
from oatbrain.ui.headerbar import HeaderBar  # noqa: E402
from oatbrain.ui.statusbar import StatusBar  # noqa: E402
from oatbrain.core.bus import EventBus  # noqa: E402

def test_headerbar_instantiation():
    event_bus = EventBus()
    header = HeaderBar(event_bus)
    assert isinstance(header.widget, Adw.HeaderBar)

def test_statusbar_instantiation():
    event_bus = EventBus()
    status = StatusBar(event_bus)
    assert isinstance(status.widget, Gtk.Box)
