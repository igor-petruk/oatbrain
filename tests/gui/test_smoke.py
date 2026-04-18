import logging
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw  # noqa: E402
from oatbrain.app.bootstrap import build_app  # noqa: E402

logger = logging.getLogger(__name__)

def test_app_instantiation():
    """Verify that the application object can be built successfully."""
    logger.info("Starting app instantiation test")
    app = build_app([])
    assert isinstance(app, Adw.Application)
    logger.info("Application instantiation successful")
