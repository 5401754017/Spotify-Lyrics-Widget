import logging

from PyQt6.QtGui import QFontDatabase


FALLBACK_FAMILY = "Microsoft JhengHei UI"

_loaded_family: str | None = None

_logger = logging.getLogger(__name__)


def load_app_font() -> str:
    global _loaded_family
    families = QFontDatabase.families()
    for preferred in ("Microsoft JhengHei UI", "Microsoft JhengHei", "Segoe UI"):
        if preferred in families:
            _loaded_family = preferred
            _logger.info("Using system font: %s", preferred)
            return preferred
    _loaded_family = FALLBACK_FAMILY
    return FALLBACK_FAMILY


def app_font_family() -> str:
    return _loaded_family or FALLBACK_FAMILY
