import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_DIR_NAME = "spotify-lyrics-widget"
LOG_FILE_NAME = "widget.log"
MAX_LOG_BYTES = 1_000_000
BACKUP_COUNT = 3


def configure_logging() -> Path:
    """Configure file logging before the app hides its console."""
    appdata = os.environ.get("APPDATA", str(Path.home()))
    log_dir = Path(appdata) / LOG_DIR_NAME
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / LOG_FILE_NAME

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    for handler in list(root_logger.handlers):
        if getattr(handler, "_spotify_widget_handler", False):
            root_logger.removeHandler(handler)
            handler.close()

    handler = RotatingFileHandler(
        log_path,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler._spotify_widget_handler = True
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root_logger.addHandler(handler)
    return log_path
