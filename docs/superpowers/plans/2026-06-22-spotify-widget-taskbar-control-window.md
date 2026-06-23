# Spotify Widget Taskbar 控制窗實作計畫

> **狀態：已被取代。** 本 plan 描述的是舊版控制窗 `Show/Hide + Quit` 設計。最新 canonical plan 是 `docs/superpowers/plans/2026-06-23-spotify-widget-controller-lifecycle.md`。不要再依照本文件實作新的 controller lifecycle。

> **給 agentic workers：** 必須使用 `superpowers:subagent-driven-development`（建議）或 `superpowers:executing-plans` 逐任務執行本計畫。所有步驟都使用 checkbox (`- [ ]`) 追蹤。

**目標：** 將方案 A 的最小化空白 host 改成方案 B 的小型控制窗：taskbar entry 仍常駐，點 taskbar 顯示控制窗，控制窗提供 `Show Widget` / `Hide Widget` 與 `Quit`。

**架構：** 沿用既有 `TaskbarHostWindow`，但把它從「還原時立刻叫回 widget 並重新 minimize」改成「正常可見的小控制窗」。`App` 負責把 widget visible 狀態同步給 host，並讓 tray 和控制窗共用同一個 `_toggle_widget()` 行為。

**技術組合：** Python 3.12、PyQt6、pytest、pytest-qt、PyInstaller one-folder build。

---

## 範圍

本計畫只實作方案 B：

- `TaskbarHostWindow` 變成有內容的小型控制窗。
- 控制窗按鈕依 widget 狀態顯示 `Show Widget` 或 `Hide Widget`。
- 控制窗 toggle button 走 `App._toggle_widget()`。
- 控制窗 `Quit` 走 `QApplication.quit()`。
- 控制窗按 X / taskbar Close window 時回到 minimized，app 繼續跑，taskbar entry 保留。
- Tray icon 原本 show/hide/quit 行為不改。
- `LyricsWidget` 原本小工具行為不改，仍保留 `Qt.Tool`。

本計畫不做：

- Installer。
- Start Menu / Desktop shortcut。
- taskbar pinning。
- size preset / settings 控制窗入口。
- 移除 widget 自己原本的 hide/close 控制。

## 檔案分工

- 修改 `src/taskbar_host.py`：建立小控制窗 UI、狀態同步 method、toggle / quit signals、close 轉 minimized。
- 修改 `tests/test_taskbar_host.py`：改測控制窗 UI、狀態切換、button signals、close/minimize 行為。
- 修改 `src/main.py`：把 host signals 接到 `_toggle_widget()` / `QApplication.quit()`；在 show/hide/raise 後同步 host button 狀態。
- 修改 `tests/test_main.py`：改測 App wiring、start 初始狀態、toggle/raise 對 host 狀態同步。

## 任務 1：把 TaskbarHostWindow 改成小型控制窗

**檔案：**
- 修改：`tests/test_taskbar_host.py`
- 修改：`src/taskbar_host.py`

- [ ] **步驟 1：先更新 taskbar host tests，描述方案 B 行為**

把 `tests/test_taskbar_host.py` 改成：

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
```

- [ ] **步驟 2：跑 taskbar host 測試確認 RED**

執行：

```powershell
python -m pytest tests/test_taskbar_host.py -q
```

預期：FAIL，原因包含 `TaskbarHostWindow` 還沒有 `_status_label`、`_toggle_button`、`set_widget_visible()`、`toggle_widget_requested` 或 `quit_requested`。

- [ ] **步驟 3：把 `src/taskbar_host.py` 改成控制窗實作**

把 `src/taskbar_host.py` 改成：

```python
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.app_icon import build_app_icon


class TaskbarHostWindow(QWidget):
    toggle_widget_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spotify Lyrics Widget")
        self.setWindowIcon(build_app_icon())
        self.resize(320, 140)

        self._title_label = QLabel("Spotify Lyrics Widget")
        self._status_label = QLabel()
        self._toggle_button = QPushButton()
        self._quit_button = QPushButton("Quit")

        button_layout = QHBoxLayout()
        button_layout.addWidget(self._toggle_button)
        button_layout.addWidget(self._quit_button)

        layout = QVBoxLayout()
        layout.addWidget(self._title_label)
        layout.addWidget(self._status_label)
        layout.addLayout(button_layout)
        self.setLayout(layout)

        self._toggle_button.clicked.connect(self.toggle_widget_requested.emit)
        self._quit_button.clicked.connect(self.quit_requested.emit)
        self.set_widget_visible(False)

    def set_widget_visible(self, is_visible: bool):
        if is_visible:
            self._status_label.setText("Widget: Visible")
            self._toggle_button.setText("Hide Widget")
        else:
            self._status_label.setText("Widget: Hidden")
            self._toggle_button.setText("Show Widget")

    def show_taskbar_entry(self):
        self.showMinimized()

    def closeEvent(self, event):
        event.ignore()
        self.showMinimized()
