# Widget Hover Settings Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> 中文說明：這份計畫交給下一位 agent 或下一輪對話執行時，必須逐項打勾推進。建議用 `superpowers:subagent-driven-development`；如果要在同一個對話內做，改用 `superpowers:executing-plans`。

**Goal:** 把 widget 上的播放控制移除，改成 hover 才顯示的設定、隱藏、退出控制，同時保留 tray 作為顯示/隱藏與退出的備用入口。

**Architecture:** size 選單從 tray 移到 widget 的齒輪浮出選單。widget 和主控制器不再連接播放控制，因為播放/暫停/上一首/下一首交給 Spotify 或工作列 hover 小窗處理。tray 簡化成只負責 `Open / Hide` 和 `Quit`。

**Tech Stack:** Python, PyQt6, pytest, pytest-qt, Windows system tray.

---

## 目前已確認狀態

- 效能節約設定已提交：`421a20b perf: reduce idle polling overhead`。
- 該 commit 當時完整測試為 `python -m pytest -q`，結果 `252 passed`。
- 目前不需要額外補效能文件，因為行為已由測試覆蓋，而且 commit 範圍很窄。

## 目標 UI

```text
[ 歌名 / 歌手                       齒輪   -   x ]
[ 歌詞                                           ]
[ progress                                      ]
```

hover 行為：

- 右側三個控制預設隱藏。
- 滑鼠移到 widget 上時顯示 `齒輪`、`-`、`x`。
- `齒輪` 開啟 size 選單：`Small`、`Medium`、`Large`。
- `-` 隱藏 widget，但程式繼續在 tray 執行。
- `x` 走目前 close 流程，退出整個程式。

tray 行為：

```text
Open / Hide
Quit
```

- tray icon 單擊仍然切換顯示/隱藏。
- tray 不再負責 size 選單。

## 檔案與責任

- 修改 `src/widget.py`
  - 移除 playback button 的 import、signal、widget、layout。
  - 新增 hover-only 的 settings、hide、close button。
  - 新增 widget 層級 signal，讓 main controller 處理 hide 和 size preset。
  - 確保 hover 前後、三種 size preset 都不造成 layout 位移。

- 修改 `src/main.py`
  - 移除 `PlaybackController` 建立與 widget playback signal wiring。
  - 把 widget hide signal 接到既有顯示/隱藏流程。
  - 把 widget size signal 接到 `_on_size_preset_changed`。
  - 不再同步 size preset 到 tray。

- 修改 `src/tray.py`
  - 移除 size submenu。
  - 保留 tray icon 建立與單擊 toggle。
  - 新增明確的 `Open / Hide` menu action，保留 `Quit`。

- 修改 `tests/test_widget.py`
  - 將 playback-control 測試改成 settings/hide/close-control 測試。
  - 保留 layout 穩定性測試。

- 修改 `tests/test_main.py`
  - 將 playback wiring 測試改成 widget settings/hide wiring 測試。
  - 更新 tray constructor 期待值。

- 修改 `tests/test_tray.py`
  - 將 size menu 測試改成簡化後的 tray menu 測試。

- 刪除 `src/transport_button.py` 和 `tests/test_transport_button.py`
  - widget playback controls 移除後，這兩個檔案會變成 dead code。

- 暫時保留 `src/playback.py` 和 `tests/test_playback.py`
  - Spotify playback API wrapper 仍有測試，但這次不再從 widget 使用。
  - 如果之後確認永遠不會回到 widget 播放控制，再另開 cleanup commit 刪除。

## Task 1: Widget Hover Controls 測試

**Files:**
- Modify: `tests/test_widget.py`

- [ ] **Step 1: 改名並更新 hover visibility 測試**

把 `test_transport_controls_are_hover_only_and_do_not_move_title` 換成：

```python
def test_hover_controls_are_hover_only_and_do_not_move_title(qtbot):
    from src.widget import LyricsWidget

    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    widget.update_track_info("A very long song title that needs eliding", "Artist")

    title_before = widget._track_label.geometry()
    assert not widget._settings_btn.isVisible()
    assert not widget._hide_btn.isVisible()
    assert not widget._close_btn.isVisible()

    widget._on_enter_hover()
    title_hover = widget._track_label.geometry()

    assert widget._settings_btn.isVisible()
    assert widget._hide_btn.isVisible()
    assert widget._close_btn.isVisible()
    assert title_hover == title_before

    widget._on_leave_hover()
    assert not widget._settings_btn.isVisible()
    assert not widget._hide_btn.isVisible()
    assert not widget._close_btn.isVisible()
    assert widget._track_label.geometry() == title_before
```

