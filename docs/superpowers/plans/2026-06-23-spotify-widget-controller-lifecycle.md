# Spotify Widget Controller Lifecycle Implementation Plan

> 狀態：current canonical plan for controller lifecycle。產品發布頁文案仍以 `docs/product-release.md` 為準。

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 taskbar 控制窗改成 controller 常駐模型：controller 控制 widget Run/Close 與 Show/Hide，tray icon 綁定 widget running 狀態。

**Architecture:** `TaskbarHostWindow` 是 Windows taskbar 入口與 controller UI。`App` 管理 widget session 的生命週期，widget session 包含 `LyricsWidget`、`SpotifyWorker`、`LyricsWorker`、`TrayIcon`。Controller 可以在 widget stopped 時繼續存在；widget close / tray close / controller Close Widget 只停止 widget session，controller X 才關閉 controller/taskbar entry。

**Tech Stack:** Python 3.12、PyQt6、pytest、pytest-qt、PyInstaller one-folder build。

---

## 目前狀態

- Branch：`codex/taskbar-host`
- Worktree：`C:\Users\crayo\personal-system\projects\spotify_widget\.worktrees\taskbar-host`
- 已實作但需要重設計的 commit：`e838c34 feat: wire taskbar control window`
- 舊版控制窗問題：`Quit`、widget close、tray menu Quit 的語意混在一起，手動 QA 發現 tray/taskbar/process 沒有照預期消失。
- Canonical spec：`docs/superpowers/specs/2026-06-21-spotify-widget-taskbar-host-installer-design.md`
- 舊 plan 已標成取代：`docs/superpowers/plans/2026-06-22-spotify-widget-taskbar-control-window.md`

## State Model

```text
Stopped:
Widget: Stopped
Widget: Hidden
[Widget Disabled] disabled    [Run Widget]
tray hidden

Running + Visible:
Widget: Running
Widget: Visible
[Hide Widget]                 [Close Widget]
tray visible

Running + Hidden:
Widget: Running
Widget: Hidden
[Show Widget]                 [Close Widget]
tray visible
```

控制入口：

- Run Widget：只由 controller 執行。
- Show/Hide Widget：controller left button、widget hide button、tray icon click。
- Close Widget：controller right button、widget close、tray menu `Close Widget`。
- Close Controller：controller 視窗 X；先 close widget，再關閉 controller/taskbar entry。

## 檔案分工

- 修改 `src/taskbar_host.py`：controller UI、狀態同步、button signal、controller close signal。
- 修改 `tests/test_taskbar_host.py`：controller UI state、button emit、close event。
- 修改 `src/tray.py`：tray menu 文字改為 `Close Widget`，callback 名稱改成 widget close 語意。
- 修改 `tests/test_tray.py`：若存在，更新 tray menu callback 測試；若不存在，在 `tests/test_main.py` 驗證 `TrayIcon` wiring。
- 修改 `src/main.py`：把 widget session 從 controller lifecycle 分離，新增 run/show/hide/close/controller-close 方法。
- 修改 `tests/test_main.py`：用 TDD 覆蓋 controller start、run widget、hide/show、close widget、controller X、shutdown。

## 任務 1：更新 TaskbarHostWindow UI 狀態模型

**檔案：**
- 修改：`tests/test_taskbar_host.py`
- 修改：`src/taskbar_host.py`

- [ ] **步驟 1：先改 controller UI tests**

把 `tests/test_taskbar_host.py` 改成覆蓋以下測試：