```

- [ ] **步驟 4：跑 taskbar host 測試確認 GREEN**

執行：

```powershell
python -m pytest tests/test_taskbar_host.py -q
```

預期：`7 passed`。

- [ ] **步驟 5：Commit 任務 1**

執行：

```powershell
git status --short
git add src/taskbar_host.py tests/test_taskbar_host.py
git commit -m "feat: turn taskbar host into control window"
```

預期：commit 只包含 `src/taskbar_host.py` 與 `tests/test_taskbar_host.py`。

## 任務 2：把控制窗接進 App lifecycle

**檔案：**
- 修改：`tests/test_main.py`
- 修改：`src/main.py`

- [ ] **步驟 1：先更新 App lifecycle tests**

把 `test_app_connects_taskbar_host_to_raise_window_and_quit()` 改成：

```python
def test_app_connects_taskbar_host_controls_to_toggle_and_quit():
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

    taskbar_host.toggle_widget_requested.connect.assert_called_once_with(
        app._toggle_widget
    )
    taskbar_host.quit_requested.connect.assert_called_once_with(fake_qapp.quit)
```

把 `test_start_shows_taskbar_entry()` 改成：

```python
def test_start_shows_taskbar_entry_and_marks_widget_visible():
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

    app._taskbar_host.set_widget_visible.assert_called_with(True)
    app._taskbar_host.show_taskbar_entry.assert_called_once()
```

在 `_toggle_widget` tests 附近新增：

```python
def test_raise_window_marks_taskbar_host_widget_visible():
    app, _, widget = _make_app()

    app.raise_window()

    widget.showNormal.assert_called_once()
    widget.raise_.assert_called_once()
    widget.activateWindow.assert_called_once()
    app._taskbar_host.set_widget_visible.assert_called_once_with(True)


def test_toggle_widget_hides_and_updates_taskbar_host_when_visible():
    app, _, widget = _make_app()
    widget.isVisible.return_value = True

    app._toggle_widget()

    widget.hide.assert_called_once()
    app._taskbar_host.set_widget_visible.assert_called_once_with(False)


def test_toggle_widget_raises_and_updates_taskbar_host_when_hidden():
    app, _, widget = _make_app()
    widget.isVisible.return_value = False

    app._toggle_widget()

    widget.showNormal.assert_called_once()
    widget.raise_.assert_called_once()
    widget.activateWindow.assert_called_once()
    app._taskbar_host.set_widget_visible.assert_called_once_with(True)
```

保留既有 tray tests，不新增 tray 專用行為；tray 仍呼叫 `App._toggle_widget()`。

- [ ] **步驟 2：跑 main tests 確認 RED**

執行：

```powershell
python -m pytest tests/test_main.py -q
```

預期：FAIL，原因是 `src.main` 仍連到 `activated` / `close_requested`，且 `_toggle_widget()` / `raise_window()` 還沒有同步 `set_widget_visible()`。

- [ ] **步驟 3：修改 `src/main.py` wiring**

把 `_connect_lifecycle_signals()` 改成：

```python
def _connect_lifecycle_signals(self):
    self._taskbar_host.toggle_widget_requested.connect(self._toggle_widget)
    app = QApplication.instance()
    if app is not None:
        self._widget.close_requested.connect(app.quit)
        self._taskbar_host.quit_requested.connect(app.quit)
```

把 `App.start()` 裡顯示 widget 後的 taskbar host 處理改成：

```python
self._widget.move(self._config.window_x, self._config.window_y)
self._widget.show()
self._taskbar_host.set_widget_visible(True)
self._taskbar_host.show_taskbar_entry()
app = QApplication.instance()
```

把 `raise_window()` 改成：

```python
def raise_window(self):
    self._widget.showNormal()
    self._widget.raise_()
    self._widget.activateWindow()
    self._taskbar_host.set_widget_visible(True)
```

把 `_toggle_widget()` 改成：

```python
def _toggle_widget(self):
    if self._widget.isVisible():
        self._widget.hide()
        self._taskbar_host.set_widget_visible(False)
    else:
        self.raise_window()
```

`shutdown()` 維持：

```python
if self._tray is not None:
    self._tray.hide()
