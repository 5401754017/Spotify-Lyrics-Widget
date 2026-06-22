# Spotify Widget Taskbar Host Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement方案 A from `docs/superpowers/specs/2026-06-21-spotify-widget-taskbar-host-installer-design.md`: keep the lyrics widget as `Qt.Tool`, add a minimized taskbar host window, and set a stable Windows AppUserModelID.

**Architecture:** Add two focused modules: `src/windows_app_id.py` owns the Windows AppUserModelID call, and `src/taskbar_host.py` owns the minimized host window behavior. Wire both into `src/main.py` so the taskbar entry exists for the app lifetime, the host activates `App.raise_window()`, and closing the host quits the app.

**Tech Stack:** Python 3.12, PyQt6, pytest, pytest-qt, PyInstaller one-folder build.

---

## Scope

This plan implements only方案 A:

- Add minimized `TaskbarHostWindow`.
- Keep `LyricsWidget` window flags unchanged, including `Qt.Tool`.
- Set `SpotifyLyricsWidget.Desktop` as the product AppUserModelID on Windows.
- Add automated tests and manual QA instructions for the taskbar behavior.

This plan does not implement:

- 方案 B small status window host.
- Inno Setup installer.
- Start Menu/Desktop shortcut changes.
- Taskbar pinning.

If方案 A fails manual QA because the host flashes visibly or the taskbar entry is unstable, stop after recording the evidence and open a separate plan for方案 B.

## File Map

- Create `src/windows_app_id.py`: small Windows-only helper for `SetCurrentProcessExplicitAppUserModelID`.
- Create `tests/test_windows_app_id.py`: unit tests for product ID, non-Windows no-op, successful Windows call, and failure logging.
- Create `src/taskbar_host.py`: minimized top-level Qt window used only as taskbar entry.
- Create `tests/test_taskbar_host.py`: pytest-qt tests for host flags, minimized display, activation signal, and close signal.
- Modify `src/main.py`: set AppUserModelID before creating `QApplication`, create and connect taskbar host, show it during startup, hide it on shutdown.
- Modify `tests/test_main.py`: patch the new host in `App` tests and verify wiring/startup/shutdown/main ordering.

## Task 1: Windows AppUserModelID Helper

**Files:**
- Create: `src/windows_app_id.py`
- Create: `tests/test_windows_app_id.py`

- [ ] **Step 1: Write failing tests for the AppUserModelID helper**

Create `tests/test_windows_app_id.py`:

```python
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
```

- [ ] **Step 2: Run the AppUserModelID tests and verify RED**

Run:

```powershell
python -m pytest tests/test_windows_app_id.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.windows_app_id'`.

- [ ] **Step 3: Add the minimal AppUserModelID helper**

Create `src/windows_app_id.py`:

```python
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
```

- [ ] **Step 4: Run the AppUserModelID tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_windows_app_id.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit Task 1**

Run:

```powershell
git status --short
git add src/windows_app_id.py tests/test_windows_app_id.py
git commit -m "feat: add Windows app user model id helper"
```

Expected: commit contains only `src/windows_app_id.py` and `tests/test_windows_app_id.py`.

## Task 2: Minimized Taskbar Host Window

**Files:**
- Create: `src/taskbar_host.py`
- Create: `tests/test_taskbar_host.py`

- [ ] **Step 1: Write failing tests for the taskbar host**

Create `tests/test_taskbar_host.py`:

```python
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QCloseEvent

from src.taskbar_host import TaskbarHostWindow


def test_taskbar_host_is_regular_top_level_window(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)

    flags = host.windowFlags()

    assert not flags & Qt.WindowType.Tool
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
```

- [ ] **Step 2: Run the taskbar host tests and verify RED**

Run:

```powershell
python -m pytest tests/test_taskbar_host.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.taskbar_host'`.

- [ ] **Step 3: Add the minimal taskbar host implementation**

Create `src/taskbar_host.py`:

```python
from PyQt6.QtCore import QEvent, pyqtSignal
from PyQt6.QtWidgets import QWidget

from src.app_icon import build_app_icon


class TaskbarHostWindow(QWidget):
    activated = pyqtSignal()
    close_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spotify Lyrics Widget")
        self.setWindowIcon(build_app_icon())
        self.resize(320, 120)

    def show_taskbar_entry(self):
        self.showMinimized()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange and not self.isMinimized():
            self.activated.emit()
            self.showMinimized()
        super().changeEvent(event)

    def closeEvent(self, event):
        self.close_requested.emit()
        event.accept()
```