```python
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent

from src.taskbar_host import TaskbarHostWindow


def test_taskbar_host_is_regular_top_level_window(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)

    flags = host.windowFlags()

    assert (flags & Qt.WindowType.WindowType_Mask) != Qt.WindowType.Tool
    assert host.windowTitle() == "Spotify Lyrics Widget"
    assert host.width() == 360
    assert host.height() == 150


def test_control_window_starts_stopped_and_hidden(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)

    assert host._running_label.text() == "Widget: Stopped"
    assert host._visibility_label.text() == "Widget: Hidden"
    assert host._visibility_button.text() == "Widget Disabled"
    assert host._visibility_button.isEnabled() is False
    assert host._run_close_button.text() == "Run Widget"


def test_running_visible_state_updates_labels_and_buttons(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)

    host.set_widget_state(is_running=True, is_visible=True)

    assert host._running_label.text() == "Widget: Running"
    assert host._visibility_label.text() == "Widget: Visible"
    assert host._visibility_button.text() == "Hide Widget"
    assert host._visibility_button.isEnabled() is True
    assert host._run_close_button.text() == "Close Widget"


def test_running_hidden_state_updates_labels_and_buttons(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)

    host.set_widget_state(is_running=True, is_visible=False)

    assert host._running_label.text() == "Widget: Running"
    assert host._visibility_label.text() == "Widget: Hidden"
    assert host._visibility_button.text() == "Show Widget"
    assert host._visibility_button.isEnabled() is True
    assert host._run_close_button.text() == "Close Widget"


def test_visibility_button_emits_hide_when_visible(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)
    host.set_widget_state(is_running=True, is_visible=True)

    with qtbot.waitSignal(host.hide_widget_requested, timeout=1000):
        host._visibility_button.click()


def test_visibility_button_emits_show_when_hidden(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)
    host.set_widget_state(is_running=True, is_visible=False)

    with qtbot.waitSignal(host.show_widget_requested, timeout=1000):
        host._visibility_button.click()


def test_run_close_button_emits_run_when_stopped(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)

    with qtbot.waitSignal(host.run_widget_requested, timeout=1000):
        host._run_close_button.click()


def test_run_close_button_emits_close_when_running(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)
    host.set_widget_state(is_running=True, is_visible=True)

    with qtbot.waitSignal(host.close_widget_requested, timeout=1000):
        host._run_close_button.click()


def test_show_taskbar_entry_minimizes_host(qtbot, monkeypatch):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)
    calls = []
    monkeypatch.setattr(host, "showMinimized", lambda: calls.append("minimized"))

    host.show_taskbar_entry()

    assert calls == ["minimized"]


def test_close_event_emits_controller_close_and_accepts(qtbot):
    host = TaskbarHostWindow()
    qtbot.addWidget(host)
    event = QCloseEvent()

    with qtbot.waitSignal(host.controller_close_requested, timeout=1000):
        host.closeEvent(event)

    assert event.isAccepted()
```

- [ ] **步驟 2：跑 taskbar host 測試確認 RED**

Run:

```powershell
python -m pytest tests/test_taskbar_host.py -q
```

Expected: FAIL，因為 `set_widget_state()`、新 labels、新 buttons、new signals 尚未存在。

- [ ] **步驟 3：實作 `TaskbarHostWindow`**

把 `src/taskbar_host.py` 改成以下 controller UI：

```python
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.app_icon import build_app_icon


class TaskbarHostWindow(QWidget):
    show_widget_requested = pyqtSignal()
    hide_widget_requested = pyqtSignal()
    run_widget_requested = pyqtSignal()
    close_widget_requested = pyqtSignal()
    controller_close_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._is_running = False
        self._is_visible = False

        self.setWindowTitle("Spotify Lyrics Widget")
        self.setWindowIcon(build_app_icon())
        self.resize(360, 150)

        self._title_label = QLabel("Spotify Lyrics Widget")
        self._running_label = QLabel()
        self._visibility_label = QLabel()
        self._visibility_button = QPushButton()
        self._run_close_button = QPushButton()

        button_layout = QHBoxLayout()
        button_layout.addWidget(self._visibility_button)
        button_layout.addWidget(self._run_close_button)

        layout = QVBoxLayout()
        layout.addWidget(self._title_label)
        layout.addWidget(self._running_label)
        layout.addWidget(self._visibility_label)
        layout.addLayout(button_layout)
        self.setLayout(layout)

        self._visibility_button.clicked.connect(self._emit_visibility_request)
        self._run_close_button.clicked.connect(self._emit_run_close_request)
        self.set_widget_state(is_running=False, is_visible=False)

    def set_widget_state(self, is_running: bool, is_visible: bool):
        self._is_running = is_running
        self._is_visible = is_visible if is_running else False
        self._running_label.setText(
            "Widget: Running" if self._is_running else "Widget: Stopped"
        )
        self._visibility_label.setText(
            "Widget: Visible" if self._is_visible else "Widget: Hidden"
        )

        if not self._is_running:
            self._visibility_button.setText("Widget Disabled")
            self._visibility_button.setEnabled(False)
            self._run_close_button.setText("Run Widget")
            return

        self._visibility_button.setEnabled(True)
        self._visibility_button.setText(
            "Hide Widget" if self._is_visible else "Show Widget"
        )
        self._run_close_button.setText("Close Widget")

    def _emit_visibility_request(self):
        if not self._is_running:
            return
        if self._is_visible:
            self.hide_widget_requested.emit()
        else:
            self.show_widget_requested.emit()

    def _emit_run_close_request(self):
        if self._is_running:
            self.close_widget_requested.emit()
        else:
            self.run_widget_requested.emit()

    def show_taskbar_entry(self):
        self.showMinimized()

    def closeEvent(self, event):
        self.controller_close_requested.emit()
        event.accept()
```