self._taskbar_host.hide()
```

- [ ] **步驟 4：跑 targeted tests 確認 GREEN**

執行：

```powershell
python -m pytest tests/test_main.py tests/test_taskbar_host.py tests/test_windows_app_id.py -q
```

預期：targeted tests 全部通過。

- [ ] **步驟 5：跑完整自動測試**

執行：

```powershell
python -m pytest -q
```

預期：全部測試通過。

- [ ] **步驟 6：Commit 任務 2**

執行：

```powershell
git status --short
git add src/main.py tests/test_main.py
git commit -m "feat: wire taskbar control window"
```

預期：commit 只包含 `src/main.py` 與 `tests/test_main.py`。

## 任務 3：Build 與方案 B 手動 QA

**檔案：**
- 預期沒有 tracked source changes。
- `build/` 與 `dist/` 可能產生 ignored build artifacts。

- [ ] **步驟 1：建 PyInstaller one-folder app**

執行：

```powershell
python -m PyInstaller --noconfirm SpotifyLyricsWidget.spec
```

預期：exit code 0，並產生新的 `dist/SpotifyLyricsWidget/SpotifyLyricsWidget.exe`。

- [ ] **步驟 2：啟動 build 後的 app 做手動 QA**

啟動前先確認沒有舊版 process：

```powershell
Get-Process SpotifyLyricsWidget -ErrorAction SilentlyContinue | Select-Object Id,Path
```

若沒有舊 process，執行：

```powershell
Start-Process -FilePath "C:\Users\crayo\personal-system\projects\spotify_widget\.worktrees\taskbar-host\dist\SpotifyLyricsWidget\SpotifyLyricsWidget.exe" -WindowStyle Hidden
```

預期：

- app 執行中時，taskbar 出現 `Spotify Lyrics Widget`。
- tray icon 仍然出現。
- lyrics widget 仍然是原本的 floating widget。
- 啟動時不直接顯示小控制窗。

- [ ] **步驟 3：手動確認 taskbar 控制窗行為**

手動檢查：

1. 點 taskbar icon。
2. 確認出現小控制窗，而不是空白窗。
3. 確認小控制窗顯示 `Widget: Visible` 和 `Hide Widget`。
4. 按 `Hide Widget`。
5. 確認 lyrics widget 消失，小控制窗變成 `Widget: Hidden` 和 `Show Widget`。
6. 確認 taskbar icon 仍存在。
7. 按 `Show Widget`。
8. 確認 lyrics widget 回來並 raise，小控制窗變成 `Widget: Visible` 和 `Hide Widget`。
9. 用 tray show/hide 各切一次，確認小控制窗狀態同步。
10. 按小控制窗 X，確認控制窗回到 taskbar，app 繼續跑。
11. 再點 taskbar icon，確認小控制窗能再次打開。
12. 按 `Quit`，確認 tray icon、taskbar entry、process 都消失。

- [ ] **步驟 4：在 final handoff 記錄手動 QA 結果**

如果方案 B 通過，在 final handoff 寫：

```text
Manual QA: 方案 B passed on Windows. Taskbar entry opened the control window; Show/Hide Widget matched widget visibility; tray show/hide stayed in sync; closing the control window minimized it back to taskbar; Quit exited cleanly.
```

如果方案 B 失敗，在 final handoff 寫符合實際觀察的證據句，例如：

```text
Manual QA: 方案 B failed on Windows. Clicking taskbar still showed a blank window instead of the control window.
Manual QA: 方案 B failed on Windows. Control window toggle button did not match widget visibility after tray toggle.
Manual QA: 方案 B failed on Windows. Closing the control window removed the taskbar entry while the app kept running.
```

- [ ] **步驟 5：確認 git status**

執行：

```powershell
git status --short --branch
```

預期：tracked files 乾淨。ignored `build/` 和 `dist/` 可以有 generated artifacts，但不能 commit。

## Spec 覆蓋自檢

- 方案 A 實測失敗原因已記錄：spec 已寫明點 taskbar 時明顯閃出空白 host window。
- taskbar entry 常駐：任務 1 保留 `show_taskbar_entry()`，任務 3 手動 QA 驗證。
- 點 taskbar 顯示控制窗：任務 1 讓 host 成為有內容的小控制窗，任務 3 手動 QA 驗證。
- Show/Hide Widget：任務 1 測 button label，任務 2 接到 `_toggle_widget()`。
- 控制窗狀態同步：任務 2 在 `start()`、`raise_window()`、`_toggle_widget()` 同步 `set_widget_visible()`。
- tray 行為不動：任務 2 保留 tray 呼叫 `_toggle_widget()` 的既有路徑。
- widget 小工具行為不動：本計畫不修改 `src/widget.py`。
- Quit：任務 1 加 `quit_requested`，任務 2 接到 `QApplication.quit()`。
- 不實作 installer：範圍明確排除 installer，留到後續 plan。