- [ ] **Step 4: Run the taskbar host tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_taskbar_host.py -q
```

Expected: `5 passed`.

- [ ] **Step 5: Commit Task 2**

Run:

```powershell
git status --short
git add src/taskbar_host.py tests/test_taskbar_host.py
git commit -m "feat: add minimized taskbar host window"
```

Expected: commit contains only `src/taskbar_host.py` and `tests/test_taskbar_host.py`.

## Task 3: Wire Taskbar Host Into App Lifecycle

**Files:**
- Modify: `src/main.py`
- Modify: `tests/test_main.py`

- [ ] **Step 1: Update `tests/test_main.py` fixtures and add failing lifecycle tests**

Modify `_make_app()` in `tests/test_main.py` to patch `TaskbarHostWindow`:

```python
def _make_app():
    config = MagicMock()
    config.refresh_token = "existing_refresh"
    config.granted_scope = (
        "user-read-currently-playing user-modify-playback-state "
        "user-read-playback-state"
    )
    widget = MagicMock()
    taskbar_host = MagicMock()

    with (
        patch("src.main.Config", return_value=config),
        patch("src.main.LyricsWidget", return_value=widget),
        patch("src.main.TaskbarHostWindow", return_value=taskbar_host),
        patch("src.main.SpotifyWorker", return_value=MagicMock()),
        patch("src.main.LyricsWorker", return_value=MagicMock()),
    ):
        app = App()

    return app, config, widget
```

In every test that constructs `App()` directly with patches, add:

```python
patch("src.main.TaskbarHostWindow", return_value=MagicMock()),
```

Add these tests near the existing lifecycle tests:

```python
def test_app_connects_taskbar_host_to_raise_window_and_quit():
    fake_qapp = MagicMock()
    taskbar_host = MagicMock()

    with (
        patch("src.main.QApplication.instance", return_value=fake_qapp),
        patch("src.main.Config", return_value=MagicMock(refresh_token="refresh")),
        patch("src.main.LyricsWidget", return_value=MagicMock()),
        patch("src.main.TaskbarHostWindow", return_value=taskbar_host),
        patch("src.main.SpotifyWorker", return_value=MagicMock()),
        patch("src.main.LyricsWorker", return_value=MagicMock()),
    ):
        app = App()

    taskbar_host.activated.connect.assert_called_once_with(app.raise_window)
    taskbar_host.close_requested.connect.assert_called_once_with(fake_qapp.quit)


def test_start_shows_taskbar_entry():
    app, config, _ = _make_app()
    config.client_id = "client"
    config.size_preset = "large"
    app._ensure_auth = MagicMock(return_value=True)
    qapp = MagicMock()

    with (
        patch("src.main.QApplication.instance", return_value=qapp),
        patch("src.main.TrayIcon"),
    ):
        app.start()

    app._taskbar_host.show_taskbar_entry.assert_called_once()


def test_shutdown_hides_taskbar_host():
    app, _, widget = _make_app()
    fresh_config = MagicMock()
    widget.pos.return_value.x.return_value = 321
    widget.pos.return_value.y.return_value = 654

    with patch("src.main.Config", return_value=fresh_config):
        app.shutdown()

    app._taskbar_host.hide.assert_called_once()
```

Modify `test_main_configures_logging_before_starting_qapplication()` so it verifies AppUserModelID ordering:

```python
def test_main_configures_logging_and_app_id_before_starting_qapplication():
    events = []

    with (
        patch("src.main.configure_logging", side_effect=lambda: events.append("log")),
        patch(
            "src.main.set_windows_app_user_model_id",
            side_effect=lambda: events.append("appid"),
        ),
        patch(
            "src.main.QApplication",
            side_effect=lambda argv: events.append("qt") or MagicMock(exec=lambda: 0),
        ),
        patch("src.main.build_app_icon"),
        patch("src.main.load_app_font"),
        patch("src.main.App"),
        patch("src.main.SingleInstanceGuard") as guard_class,
        patch("src.main.sys.exit", side_effect=lambda code=0: events.append(("exit", code))),
    ):
        guard_class.return_value.try_claim.return_value = False
        main_module.main()

    assert events[:3] == ["log", "appid", "qt"]
```

- [ ] **Step 2: Run targeted main tests and verify RED**

Run:

```powershell
python -m pytest tests/test_main.py -q
```

Expected: FAIL because `src.main` does not import `TaskbarHostWindow` or `set_windows_app_user_model_id`, and `App` does not create `_taskbar_host`.

- [ ] **Step 3: Wire the taskbar host and AppUserModelID in `src/main.py`**

Add imports near existing app imports:

```python
from src.taskbar_host import TaskbarHostWindow
from src.windows_app_id import set_windows_app_user_model_id
```

In `App.__init__`, create the host before `_connect_lifecycle_signals()`:

```python
self._tray: TrayIcon | None = None
self._taskbar_host = TaskbarHostWindow()
self._last_heartbeat_ts: float = 0.0
```

Replace `_connect_lifecycle_signals()` with:

```python
def _connect_lifecycle_signals(self):
    self._taskbar_host.activated.connect(self.raise_window)
    app = QApplication.instance()
    if app is not None:
        self._widget.close_requested.connect(app.quit)
        self._taskbar_host.close_requested.connect(app.quit)