- [ ] **步驟 4：跑 taskbar host 測試確認 GREEN**

Run:

```powershell
python -m pytest tests/test_taskbar_host.py -q
```

Expected: `10 passed`。

- [ ] **步驟 5：Commit 任務 1**

Run:

```powershell
git status --short
git add src/taskbar_host.py tests/test_taskbar_host.py
git commit -m "feat: add widget controller state UI"
```

Expected: commit 只包含 `src/taskbar_host.py` 與 `tests/test_taskbar_host.py`。

## 任務 2：讓 tray icon 綁定 widget lifecycle

**檔案：**
- 修改：`src/tray.py`
- 修改：`tests/test_main.py`

- [ ] **步驟 1：先更新 tray wiring expectations**

在 `tests/test_main.py` 裡，後續 `_run_widget()` 測試要驗證 `TrayIcon` 以 widget close 語意建立：

```python
def test_run_widget_creates_tray_bound_to_widget_lifecycle():
    app, config = _make_controller_only_app()
    config.client_id = "client"
    app._ensure_auth = MagicMock(return_value=True)
    qapp = MagicMock()

    with (
        patch("src.main.QApplication.instance", return_value=qapp),
        patch("src.main.TrayIcon") as tray_class,
    ):
        app._run_widget()

    tray_class.assert_called_once_with(
        on_toggle=app._toggle_widget,
        on_close_widget=app._close_widget,
    )
    tray_class.return_value.show.assert_called_once()
```

- [ ] **步驟 2：修改 `src/tray.py` menu 文字與 callback 名稱**

把 `TrayIcon` constructor 改成：

```python
class TrayIcon:
    def __init__(
        self,
        on_toggle,
        on_close_widget,
        parent=None,
    ):
        self._on_toggle = on_toggle
        self._tray = QSystemTrayIcon(build_tray_icon(), parent)
        self._tray.setToolTip("Spotify Lyrics Widget")

        self._menu = QMenu()
        self._menu.addAction("Open / Hide").triggered.connect(on_toggle)
        self._menu.addAction("Close Widget").triggered.connect(on_close_widget)
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_tray_activated)
```

- [ ] **步驟 3：Commit 任務 2**

Run:

```powershell
python -m pytest tests/test_main.py -q
git status --short
git add src/tray.py tests/test_main.py
git commit -m "feat: bind tray actions to widget lifecycle"
```

Expected: targeted tests pass，commit 只包含 tray lifecycle wiring 相關變更。

## 任務 3：把 App 改成 controller-managed widget session

**檔案：**
- 修改：`tests/test_main.py`
- 修改：`src/main.py`

- [ ] **步驟 1：建立 controller-only test helper**

在 `tests/test_main.py` 新增 helper，讓 tests 不再假設 `App.__init__()` 會建立 widget：

```python
def _make_controller_only_app():
    config = MagicMock()
    config.refresh_token = "existing_refresh"
    config.granted_scope = (
        "user-read-currently-playing user-modify-playback-state "
        "user-read-playback-state"
    )
    config.size_preset = "large"
    config.config_dir = "config-dir"
    taskbar_host = MagicMock()

    with (
        patch("src.main.Config", return_value=config),
        patch("src.main.TaskbarHostWindow", return_value=taskbar_host),
    ):
        app = App()

    return app, config
```

