from pathlib import Path

from PyQt6.QtGui import QFontDatabase


_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_FONT_FILES = ("NotoSansTC-VF.ttf",)
FALLBACK_FAMILY = "Segoe UI"

_loaded_family: str | None = None


def load_app_font() -> str:
    global _loaded_family
    family = FALLBACK_FAMILY
    for file_name in _FONT_FILES:
        font_id = QFontDatabase.addApplicationFont(str(_FONT_DIR / file_name))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            family = families[0]
    _loaded_family = family
    return family


def app_font_family() -> str:
    return _loaded_family or FALLBACK_FAMILY
