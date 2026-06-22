from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent

from src.taskbar_host import TaskbarHostWindow


def test_taskbar_host_is_regular_top_level_window(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)

    flags = host.windowFlags()

    assert (flags & Qt.WindowType.WindowType_Mask) != Qt.WindowType.Tool
    assert host.windowTitle() == "Spotify Lyrics Widget"
    assert host.width() == 320
    assert host.height() == 140


def test_control_window_starts_with_hidden_widget_state(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)

    assert host._status_label.text() == "Widget: Hidden"
    assert host._toggle_button.text() == "Show Widget"
    assert host._quit_button.text() == "Quit"


def test_set_widget_visible_updates_status_and_toggle_button(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)

    host.set_widget_visible(True)

    assert host._status_label.text() == "Widget: Visible"
    assert host._toggle_button.text() == "Hide Widget"

    host.set_widget_visible(False)

    assert host._status_label.text() == "Widget: Hidden"
    assert host._toggle_button.text() == "Show Widget"


def test_toggle_button_emits_toggle_widget_requested(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)

    with qtbot.waitSignal(host.toggle_widget_requested, timeout=1000):
        host._toggle_button.click()


def test_quit_button_emits_quit_requested(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)

    with qtbot.waitSignal(host.quit_requested, timeout=1000):
        host._quit_button.click()


def test_show_taskbar_entry_minimizes_host(qtbot, monkeypatch):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)
    calls = []
    monkeypatch.setattr(host, "showMinimized", lambda: calls.append("minimized"))

    host.show_taskbar_entry()

    assert calls == ["minimized"]


def test_close_event_returns_to_taskbar_without_accepting_close(qtbot, monkeypatch):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)
    calls = []
    monkeypatch.setattr(host, "showMinimized", lambda: calls.append("minimized"))
    event = QCloseEvent()

    host.closeEvent(event)

    assert calls == ["minimized"]
    assert not event.isAccepted()
