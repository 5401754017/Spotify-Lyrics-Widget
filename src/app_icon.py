import sys
from pathlib import Path

from PyQt6.QtGui import QIcon


APP_ICON_RELATIVE_PATH = Path("assets") / "app-icon.ico"


def app_icon_path() -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base_path / APP_ICON_RELATIVE_PATH


def build_app_icon() -> QIcon:
    return QIcon(str(app_icon_path()))