- [ ] **步驟 2：先寫 controller start 的 failing tests**

新增：

```python
def test_start_only_shows_controller_taskbar_entry():
    app, config = _make_controller_only_app()
    config.client_id = "client"

    app.start()

    app._taskbar_host.set_widget_state.assert_called_once_with(
        is_running=False,
        is_visible=False,
    )
    app._taskbar_host.show_taskbar_entry.assert_called_once()
    assert app._widget is None
    assert app._tray is None
    assert app._spotify_worker is None
    assert app._lyrics_worker is None
```

Run:

```powershell
python -m pytest tests/test_main.py::test_start_only_shows_controller_taskbar_entry -q
```

Expected: FAIL，因為目前 `App.__init__()` 仍會建立 widget/worker，`start()` 也會直接 show widget。

- [ ] **步驟 3：先寫 Run Widget 的 failing tests**

新增：

```python
def test_run_widget_creates_widget_session_and_marks_running_visible():
    app, config = _make_controller_only_app()
    config.client_id = "client"
    app._ensure_auth = MagicMock(return_value=True)
    widget = MagicMock()
    spotify_worker = MagicMock()
    lyrics_worker = MagicMock()

    with (
        patch("src.main.LyricsWidget", return_value=widget),
        patch("src.main.SpotifyWorker", return_value=spotify_worker),
        patch("src.main.LyricsWorker", return_value=lyrics_worker),
        patch("src.main.TrayIcon") as tray_class,
    ):
        app._run_widget()

    widget.apply_size_preset.assert_called_once_with("large")
    widget.show.assert_called_once()
    tray_class.return_value.show.assert_called_once()
    spotify_worker.start.assert_called_once()
    app._taskbar_host.set_widget_state.assert_called_with(
        is_running=True,
        is_visible=True,
    )


def test_run_widget_cancelled_auth_keeps_widget_stopped():
    app, config = _make_controller_only_app()
    config.client_id = "client"
    app._ensure_auth = MagicMock(return_value=False)

    app._run_widget()

    assert app._widget is None
    app._taskbar_host.set_widget_state.assert_called_with(
        is_running=False,
        is_visible=False,
    )
```

Run:

```powershell
python -m pytest tests/test_main.py::test_run_widget_creates_widget_session_and_marks_running_visible tests/test_main.py::test_run_widget_cancelled_auth_keeps_widget_stopped -q
```

Expected: FAIL，因為 `_run_widget()` 尚未存在。

- [ ] **步驟 4：先寫 Show/Hide/Close Widget 的 failing tests**

新增：

```python
def test_hide_widget_only_hides_running_widget_and_keeps_tray():
    app, _ = _make_controller_only_app()
    widget = MagicMock()
    app._widget = widget

    app._hide_widget()

    widget.hide.assert_called_once()
    app._taskbar_host.set_widget_state.assert_called_with(
        is_running=True,
        is_visible=False,
    )


def test_show_widget_raises_running_widget():
    app, _ = _make_controller_only_app()
    widget = MagicMock()
    app._widget = widget

    app._show_widget()

    widget.showNormal.assert_called_once()
    widget.raise_.assert_called_once()
    widget.activateWindow.assert_called_once()
    app._taskbar_host.set_widget_state.assert_called_with(
        is_running=True,
        is_visible=True,
    )


def test_close_widget_stops_workers_hides_tray_and_keeps_controller():
    app, config = _make_controller_only_app()
    widget = MagicMock()
    spotify_worker = MagicMock()
    lyrics_worker = MagicMock()
    lyrics_worker.isRunning.return_value = True
    tray = MagicMock()
    fresh_config = MagicMock()
    widget.pos.return_value.x.return_value = 321
    widget.pos.return_value.y.return_value = 654
    app._widget = widget
    app._spotify_worker = spotify_worker
    app._lyrics_worker = lyrics_worker
    app._tray = tray

    with patch("src.main.Config", return_value=fresh_config):
        app._close_widget()

    tray.hide.assert_called_once()
    widget.hide.assert_called_once()
    spotify_worker.stop.assert_called_once()
    spotify_worker.wait.assert_called_once_with(2000)
    lyrics_worker.wait.assert_called_once_with(6000)
    assert fresh_config.window_x == 321
    assert fresh_config.window_y == 654
    fresh_config.save.assert_called_once()
    app._taskbar_host.hide.assert_not_called()
    app._taskbar_host.set_widget_state.assert_called_with(
        is_running=False,
        is_visible=False,
    )
```

