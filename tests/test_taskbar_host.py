from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QCloseEvent

from src.taskbar_host import TaskbarHostWindow


def test_taskbar_host_is_regular_top_level_window(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)

    flags = host.windowFlags()

    assert (flags & Qt.WindowType.WindowType_Mask) != Qt.WindowType.Tool
    assert host.windowTitle() == "Spotify Lyrics Widget"
    assert host.width() == 320
    assert host.height() == 120


def test_show_taskbar_entry_minimizes_host(qtbot, monkeypatch):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)
    calls = []
    monkeypatch.setattr(host, "showMinimized", lambda: calls.append("minimized"))

    host.show_taskbar_entry()

    assert calls == ["minimized"]


def test_restoring_host_emits_activated_and_minimizes_again(qtbot, monkeypatch):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)
    calls = []
    monkeypatch.setattr(host, "isMinimized", lambda: False)
    monkeypatch.setattr(host, "showMinimized", lambda: calls.append("minimized"))

    with qtbot.waitSignal(host.activated, timeout=1000):
        host.changeEvent(QEvent(QEvent.Type.WindowStateChange))

    assert calls == ["minimized"]


def test_minimized_state_change_does_not_emit_activated(qtbot, monkeypatch):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)
    signals = []
    host.activated.connect(lambda: signals.append("activated"))
    monkeypatch.setattr(host, "isMinimized", lambda: True)

    host.changeEvent(QEvent(QEvent.Type.WindowStateChange))

    assert signals == []


def test_close_event_emits_close_requested(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)
    event = QCloseEvent()

    with qtbot.waitSignal(host.close_requested, timeout=1000):
        host.closeEvent(event)

    assert event.isAccepted()