- [ ] **Step 2: 更新右側 slot 順序測試**

把 `test_transport_controls_sit_between_title_and_close_slots` 換成：

```python
def test_hover_controls_sit_after_title_slot(qtbot):
    from src.widget import LyricsWidget

    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    widget._on_enter_hover()

    settings = widget._settings_btn.geometry()
    hide = widget._hide_btn.geometry()
    close = widget._close_btn.geometry()
    title_right = widget._track_label.mapTo(
        widget._panel,
        widget._track_label.rect().topRight(),
    ).x()

    assert title_right < settings.left()
    assert settings.right() < hide.left()
    assert hide.right() < close.left()
```

- [ ] **Step 3: 更新 title row 對齊測試**

把 `test_transport_controls_align_with_title_row_height` 換成：

```python
def test_hover_controls_align_with_title_row_height(qtbot):
    from src.widget import LyricsWidget

    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    widget._on_enter_hover()

    controls_y = widget._settings_btn.geometry().top()
    title_y = widget._track_label.mapTo(
        widget._panel,
        widget._track_label.rect().topLeft(),
    ).y()

    assert controls_y == title_y
```

- [ ] **Step 4: 更新 title elision 測試**

把 `test_title_label_elides_before_transport_controls_slot` 換成：

```python
def test_title_label_elides_before_hover_controls_slot(qtbot):
    from src.widget import LyricsWidget

    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)

    title_right = widget._track_label.mapTo(
        widget._panel,
        widget._track_label.rect().topRight(),
    ).x()

    assert title_right < widget._settings_btn.geometry().left()
```

- [ ] **Step 5: 移除 playback button signal 測試，改成 hide 和 size signal 測試**

刪除 `test_play_pause_button_reflects_playing_state` 和 `test_transport_buttons_emit_widget_level_signals`，新增：

```python
def test_hide_button_emits_hide_requested(qtbot):
    from src.widget import LyricsWidget

    widget = LyricsWidget()
    qtbot.addWidget(widget)

    with qtbot.waitSignal(widget.hide_requested, timeout=1000):
        widget._hide_btn.click()


def test_settings_menu_emits_size_preset_requested(qtbot):
    from src.widget import LyricsWidget

    widget = LyricsWidget()
    qtbot.addWidget(widget)

    medium_action = next(
        action for action in widget._size_menu.actions()
        if action.data() == "medium"
    )

    with qtbot.waitSignal(widget.size_preset_requested, timeout=1000) as blocker:
        medium_action.trigger()

    assert blocker.args == ["medium"]
```

- [ ] **Step 6: 更新 size preset layout 測試**

把 `test_size_preset_keeps_title_before_controls` 換成：

```python
def test_size_preset_keeps_title_before_hover_controls(qtbot):
    from src.widget import SIZE_PRESETS, LyricsWidget

    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)

    for name in SIZE_PRESETS:
        widget.apply_size_preset(name)
        widget._on_enter_hover()
        title_right = widget._track_label.mapTo(
            widget._panel,
            widget._track_label.rect().topRight(),
        ).x()
        assert title_right < widget._settings_btn.geometry().left()
        assert widget._settings_btn.geometry().right() < widget._hide_btn.geometry().left()
        assert widget._hide_btn.geometry().right() < widget._close_btn.geometry().left()
```

- [ ] **Step 7: 跑 widget 測試，確認會先失敗**

Run:

```powershell
python -m pytest tests/test_widget.py -q
```

Expected before implementation:

```text
FAILED tests/test_widget.py::test_hover_controls_are_hover_only_and_do_not_move_title
FAILED tests/test_widget.py::test_hover_controls_sit_after_title_slot
FAILED tests/test_widget.py::test_hide_button_emits_hide_requested
FAILED tests/test_widget.py::test_settings_menu_emits_size_preset_requested
```

## Task 2: 實作 Widget Hover Settings / Hide / Close Controls

**Files:**
- Modify: `src/widget.py`

- [ ] **Step 1: 更新 imports**

移除 `TransportButton`。如果還沒 import `QMenu`，加入：

```python
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
```

- [ ] **Step 2: 替換 control constants**

把 playback cluster 常數換成固定 hover control slot：