Run:

```powershell
python -m pytest tests/test_main.py::test_hide_widget_only_hides_running_widget_and_keeps_tray tests/test_main.py::test_show_widget_raises_running_widget tests/test_main.py::test_close_widget_stops_workers_hides_tray_and_keeps_controller -q
```

Expected: FAIL，因為 `_hide_widget()`、`_show_widget()`、`_close_widget()` 尚未符合新語意。

- [ ] **步驟 5：先寫 controller close 的 failing test**

新增：

```python
def test_close_controller_closes_widget_and_quits_qapplication():
    app, _ = _make_controller_only_app()
    app._close_widget = MagicMock()
    fake_qapp = MagicMock()

    with patch("src.main.QApplication.instance", return_value=fake_qapp):
        app._close_controller()

    app._close_widget.assert_called_once()
    app._taskbar_host.hide.assert_called_once()
    fake_qapp.quit.assert_called_once()
```

Run:

```powershell
python -m pytest tests/test_main.py::test_close_controller_closes_widget_and_quits_qapplication -q
```

Expected: FAIL，因為 `_close_controller()` 尚未存在。

- [ ] **步驟 6：重構 `App.__init__()` 與 controller signal wiring**

把 `App.__init__()` 的 widget/worker 建立移到 `_create_widget_session()`，初始化只保留 controller：

```python
class App(QObject):
    """Main application controller for the widget and taskbar controller."""

    def __init__(self):
        super().__init__()
        self._config = Config()
        self._widget: LyricsWidget | None = None
        self._spotify_worker: SpotifyWorker | None = None
        self._lyrics_worker: LyricsWorker | None = None
        self._current_track_id: str | None = None
        self._tray: TrayIcon | None = None
        self._taskbar_host = TaskbarHostWindow()
        self._last_heartbeat_ts: float = 0.0
        self._is_playing = False
        self._connect_controller_signals()
        self._sync_controller_state()

    def _connect_controller_signals(self):
        self._taskbar_host.show_widget_requested.connect(self._show_widget)
        self._taskbar_host.hide_widget_requested.connect(self._hide_widget)
        self._taskbar_host.run_widget_requested.connect(self._run_widget)
        self._taskbar_host.close_widget_requested.connect(self._close_widget)
        self._taskbar_host.controller_close_requested.connect(self._close_controller)
```

- [ ] **步驟 7：重構 `App.start()`**

把 `start()` 改成只啟動 controller/taskbar entry：

```python
def start(self):
    self._sync_controller_state()
    self._taskbar_host.show_taskbar_entry()
```

- [ ] **步驟 8：新增 client/auth 與 widget session 建立方法**

新增：

