import ctypes
import logging
import sys


APP_USER_MODEL_ID = "SpotifyLyricsWidget.Desktop"


def set_windows_app_user_model_id(app_id: str = APP_USER_MODEL_ID) -> bool:
    if sys.platform != "win32":
        return False

    try:
        result = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception as exc:
        logging.warning("Failed to set Windows AppUserModelID: %s", exc)
        return False

    if result != 0:
        logging.warning(
            "SetCurrentProcessExplicitAppUserModelID failed: hr=0x%08x",
            result & 0xFFFFFFFF,
        )
        return False

    return True
