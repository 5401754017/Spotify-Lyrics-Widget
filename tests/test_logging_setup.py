import importlib
import logging
from logging.handlers import RotatingFileHandler


def test_configure_logging_writes_rotating_file_under_appdata(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    module = importlib.import_module("src.logging_setup")

    log_path = module.configure_logging()

    assert log_path == tmp_path / "spotify-lyrics-widget" / "widget.log"
    handlers = [
        handler
        for handler in logging.getLogger().handlers
        if isinstance(handler, RotatingFileHandler)
    ]
    assert handlers
    assert handlers[-1].baseFilename == str(log_path)
    assert handlers[-1].maxBytes == 1_000_000
    assert handlers[-1].backupCount == 3


def test_log_file_path_under_appdata(monkeypatch, tmp_path):
    from src.logging_setup import log_file_path

    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert log_file_path() == tmp_path / "spotify-lyrics-widget" / "widget.log"