```python
def _ensure_client_configured(self) -> bool:
    if self._config.client_id:
        return True

    dialog = SpotifyOnboardingDialog(REDIRECT_URI)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False
    self._config.client_id = dialog.client_id
    self._config.save()
    return True

def _create_widget_session(self):
    self._widget = LyricsWidget()
    self._spotify_worker = SpotifyWorker(self._config)
    self._lyrics_worker = LyricsWorker(netease_fallback=self._config.netease_fallback)
    self._current_track_id = None
    self._is_playing = False
    self._widget.apply_size_preset(self._config.size_preset)
    self._connect_widget_session_signals()

def _connect_widget_session_signals(self):
    if (
        self._widget is None
        or self._spotify_worker is None
        or self._lyrics_worker is None
    ):
        raise RuntimeError("Widget session is not initialized")

    self._spotify_worker.track_changed.connect(self._on_track_changed)
    self._spotify_worker.state_synced.connect(self._on_state_synced)
    self._spotify_worker.playback_toggled.connect(self._on_playback_toggled)
    self._spotify_worker.not_a_track.connect(self._on_not_a_track)
    self._spotify_worker.not_playing.connect(self._on_not_playing)
    self._spotify_worker.auth_expired.connect(self._on_auth_expired)
    self._spotify_worker.network_error.connect(self._widget.show_offline)
    self._spotify_worker.network_recovered.connect(self._widget.hide_offline)
    self._spotify_worker.rate_limited.connect(self._widget.show_rate_limited)
    self._widget.hide_requested.connect(self._toggle_widget)
    self._widget.close_requested.connect(self._close_widget)
    self._widget.size_preset_requested.connect(self._on_size_preset_changed)

    self._lyrics_worker.lyrics_ready.connect(self._on_lyrics_ready)
    self._lyrics_worker.no_lyrics.connect(self._on_no_lyrics)
    self._lyrics_worker.lyrics_unavailable.connect(self._on_lyrics_unavailable)
```

- [ ] **步驟 9：新增 Run/Show/Hide/Close lifecycle methods**

新增：

```python
def _sync_controller_state(self):
    is_running = self._widget is not None
    is_visible = bool(is_running and self._widget.isVisible())
    self._taskbar_host.set_widget_state(
        is_running=is_running,
        is_visible=is_visible,
    )

def _run_widget(self):
    if self._widget is not None:
        self._show_widget()
        return
    if not self._ensure_client_configured():
        self._sync_controller_state()
        return
    if not self._ensure_auth():
        self._sync_controller_state()
        return

    self._create_widget_session()
    self._widget.move(self._config.window_x, self._config.window_y)
    self._widget.show()
    self._tray = TrayIcon(
        on_toggle=self._toggle_widget,
        on_close_widget=self._close_widget,
    )
    self._tray.show()
    self._spotify_worker.start()
    self._sync_controller_state()

def _show_widget(self):
    if self._widget is None:
        return
    self._widget.showNormal()
    self._widget.raise_()
    self._widget.activateWindow()
    self._sync_controller_state()

def _hide_widget(self):
    if self._widget is None:
        return
    self._widget.hide()
    self._sync_controller_state()

def _toggle_widget(self):
    if self._widget is None:
        return
    if self._widget.isVisible():
        self._hide_widget()
    else:
        self._show_widget()

def _save_widget_position(self, widget):
    position = widget.pos()
    config = Config(config_dir=self._config.config_dir)
    config.window_x = position.x()
    config.window_y = position.y()
    config.size_preset = self._config.size_preset
    config.save()

def _close_widget(self):
    widget = self._widget
    spotify_worker = self._spotify_worker
    lyrics_worker = self._lyrics_worker
    tray = self._tray

    self._widget = None
    self._spotify_worker = None
    self._lyrics_worker = None
    self._tray = None
    self._current_track_id = None
    self._is_playing = False

    if tray is not None:
        tray.hide()
    if widget is not None:
        self._save_widget_position(widget)
        widget.hide()
        widget.deleteLater()
    if spotify_worker is not None:
        spotify_worker.stop()
        spotify_worker.wait(2000)
    if lyrics_worker is not None and lyrics_worker.isRunning():
        lyrics_worker.wait(6000)
    self._sync_controller_state()

def _close_controller(self):
    self._close_widget()
    self._taskbar_host.hide()
    app = QApplication.instance()
    if app is not None:
        app.quit()
```

- [ ] **步驟 10：更新 worker slots 的 stopped guards**

在需要 widget/worker 存在的 slots 開頭加 guard：

```python
if self._widget is None:
    return
```

需要 guard 的 methods：

- `_on_track_changed`
- `_on_state_synced`
- `_on_playback_toggled`
- `_on_not_a_track`
- `_on_not_playing`
- `_on_auth_expired`
- `_on_size_preset_changed`
- `_on_lyrics_ready`
- `_on_no_lyrics`
- `_on_lyrics_unavailable`

`_on_auth_expired()` 重新建立 worker 時，要在 `self._spotify_worker is not None` 時才 stop/wait。

- [ ] **步驟 11：更新 shutdown 與 single-instance activation**