```

In `App.start()`, after showing the lyrics widget, show the taskbar entry:

```python
self._widget.move(self._config.window_x, self._config.window_y)
self._widget.show()
self._taskbar_host.show_taskbar_entry()
app = QApplication.instance()
```

In `App.shutdown()`, hide the taskbar host before saving config and stopping workers:

```python
logging.info("App.shutdown called -- event loop is exiting")
if self._tray is not None:
    self._tray.hide()
self._taskbar_host.hide()
```

In `main()`, set the AppUserModelID after logging is configured and before `QApplication` is created:

```python
def main():
    configure_logging()
    set_windows_app_user_model_id()
    app = QApplication(sys.argv)
```

- [ ] **Step 4: Run targeted tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_main.py tests/test_taskbar_host.py tests/test_windows_app_id.py -q
```

Expected: all targeted tests pass.

- [ ] **Step 5: Run full automated test suite**

Run:

```powershell
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 3**

Run:

```powershell
git status --short
git add src/main.py tests/test_main.py
git commit -m "feat: keep taskbar entry while widget is hidden"
```

Expected: commit contains only `src/main.py` and `tests/test_main.py`.

## Task 4: Build And Manual QA For方案 A

**Files:**
- No tracked source changes expected.
- Generated ignored files under `build/` and `dist/` may change.

- [ ] **Step 1: Build the PyInstaller one-folder app**

Run:

```powershell
python -m PyInstaller --noconfirm SpotifyLyricsWidget.spec
```

Expected: exit code 0, with fresh `dist/SpotifyLyricsWidget/SpotifyLyricsWidget.exe`.

- [ ] **Step 2: Launch the built app for manual QA**

Run:

```powershell
Start-Process -FilePath "C:\Users\crayo\personal-system\projects\spotify_widget\.worktrees\taskbar-host\dist\SpotifyLyricsWidget\SpotifyLyricsWidget.exe" -WindowStyle Hidden
```

Expected:

- `Spotify Lyrics Widget` appears in the taskbar while the app is running.
- The tray icon still appears.
- The lyrics widget still appears as the floating widget.

- [ ] **Step 3: Verify hide and taskbar behavior manually**

Manual checks:

1. Click the widget hide button.
2. Confirm the lyrics widget disappears.
3. Confirm the taskbar icon remains.
4. Click the taskbar icon.
5. Confirm the lyrics widget returns and is raised.
6. Watch for a blank host window flash. If the flash is obvious or confusing, stop and record that方案 A failed manual QA.
7. Use tray Quit and confirm both tray icon and taskbar entry disappear.

- [ ] **Step 4: Record manual QA outcome in the final implementation handoff**

If方案 A passes, write this in the final handoff:

```text
Manual QA: 方案 A passed on Windows. Taskbar entry stayed visible while widget was hidden; clicking taskbar raised the widget; no obvious blank host flash.
```

If方案 A fails, write the matching evidence line in the final handoff:

```text
Manual QA: 方案 A failed on Windows. Blank host window flashed visibly when clicking taskbar.
Manual QA: 方案 A failed on Windows. Taskbar entry disappeared after widget was hidden.
Manual QA: 方案 A failed on Windows. Clicking taskbar did not raise the widget.
```

- [ ] **Step 5: Verify git status**

Run:

```powershell
git status --short --branch
```

Expected: tracked files are clean. Ignored `build/` and `dist/` may contain generated artifacts and must not be committed.

## Spec Coverage Self-Review

- App running keeps taskbar entry: Task 2 creates the host, Task 3 shows it on startup.
- Lyrics widget keeps `Qt.Tool`: this plan never edits `src/widget.py`.
- Widget hidden but taskbar remains: Task 3 wires the host independently from widget visibility; manual QA verifies it.
- Clicking taskbar raises widget: Task 2 emits `activated`; Task 3 connects it to `App.raise_window()`.
- Tray behavior remains: Task 3 leaves `TrayIcon` wiring unchanged and full suite verifies existing tray tests.
- Stable AppUserModelID: Task 1 adds `SpotifyLyricsWidget.Desktop`; Task 3 calls it before `QApplication`.
-方案 B not implemented: Scope and Task 4 explicitly stop and record evidence if方案 A fails.
- Installer not implemented: Scope excludes installer; keep it for a later plan.