```python
CONTROL_SLOT_WIDTH = 22
CONTROL_SLOT_HEIGHT = 22
CONTROL_GAP = 6
HOVER_CONTROL_COUNT = 3
TOP_ROW_RIGHT_RESERVE = (
    CONTROL_SLOT_WIDTH * HOVER_CONTROL_COUNT
    + CONTROL_GAP * (HOVER_CONTROL_COUNT - 1)
)
```

- [ ] **Step 3: 更新 `WidgetSizePreset` 欄位**

保留 layout 需要的欄位，將 control 欄位改成：

```python
    title_control_gap: int
    control_width: int
    control_height: int
    control_gap: int
    right_margin: int
    title_font_pt: int
    lyric_font_pt: int
    lyric_lines: int
    control_font_px: int
```

移除這些 playback-control 欄位：

```python
    controls_width: int
    controls_height: int
    controls_close_gap: int
    close_width: int
    close_height: int
    button_size: QSize
    controls_spacing: int
    close_font_px: int
```

- [ ] **Step 4: 更新 `SIZE_PRESETS`**

使用以下 preset 值，讓右側保留寬度接近現在版面：

```python
"small": WidgetSizePreset(
    "small", 300, 74, 6, 18, 2, 41, 2, 1, 4, 10,
    204, 8, 18, 18, 5, 6, 8, 10, 2, 12,
),
"medium": WidgetSizePreset(
    "medium", 360, 90, 8, 21, 4, 48, 3, 1, 5, 13,
    242, 11, 19, 19, 6, 9, 9, 13, 2, 13,
),
"large": WidgetSizePreset(
    "large", 420, 112, 12, 24, 5, 56, 5, 2, 8, 16,
    288, 14, 20, 20, 7, 10, 10, 16, 2, 14,
),
```

- [ ] **Step 5: 替換 widget signals**

使用以下 signal：

```python
    close_requested = pyqtSignal()
    hide_requested = pyqtSignal()
    size_preset_requested = pyqtSignal(str)
```

- [ ] **Step 6: 在 `_setup_ui` 內加入小型 button factory**

放在建立控制按鈕前：

```python
        def make_control_button(text: str) -> QPushButton:
            button = QPushButton(text, self._panel)
            button.setMouseTracking(True)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setVisible(False)
            return button
```

- [ ] **Step 7: 替換 playback controls 建立流程**

移除 `_controls_cluster`、`_controls_layout`、`_prev_btn`、`_play_pause_btn`、`_next_btn`，改成：

```python
        self._settings_btn = make_control_button("⚙")
        self._hide_btn = make_control_button("-")
        self._close_btn = make_control_button("×")

        self._size_menu = QMenu(self)
        for label, value in (("Small", "small"), ("Medium", "medium"), ("Large", "large")):
            action = self._size_menu.addAction(label)
            action.setData(value)
            action.triggered.connect(
                lambda checked=False, preset=value: self.size_preset_requested.emit(preset)
            )

        self._settings_btn.clicked.connect(
            lambda: self._size_menu.popup(
                self._settings_btn.mapToGlobal(self._settings_btn.rect().bottomLeft())
            )
        )
        self._hide_btn.clicked.connect(self.hide_requested)
        self._close_btn.clicked.connect(self.close)
```

- [ ] **Step 8: 更新 `apply_size_preset`**

把 right reserve 與 button sizing block 改成：

```python
        top_row_right_reserve = (
            preset.title_control_gap
            + preset.control_width * HOVER_CONTROL_COUNT
            + preset.control_gap * (HOVER_CONTROL_COUNT - 1)
        )
        self._top_row_layout.setContentsMargins(0, 0, top_row_right_reserve, 0)
```

再設定 button size 與樣式：

```python
        control_style = (
            f"QPushButton {{ color: {WHITE}; background: transparent; border: none; "
            f"font-size: {preset.control_font_px}px; }}"
            f"QPushButton:hover {{ color: {SPOTIFY_GREEN}; }}"
        )
        for button in (self._settings_btn, self._hide_btn, self._close_btn):
            button.setFixedSize(preset.control_width, preset.control_height)
            button.setStyleSheet(control_style)
```

- [ ] **Step 9: 更新 `_position_overlay_controls`**

使用明確的右側 slot：

```python
    def _position_overlay_controls(self):
        if not hasattr(self, "_close_btn"):
            return

        preset = SIZE_PRESETS.get(
            self._size_preset_name,
            SIZE_PRESETS[DEFAULT_SIZE_PRESET],
        )
        x = preset.left_margin + preset.title_width + preset.title_control_gap
        y = preset.top_padding
        self._settings_btn.move(x, y)
        self._hide_btn.move(x + preset.control_width + preset.control_gap, y)
        self._close_btn.move(
            x + (preset.control_width + preset.control_gap) * 2,
            y,
        )
```