把 `shutdown()` 改成 idempotent：

```python
def shutdown(self):
    logging.info("App.shutdown called - event loop is exiting")
    self._close_widget()
    self._taskbar_host.hide()
```

新增 controller raise method：

```python
def show_controller(self):
    self._taskbar_host.showNormal()
    self._taskbar_host.raise_()
    self._taskbar_host.activateWindow()
```

把 `main()` 裡 single instance guard 改成：

```python
guard = SingleInstanceGuard(on_activate=controller.show_controller)
```

- [ ] **步驟 12：跑 main tests 確認 GREEN**

Run:

```powershell
python -m pytest tests/test_main.py -q
```

Expected: all `tests/test_main.py` tests pass。

- [ ] **步驟 13：Commit 任務 3**

Run:

```powershell
git status --short
git add src/main.py tests/test_main.py
git commit -m "feat: manage widget lifecycle from controller"
```

Expected: commit 只包含 `src/main.py` 與 `tests/test_main.py`。

## 任務 4：完整驗證與 Windows 手動 QA

**檔案：**
- 預期沒有 tracked source changes。
- `build/` 與 `dist/` 是 generated artifacts，不 commit。

- [ ] **步驟 1：跑完整自動測試**

Run:

```powershell
python -m pytest -q
```

Expected: all tests pass。

- [ ] **步驟 2：建 PyInstaller one-folder app**

Run:

```powershell
python -m PyInstaller --noconfirm SpotifyLyricsWidget.spec
```

Expected: exit code 0，產生 `dist/SpotifyLyricsWidget/SpotifyLyricsWidget.exe`。

- [ ] **步驟 3：啟動 worktree build 做手動 QA**

先確認沒有舊 process：

```powershell
Get-Process SpotifyLyricsWidget -ErrorAction SilentlyContinue | Select-Object Id,Path
```

沒有舊 process 時啟動：

```powershell
Start-Process -FilePath "C:\Users\crayo\personal-system\projects\spotify_widget\.worktrees\taskbar-host\dist\SpotifyLyricsWidget\SpotifyLyricsWidget.exe" -WindowStyle Hidden
```

手動檢查：

1. Taskbar 出現 `Spotify Lyrics Widget`，tray icon 不出現。
2. 點 taskbar，controller 顯示 `Widget: Stopped`、`Widget: Hidden`、disabled `Widget Disabled`、`Run Widget`。
3. 按 `Run Widget`，widget 顯示，tray icon 出現，controller 變成 Running + Visible。
4. 按 `Hide Widget`，widget 隱藏，tray icon 保留，controller 變成 Running + Hidden。
5. 按 `Show Widget`，widget 顯示並 raise，controller 變成 Running + Visible。
6. 點 tray icon，widget Hidden/Visible 來回切換，controller 狀態同步。
7. 按 widget 的 hide 按鈕，widget 隱藏，controller 狀態同步。
8. 按 controller `Close Widget`，widget/tray 關閉，controller/taskbar 保留，狀態回 Stopped + Hidden。
9. 再按 `Run Widget`，widget/tray 可重新啟動。
10. 按 widget close，widget/tray 關閉，controller/taskbar 保留。
11. 按 tray menu `Close Widget`，widget/tray 關閉，controller/taskbar 保留。
12. Widget Running 時按 controller X，widget/tray 關閉，controller/taskbar 消失。
13. Widget Stopped 時按 controller X，controller/taskbar 消失。

- [ ] **步驟 4：確認 git status**

Run:

```powershell
git status --short --branch
```

Expected: tracked files 乾淨；只有 ignored build artifacts 可以存在。

## 完成條件

- Spec 與本 plan 都使用 controller/widget/tray/taskbar 語意，不再使用模糊的「關閉整個程式」說法。
- `Widget Disabled` 是 disabled button 的實際文字，不是灰掉的 `Show Widget`。
- Widget close、tray `Close Widget`、controller `Close Widget` 都只停止 widget session。
- Controller X 會 close widget 並關閉 controller/taskbar entry。
- Tray icon 只在 widget Running 時存在。
- 自動測試與 Windows 手動 QA 都有 fresh evidence。
