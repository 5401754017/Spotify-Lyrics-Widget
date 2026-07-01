# Spotify Widget Taskbar Host 實作計畫

> 狀態：歷史 plan。這是早期方案 A taskbar host 計畫；目前 controller lifecycle 以 `docs/superpowers/plans/2026-06-23-spotify-widget-controller-lifecycle.md` 和 `docs/superpowers/specs/2026-06-21-spotify-widget-taskbar-host-installer-design.md` 為準。

> **給 agentic workers：** 必須使用 `superpowers:subagent-driven-development`（建議）或 `superpowers:executing-plans` 逐 task 執行本計畫。所有步驟都使用 checkbox (`- [ ]`) 追蹤。

**目標：** 實作 `docs/superpowers/specs/2026-06-21-spotify-widget-taskbar-host-installer-design.md` 裡的方案 A：保留 lyrics widget 的 `Qt.Tool` 小工具行為，新增一個最小化的 taskbar host window，並設定穩定的 Windows AppUserModelID。

**架構：** 新增兩個小而明確的模組：`src/windows_app_id.py` 負責 Windows AppUserModelID；`src/taskbar_host.py` 負責最小化 taskbar host window。`src/main.py` 只做 lifecycle wiring：app 執行期間維持 taskbar entry、host activated 時呼叫 `App.raise_window()`、host close 時退出 app。

**技術組合：** Python 3.12、PyQt6、pytest、pytest-qt、PyInstaller one-folder build。

---

## 範圍

本計畫只實作方案 A：

- 新增最小化的 `TaskbarHostWindow`。
- 保留 `LyricsWidget` 現有 window flags，包含 `Qt.Tool`。
- 在 Windows 設定產品層級 AppUserModelID：`SpotifyLyricsWidget.Desktop`。
- 加入自動測試與手動 QA 步驟，驗證 taskbar 行為。

本計畫不做：

- 方案 B：小型狀態窗 host。
- Inno Setup installer。
- Start Menu / Desktop shortcut 變更。
- taskbar pinning。

如果方案 A 在手動 QA 時失敗，例如 host 空白窗明顯閃爍、taskbar entry 不穩定，這輪工作要停下來記錄證據；方案 B 另開後續 plan / 對話處理。

## 檔案分工

- 新增 `src/windows_app_id.py`：Windows-only helper，封裝 `SetCurrentProcessExplicitAppUserModelID`。
- 新增 `tests/test_windows_app_id.py`：測 product ID、非 Windows no-op、Windows 成功呼叫、Windows 失敗 logging。
- 新增 `src/taskbar_host.py`：只作為 taskbar entry 的最小化 top-level Qt window。
- 新增 `tests/test_taskbar_host.py`：pytest-qt 測 host flags、最小化顯示、activated signal、close signal。
- 修改 `src/main.py`：在建立 `QApplication` 前設定 AppUserModelID；建立並連接 taskbar host；startup 時 show taskbar entry；shutdown 時 hide host。
- 修改 `tests/test_main.py`：在 `App` 測試裡 patch 新 host，驗證 wiring、startup、shutdown、main ordering。

## 任務 1：Windows AppUserModelID Helper

**檔案：**
- 新增：`src/windows_app_id.py`
- 新增：`tests/test_windows_app_id.py`

- [ ] **步驟 1：先寫 AppUserModelID helper 的 failing tests**

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

- [ ] **步驟 2：跑測試確認 RED**

執行：

```powershell
python -m pytest tests/test_windows_app_id.py -q
```

預期：FAIL，錯誤是 `ModuleNotFoundError: No module named 'src.windows_app_id'`。

- [ ] **步驟 3：加入最小 AppUserModelID helper 實作**

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

- [ ] **步驟 4：跑測試確認 GREEN**

執行：

```powershell
python -m pytest tests/test_windows_app_id.py -q
```

預期：`4 passed`。

- [ ] **步驟 5：Commit 任務 1**

執行：

```powershell
git status --short
git add src/windows_app_id.py tests/test_windows_app_id.py
git commit -m "feat: add Windows app user model id helper"
```

預期：commit 只包含 `src/windows_app_id.py` 與 `tests/test_windows_app_id.py`。

## 任務 2：最小化 Taskbar Host Window

**檔案：**
- 新增：`src/taskbar_host.py`
- 新增：`tests/test_taskbar_host.py`

- [ ] **步驟 1：先寫 taskbar host 的 failing tests**

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

- [ ] **步驟 2：跑 taskbar host 測試確認 RED**

執行：

```powershell
python -m pytest tests/test_taskbar_host.py -q
```

預期：FAIL，錯誤是 `ModuleNotFoundError: No module named 'src.taskbar_host'`。

- [ ] **步驟 3：加入最小 taskbar host 實作**

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

- [ ] **步驟 4：跑 taskbar host 測試確認 GREEN**

執行：

```powershell
python -m pytest tests/test_taskbar_host.py -q
```

預期：`5 passed`。

- [ ] **步驟 5：Commit 任務 2**

執行：

```powershell
git status --short
git add src/taskbar_host.py tests/test_taskbar_host.py
git commit -m "feat: add minimized taskbar host window"
```

預期：commit 只包含 `src/taskbar_host.py` 與 `tests/test_taskbar_host.py`。

## 任務 3：把 Taskbar Host 接進 App Lifecycle

**檔案：**
- 修改：`src/main.py`
- 修改：`tests/test_main.py`

- [ ] **步驟 1：更新 `tests/test_main.py` fixture，並加入 failing lifecycle tests**