- [ ] **Step 10: 移除 `set_playing`**

刪除：

```python
    def set_playing(self, is_playing: bool):
        self._play_pause_btn.set_mode("pause" if is_playing else "play")
```

- [ ] **Step 11: 更新 hover methods**

替換 visibility 邏輯：

```python
    def _on_enter_hover(self):
        self._settings_btn.setVisible(True)
        self._hide_btn.setVisible(True)
        self._close_btn.setVisible(True)
        self._track_label.start_marquee()

    def _on_leave_hover(self):
        if self.underMouse():
            return
        self._settings_btn.setVisible(False)
        self._hide_btn.setVisible(False)
        self._close_btn.setVisible(False)
        self._track_label.stop_marquee()
```

- [ ] **Step 12: 跑 widget tests**

Run:

```powershell
python -m pytest tests/test_widget.py -q
```

Expected:

```text
tests/test_widget.py ... passed
```

- [ ] **Step 13: commit widget-only work**

Run:

```powershell
git add src/widget.py tests/test_widget.py
git commit -m "feat: add widget hover settings controls"
```

## Task 3: Main App Wiring 移除 Playback Buttons

**Files:**
- Modify: `tests/test_main.py`
- Modify: `src/main.py`

- [ ] **Step 1: 更新 `_make_app` 測試 setup**

`_make_app` 只保留既有的 `Config`、`LyricsWidget`、`SpotifyWorker`、`LyricsWorker` patch。不要再為 widget button 期待 `PlaybackController` 被建立。

- [ ] **Step 2: 替換 playback wiring 測試**

把 `test_connect_signals_wires_playback_controls` 換成：

```python
def test_connect_signals_wires_widget_hide_and_size_controls():
    app, _, widget = _make_app()

    app._connect_signals()

    widget.hide_requested.connect.assert_called_once_with(app._toggle_widget)
    widget.size_preset_requested.connect.assert_called_once_with(
        app._on_size_preset_changed
    )
```

- [ ] **Step 3: 刪除 play/pause click 測試**

刪除 `test_play_pause_click_uses_latest_play_state`。

- [ ] **Step 4: 替換 playing icon state 測試**

把 `test_state_sync_updates_widget_playing_icon` 換成：

```python
def test_state_sync_resyncs_widget_timer_without_playing_icon():
    app, _, widget = _make_app()

    app._on_state_synced(1234, True, 10.0)

    assert app._is_playing is True
    widget.resync_local_timer.assert_called_once_with(1234, True, 10.0)
    widget.set_playing.assert_not_called()
```

- [ ] **Step 5: 更新 tray constructor 測試**

把 `test_start_creates_and_shows_tray` 的 constructor 期待值改成：

```python
    tray_class.assert_called_once_with(
        on_toggle=app._toggle_widget,
        on_quit=qapp.quit,
    )
```

- [ ] **Step 6: 替換 tray size-preset constructor 測試**

把 `test_start_creates_tray_with_size_preset` 換成：

```python
def test_start_creates_tray_without_size_menu_wiring():
    app, config, _ = _make_app()
    config.client_id = "client"
    config.size_preset = "medium"
    app._ensure_auth = MagicMock(return_value=True)
    qapp = MagicMock()

    with (
        patch("src.main.QApplication.instance", return_value=qapp),
        patch("src.main.TrayIcon") as tray_class,
    ):
        app.start()

    tray_class.assert_called_once()
    assert "size_preset" not in tray_class.call_args.kwargs
    assert "on_size_changed" not in tray_class.call_args.kwargs
```

- [ ] **Step 7: 更新 size-preset change 測試**

在 `test_size_preset_change_updates_widget_and_config` 移除 tray size sync 期待：

```python
    app._tray = MagicMock()
    widget.apply_size_preset.reset_mock()
    config.save.reset_mock()
    widget.size_preset = "small"

    app._on_size_preset_changed("small")

    widget.apply_size_preset.assert_called_once_with("small")
    assert config.size_preset == "small"
    config.save.assert_called_once()
    app._tray.set_size_preset.assert_not_called()
```

- [ ] **Step 8: 跑 main tests，確認會先失敗**

Run:

```powershell
python -m pytest tests/test_main.py -q
```

Expected before implementation:

```text
FAILED tests/test_main.py::test_connect_signals_wires_widget_hide_and_size_controls
FAILED tests/test_main.py::test_start_creates_and_shows_tray
FAILED tests/test_main.py::test_start_creates_tray_without_size_menu_wiring
```

- [ ] **Step 9: 從 app code 移除 playback controller**

在 `src/main.py` 移除：

```python
from src.playback import PlaybackController
```

在 `App.__init__` 移除：

```python
        self._playback = PlaybackController(self._config)
```

- [ ] **Step 10: 簡化 tray 建立**

把 `start` 裡的 `TrayIcon` call 換成：

```python
        self._tray = TrayIcon(
            on_toggle=self._toggle_widget,
            on_quit=app.quit if app is not None else (lambda: None),
        )
```

- [ ] **Step 11: 替換 widget signal wiring**

在 `_connect_signals` 移除：

```python
        self._widget.prev_clicked.connect(self._playback.previous)
        self._widget.next_clicked.connect(self._playback.next)
        self._widget.play_pause_clicked.connect(self._on_play_pause_clicked)
```

加入：

```python
        self._widget.hide_requested.connect(self._toggle_widget)
        self._widget.size_preset_requested.connect(self._on_size_preset_changed)
```

- [ ] **Step 12: 移除 playback icon 更新**

在 `_on_state_synced` 移除：

```python
        self._widget.set_playing(is_playing)
```

在 `_on_playback_toggled` 移除：

```python
        self._widget.set_playing(is_playing)
```

- [ ] **Step 13: 刪除 `_on_play_pause_clicked`**

移除整個 method：

```python
    @pyqtSlot()
    def _on_play_pause_clicked(self):
        self._playback.toggle(self._is_playing)
        self._is_playing = not self._is_playing
        self._widget.set_playing(self._is_playing)
```

- [ ] **Step 14: 停止同步 tray size state**

在 `_on_size_preset_changed` 移除：

```python
        if self._tray is not None:
            self._tray.set_size_preset(self._widget.size_preset)
```

- [ ] **Step 15: 跑 main tests**

Run:

```powershell
python -m pytest tests/test_main.py -q
```

Expected:

```text
tests/test_main.py ... passed
```

- [ ] **Step 16: commit main wiring**

Run:

```powershell
git add src/main.py tests/test_main.py
git commit -m "refactor: remove widget playback control wiring"
```

## Task 4: 簡化 Tray Menu

**Files:**
- Modify: `tests/test_tray.py`
- Modify: `src/tray.py`

- [ ] **Step 1: 更新 tray test factory**

把 `_make_tray` 換成：

```python
def _make_tray(**overrides):
    callbacks = dict(
        on_toggle=_noop,
        on_quit=_noop,
    )
    callbacks.update(overrides)
    return TrayIcon(**callbacks)
```

- [ ] **Step 2: 替換 tray menu tests**

把 `test_menu_has_size_and_quit`、`test_menu_has_size_submenu_with_presets`、`test_size_action_calls_callback` 換成：

```python
def test_menu_has_open_hide_and_quit(qtbot):
    tray = _make_tray()
    labels = [action.text() for action in tray._menu.actions() if action.text()]
    assert labels == ["Open / Hide", "Quit"]


def test_open_hide_menu_action_calls_on_toggle(qtbot):
    calls = []
    tray = _make_tray(on_toggle=lambda: calls.append("toggle"))

    open_hide_action = next(
        action for action in tray._menu.actions()
        if action.text() == "Open / Hide"
    )
    open_hide_action.trigger()

    assert calls == ["toggle"]


def test_quit_menu_action_calls_on_quit(qtbot):
    calls = []
    tray = _make_tray(on_quit=lambda: calls.append("quit"))

    quit_action = next(
        action for action in tray._menu.actions()
        if action.text() == "Quit"
    )
    quit_action.trigger()

    assert calls == ["quit"]
```

- [ ] **Step 3: 跑 tray tests，確認會先失敗**

Run:

```powershell
python -m pytest tests/test_tray.py -q
```

Expected before implementation:

```text
FAILED tests/test_tray.py::test_menu_has_open_hide_and_quit
FAILED tests/test_tray.py::test_open_hide_menu_action_calls_on_toggle
```

- [ ] **Step 4: 移除 tray size menu code**

在 `src/tray.py` 移除：

```python
from PyQt6.QtGui import QActionGroup, QIcon
```

改成：

```python
from PyQt6.QtGui import QIcon
```

移除：

```python
SIZE_ACTIONS = [
    ("Small", "small"),
    ("Medium", "medium"),
    ("Large", "large"),
]
```

