import logging
from types import SimpleNamespace

import src.windows_app_id as windows_app_id


class FakeShell32:
    def __init__(self, result=0):
        self.result = result
        self.calls = []

    def SetCurrentProcessExplicitAppUserModelID(self, app_id):
        self.calls.append(app_id)
        return self.result


def test_app_user_model_id_is_product_level():
    assert windows_app_id.APP_USER_MODEL_ID == "SpotifyLyricsWidget.Desktop"


def test_non_windows_skips_shell_call(monkeypatch):
    fake_shell32 = FakeShell32()
    monkeypatch.setattr(windows_app_id.sys, "platform", "linux")
    monkeypatch.setattr(
        windows_app_id.ctypes,
        "windll",
        SimpleNamespace(shell32=fake_shell32),
        raising=False,
    )

    assert windows_app_id.set_windows_app_user_model_id() is False
    assert fake_shell32.calls == []


def test_windows_sets_explicit_app_user_model_id(monkeypatch):
    fake_shell32 = FakeShell32()
    monkeypatch.setattr(windows_app_id.sys, "platform", "win32")
    monkeypatch.setattr(
        windows_app_id.ctypes,
        "windll",
        SimpleNamespace(shell32=fake_shell32),
        raising=False,
    )

    assert windows_app_id.set_windows_app_user_model_id() is True
    assert fake_shell32.calls == ["SpotifyLyricsWidget.Desktop"]


def test_windows_logs_failure_hresult(monkeypatch, caplog):
    fake_shell32 = FakeShell32(result=5)
    monkeypatch.setattr(windows_app_id.sys, "platform", "win32")
    monkeypatch.setattr(
        windows_app_id.ctypes,
        "windll",
        SimpleNamespace(shell32=fake_shell32),
        raising=False,
    )

    caplog.set_level(logging.WARNING)

    assert windows_app_id.set_windows_app_user_model_id() is False
    assert any("AppUserModelID" in record.message for record in caplog.records)
    assert any("0x00000005" in record.message for record in caplog.records)