把 `tests/test_main.py` 的 `_make_app()` 改成會 patch `TaskbarHostWindow`：

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

所有直接 patch dependencies 來建 `App()` 的測試，都加上：

```python
patch("src.main.TaskbarHostWindow", return_value=MagicMock()),
```

在既有 lifecycle tests 附近新增：

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

把 `test_main_configures_logging_before_starting_qapplication()` 改成驗證 AppUserModelID 的呼叫順序：

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

- [ ] **步驟 2：跑 main tests 確認 RED**

執行：

```powershell
python -m pytest tests/test_main.py -q
```

預期：FAIL，原因是 `src.main` 還沒有 import `TaskbarHostWindow` / `set_windows_app_user_model_id`，`App` 也還沒有建立 `_taskbar_host`。

- [ ] **步驟 3：在 `src/main.py` 接上 taskbar host 和 AppUserModelID**

在 app imports 附近加入：

```python
from src.taskbar_host import TaskbarHostWindow
from src.windows_app_id import set_windows_app_user_model_id
```

在 `App.__init__` 裡，於 `_connect_lifecycle_signals()` 前建立 host：

```python
self._tray: TrayIcon | None = None
self._taskbar_host = TaskbarHostWindow()
self._last_heartbeat_ts: float = 0.0
```

把 `_connect_lifecycle_signals()` 改成：

```python
def _connect_lifecycle_signals(self):
    self._taskbar_host.activated.connect(self.raise_window)
    app = QApplication.instance()
    if app is not None:
        self._widget.close_requested.connect(app.quit)
        self._taskbar_host.close_requested.connect(app.quit)
```

在 `App.start()` 裡，歌詞 widget show 之後顯示 taskbar entry：

```python
self._widget.move(self._config.window_x, self._config.window_y)
self._widget.show()
self._taskbar_host.show_taskbar_entry()
app = QApplication.instance()
```

在 `App.shutdown()` 裡，停止 worker 前先 hide taskbar host：

```python
logging.info("App.shutdown called -- event loop is exiting")
if self._tray is not None:
    self._tray.hide()
self._taskbar_host.hide()
```

在 `main()` 裡，logging 設定完成後、建立 `QApplication` 前設定 AppUserModelID：

```python
def main():
    configure_logging()
    set_windows_app_user_model_id()
    app = QApplication(sys.argv)
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

- [ ] **步驟 6：Commit 任務 3**

執行：

```powershell
git status --short
git add src/main.py tests/test_main.py
git commit -m "feat: keep taskbar entry while widget is hidden"
```

預期：commit 只包含 `src/main.py` 與 `tests/test_main.py`。

## 任務 4：Build 與方案 A 手動 QA

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

執行：

```powershell
Start-Process -FilePath "C:\Users\crayo\personal-system\projects\spotify_widget\.worktrees\taskbar-host\dist\SpotifyLyricsWidget\SpotifyLyricsWidget.exe" -WindowStyle Hidden
```

預期：

- app 執行中時，taskbar 出現 `Spotify Lyrics Widget`。
- tray icon 仍然出現。
- lyrics widget 仍然是原本的 floating widget。

- [ ] **步驟 3：手動確認 hide 與 taskbar 行為**

手動檢查：

1. 按 widget 的 hide button。
2. 確認 lyrics widget 消失。
3. 確認 taskbar icon 仍存在。
4. 點 taskbar icon。
5. 確認 lyrics widget 回來並 raise。
6. 觀察是否有空白 host window 明顯閃爍；若閃爍明顯或讓人困惑，停止並記錄方案 A 手動 QA 失敗。
7. 用 tray Quit，確認 tray icon 和 taskbar entry 都消失。

- [ ] **步驟 4：在 final handoff 記錄手動 QA 結果**

如果方案 A 通過，在 final handoff 寫：

```text
Manual QA: 方案 A passed on Windows. Taskbar entry stayed visible while widget was hidden; clicking taskbar raised the widget; no obvious blank host flash.
```

如果方案 A 失敗，在 final handoff 寫符合實際觀察的證據句：

```text
Manual QA: 方案 A failed on Windows. Blank host window flashed visibly when clicking taskbar.
Manual QA: 方案 A failed on Windows. Taskbar entry disappeared after widget was hidden.
Manual QA: 方案 A failed on Windows. Clicking taskbar did not raise the widget.
```

- [ ] **步驟 5：確認 git status**

執行：

```powershell
git status --short --branch
```

預期：tracked files 乾淨。ignored `build/` 和 `dist/` 可以有 generated artifacts，但不能 commit。

## Spec 覆蓋自檢

- app 執行中維持 taskbar entry：任務 2 建 host，任務 3 startup 時 show host。
- lyrics widget 保留 `Qt.Tool`：本計畫完全不改 `src/widget.py`。
- widget 隱藏時 taskbar 仍存在：任務 3 讓 host lifecycle 獨立於 widget visibility；任務 4 手動 QA 驗證。
- 點 taskbar 叫回 widget：任務 2 emit `activated`；任務 3 connect 到 `App.raise_window()`。
- tray 行為保留：任務 3 不改 `TrayIcon` wiring，完整測試會覆蓋既有 tray tests。
- 穩定 AppUserModelID：任務 1 加 `SpotifyLyricsWidget.Desktop`，任務 3 在 `QApplication` 前呼叫。
- 不實作方案 B：範圍和任務 4 明確要求方案 A 失敗時停下來記錄證據。
- 不實作 installer：範圍明確排除 installer，留到後續 plan。