- [ ] **Step 5: 簡化 `TrayIcon.__init__`**

使用這個 constructor：

```python
class TrayIcon:
    def __init__(
        self,
        on_toggle,
        on_quit,
        parent=None,
    ):
        self._on_toggle = on_toggle
        self._tray = QSystemTrayIcon(build_tray_icon(), parent)
        self._tray.setToolTip("Spotify Lyrics Widget")

        self._menu = QMenu()
        self._menu.addAction("Open / Hide").triggered.connect(on_toggle)
        self._menu.addAction("Quit").triggered.connect(on_quit)
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_tray_activated)
```

- [ ] **Step 6: 移除 tray size sync API**

刪除：

```python
    def set_size_preset(self, preset: str):
        if preset in self._size_actions:
            self._size_actions[preset].setChecked(True)
```

- [ ] **Step 7: 跑 tray tests**

Run:

```powershell
python -m pytest tests/test_tray.py -q
```

Expected:

```text
tests/test_tray.py ... passed
```

- [ ] **Step 8: commit tray simplification**

Run:

```powershell
git add src/tray.py tests/test_tray.py
git commit -m "refactor: simplify tray menu"
```

## Task 5: 刪除 Dead Transport Button Module

**Files:**
- Delete: `src/transport_button.py`
- Delete: `tests/test_transport_button.py`

- [ ] **Step 1: 確認 production import 已不存在**

Run:

```powershell
rg -n "TransportButton|transport_button" src tests
```

Expected:

```text
tests/test_transport_button.py:...
```

實作前只應該剩測試檔引用。

- [ ] **Step 2: 分開刪除 dead files**

Run as separate commands:

```powershell
Remove-Item -LiteralPath src\transport_button.py
```

```powershell
Remove-Item -LiteralPath tests\test_transport_button.py
```

- [ ] **Step 3: 確認已無引用**

Run:

```powershell
rg -n "TransportButton|transport_button" src tests
```

Expected:

```text
```

- [ ] **Step 4: 跑 focused tests**

Run:

```powershell
python -m pytest tests/test_widget.py tests/test_main.py tests/test_tray.py -q
```

Expected:

```text
tests/test_widget.py tests/test_main.py tests/test_tray.py ... passed
```

- [ ] **Step 5: commit deletion**

Run:

```powershell
git add src/transport_button.py tests/test_transport_button.py
git commit -m "refactor: remove unused transport button"
```

## Task 6: Full Verification

**Files:**
- No code edits.

- [ ] **Step 1: 跑完整測試**

Run:

```powershell
python -m pytest -q
```

Expected:

```text
passed
```

- [ ] **Step 2: 確認 git state**

Run:

```powershell
git status --short
```

Expected:

```text
```

- [ ] **Step 3: 手動桌面驗證**

用平常的本機開發指令啟動 app，確認：

```text
1. Widget 能啟動，歌詞仍正常更新。
2. Hover 顯示齒輪、-、x，而且 title、歌詞、progress bar 不位移。
3. 齒輪會開 Small / Medium / Large。
4. 每個 size 都能切換，重啟後仍保留。
5. - 會隱藏 widget，而且 tray icon 能恢復顯示。
6. x 會退出 app，不留下 widget process。
7. Tray menu 只顯示 Open / Hide 和 Quit。
8. Tray icon 單擊仍能切換 widget 顯示/隱藏。
```

- [ ] **Step 4: 最終 commit 檢查**

Run:

```powershell
git log --oneline -5
```

Expected newest implementation commits:

```text
refactor: remove unused transport button
refactor: simplify tray menu
refactor: remove widget playback control wiring
feat: add widget hover settings controls
```

## 自我檢查

- 需求覆蓋：
  - widget settings popup：Task 1 和 Task 2。
  - widget hide button：Task 1、Task 2、Task 3。
  - close button：保留 `self.close()` 和 `close_requested` 現有路徑。
  - tray show/hide fallback：Task 3 和 Task 4。
  - 移除 playback controls：Task 2 和 Task 3。

- 空洞項目掃描：
  - 沒有空白待補項或未指定的後續決策。
  - 唯一刻意延後的是 `src/playback.py` cleanup，因為它還是被測試覆蓋的 Spotify playback API wrapper。

- 型別一致性：
  - `hide_requested` 是無參數 signal。
  - `size_preset_requested` emit preset string，交給 `_on_size_preset_changed`。
  - widget button 名稱全程使用 `_settings_btn`、`_hide_btn`、`_close_btn`。
