# Spotify Widget Size Presets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 實作 V2.03 size preset，讓 widget 可從 tray menu 切換 Current / Compact / Small / Mini 四種固定密度尺寸。

**Architecture:** `src/widget.py` 會擁有固定的 preset profile，套用後更新 widget 尺寸、layout margins、top row budget、字體、button size 和 lyric line count。`src/tray.py` 新增 `Size` submenu，`src/main.py` 負責把 tray 選擇寫入 config 並套用到 widget。`src/lyric_clamp.py` 支援 `max_lines=1`，讓 Mini 模式只顯示一行歌詞並省略。

**Tech Stack:** Python 3.12, PyQt6, pytest, pytest-qt.

---

## File Structure

| File | Status | Responsibility |
| --- | --- | --- |
| `src/config.py` | Modify | 新增 persisted `size_preset` default |
| `src/lyric_clamp.py` | Modify | 支援 `max_lines=1` 的單行 visual clamp |
| `src/transport_button.py` | Modify | 允許每個 preset 設定 transport button size |
| `src/widget.py` | Modify | 定義 preset profile，套用尺寸、字體、layout budget、lyric line count |
| `src/tray.py` | Modify | 新增 `Size` submenu 和 checked action 狀態 |
| `src/main.py` | Modify | 啟動時套用 config preset；tray 選擇後保存 |
| `tests/test_config.py` | Modify | 測 config default / persistence |
| `tests/test_lyric_clamp.py` | Modify | 測 Mini 一行省略 |
| `tests/test_transport_button.py` | Modify | 測 button 可套不同 size |
| `tests/test_widget.py` | Modify | 測每個 preset 的寬高、字體、行數、top row slot |
| `tests/test_tray.py` | Modify | 測 tray size submenu |
| `tests/test_main.py` | Modify | 測 startup apply preset 和 tray save |
| `spotify_lyrics_widget.md` | Modify | 完成後記錄 V2.03 狀態 |
| `docs/superpowers/plans/2026-05-25-roadmap.md` | Modify | 完成後記錄 V2.03 |

All pytest commands should keep using the repo's safe temp/cache flags:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_03 -q <args>
```

---

## Task 1: Config Persists `size_preset`

**Why:** tray 選擇尺寸後要下次啟動沿用。

**Files:**
- Modify: `src/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Add failing config tests**

Append to `tests/test_config.py`:

```python
def test_size_preset_defaults_to_current(tmp_path):
    config = Config(config_dir=tmp_path)

    assert config.size_preset == "current"


def test_size_preset_persists(tmp_path):
    config = Config(config_dir=tmp_path)
    config.size_preset = "mini"
    config.save()

    config2 = Config(config_dir=tmp_path)

    assert config2.size_preset == "mini"
```

- [ ] **Step 2: Run config tests red**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_03_config -q tests/test_config.py -k size_preset -v
```

Expected: FAIL with `AttributeError` for `size_preset`.

- [ ] **Step 3: Add default field**

In `src/config.py`, add the default after `"netease_fallback": True,`:

```python
        "size_preset": "current",
```

- [ ] **Step 4: Run config tests green**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_03_config -q tests/test_config.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```powershell
git add src/config.py tests/test_config.py
git commit -m "feat: persist widget size preset"
```

---

## Task 2: Mini One-Line Lyric Clamp

**Why:** Mini mode 只顯示一行歌詞，超過寬度用 `...` 省略；Current / Compact / Small 保留兩行。

**Files:**
- Modify: `src/lyric_clamp.py`
- Test: `tests/test_lyric_clamp.py`

- [ ] **Step 1: Add failing one-line clamp tests**

Append to `tests/test_lyric_clamp.py`:

```python
def test_clamp_lyric_text_one_visual_line_elides(qtbot):
    text = "You look away from me and I see something you are trying to hide"
    width = 120

    clamped = clamp_lyric_text(text, _font(), width, max_lines=1)

    assert "\n" not in clamped
    assert clamped.endswith("...")
    assert QFontMetrics(_font()).horizontalAdvance(clamped) <= width


def test_clamp_lyric_text_one_explicit_line_only(qtbot):
    text = "first line\nsecond line"

    clamped = clamp_lyric_text(text, _font(), 300, max_lines=1)

    assert clamped == "first line"
```

- [ ] **Step 2: Run clamp tests red**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_03_clamp -q tests/test_lyric_clamp.py -k "one_visual_line or one_explicit_line" -v
```

Expected: first test FAILS because current implementation can return two lines when `max_lines=1`.

- [ ] **Step 3: Implement one-line clamp**

In `src/lyric_clamp.py`, replace the final wrap branch:

```python
    first_line = visual_lines[0]
    remaining_text = " ".join(line for line in visual_lines[1:] if line)
    second_line = _elide_ascii(remaining_text, QFontMetrics(font), width)
    return f"{first_line}\n{second_line}" if second_line else first_line
```

with:

```python
    if max_lines == 1:
        return _elide_ascii(text.replace("\n", " "), QFontMetrics(font), width)

    first_line = visual_lines[0]
    remaining_text = " ".join(line for line in visual_lines[1:] if line)
    second_line = _elide_ascii(remaining_text, QFontMetrics(font), width)
    return f"{first_line}\n{second_line}" if second_line else first_line
```

- [ ] **Step 4: Run clamp tests green**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_03_clamp -q tests/test_lyric_clamp.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```powershell
git add src/lyric_clamp.py tests/test_lyric_clamp.py
git commit -m "feat: support one-line lyric clamp"
```

---

## Task 3: Transport Buttons Accept Preset Sizes

**Why:** Small / Mini 的 controls slot 比目前窄，transport buttons 需要小幅縮小，但不能用硬編碼 icon 座標剪壞。

**Files:**
- Modify: `src/transport_button.py`
- Test: `tests/test_transport_button.py`

- [ ] **Step 1: Add failing button-size test**

Append to `tests/test_transport_button.py`:

```python
def test_transport_button_can_apply_smaller_size(qtbot):
    from src.transport_button import TransportButton

    button = TransportButton("play")
    qtbot.addWidget(button)

    button.set_button_size(QSize(16, 22))

    assert button.size() == QSize(16, 22)
```

- [ ] **Step 2: Run transport button test red**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_03_button -q tests/test_transport_button.py::test_transport_button_can_apply_smaller_size -v
```

Expected: FAIL with `AttributeError: 'TransportButton' object has no attribute 'set_button_size'`.

- [ ] **Step 3: Add resizable button support**

In `src/transport_button.py`, change the size handling:

```python
BASE_BUTTON_SIZE = QSize(18, 24)
BUTTON_SIZE = BASE_BUTTON_SIZE
```

In `__init__`, before `setFixedSize`:

```python
        self._button_size = BASE_BUTTON_SIZE
```

Replace `self.setFixedSize(BUTTON_SIZE)` in `__init__` with:

```python
        self.setFixedSize(self._button_size)
```

Add:

```python
    def set_button_size(self, size: QSize):
        self._button_size = size
        self.setFixedSize(size)
        self.update()
```

In `set_mode`, replace `self.setFixedSize(BUTTON_SIZE)` with:

```python
        self.setFixedSize(self._button_size)
```

At the start of `paintEvent`, after creating `painter`:

```python
        painter.scale(
            max(1, self.width()) / BASE_BUTTON_SIZE.width(),
            max(1, self.height()) / BASE_BUTTON_SIZE.height(),
        )
```

Keep the existing icon coordinates unchanged; painter scaling maps them to the active button size.

- [ ] **Step 4: Run transport tests green**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_03_button -q tests/test_transport_button.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```powershell
git add src/transport_button.py tests/test_transport_button.py
git commit -m "feat: allow compact transport button sizes"
```

---

## Task 4: Widget Applies Size Presets

**Why:** Widget 是尺寸 preset 的核心：固定寬高、垂直配置、top row 水平 budget、字體、button size、lyric line count 都在這裡套用。

**Files:**
- Modify: `src/widget.py`
- Test: `tests/test_widget.py`

- [ ] **Step 1: Add failing widget preset tests**

Append to `tests/test_widget.py`:

```python
def test_widget_defaults_to_current_size_preset(qtbot):
    from src.widget import LyricsWidget

    widget = LyricsWidget()
    qtbot.addWidget(widget)

    assert widget.size_preset == "current"
    assert widget.size().width() == 420
    assert widget.size().height() == 112


def test_widget_applies_all_size_presets(qtbot):
    from src.widget import SIZE_PRESETS, LyricsWidget

    widget = LyricsWidget()
    qtbot.addWidget(widget)

    for name, preset in SIZE_PRESETS.items():
        widget.apply_size_preset(name)
        assert widget.size().width() == preset.width
        assert widget.size().height() == preset.height
        assert widget._track_label.font().pointSize() == preset.title_font_pt
        assert widget._lyric_label.font().pointSize() == preset.lyric_font_pt
        assert widget._max_lyric_visual_lines == preset.lyric_lines


def test_widget_mini_clamps_lyric_to_one_line(qtbot):
    from src.widget import LyricsWidget

    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.apply_size_preset("mini")
    widget.show()
    qtbot.waitExposed(widget)

    widget.set_lyric_text(
        "You look away from me and I see something you are trying to hide"
    )

    assert "\n" not in widget._lyric_label.text()
    assert widget._lyric_label.text().endswith("...")


def test_size_preset_keeps_title_before_controls(qtbot):
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
        assert title_right < widget._controls_cluster.geometry().left()
        assert widget._controls_cluster.geometry().right() < widget._close_btn.geometry().left()
```

- [ ] **Step 2: Run widget preset tests red**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_03_widget -q tests/test_widget.py -k "size_preset or mini_clamps or title_before_controls" -v
```

Expected: FAIL because `SIZE_PRESETS`, `size_preset`, and `apply_size_preset` do not exist.

- [ ] **Step 3: Add preset data structure**

In `src/widget.py`, add imports:

```python
from dataclasses import dataclass
from PyQt6.QtCore import QSize
```

Add near constants:

```python
@dataclass(frozen=True)
class WidgetSizePreset:
    name: str
    width: int
    height: int
    top_padding: int
    top_row_height: int
    gap_after_top: int
    lyric_lane_height: int
    gap_after_lyric: int
    progress_height: int
    bottom_padding: int
    left_margin: int
    title_width: int
    title_control_gap: int
    controls_width: int
    controls_height: int
    controls_close_gap: int
    close_width: int
    close_height: int
    right_margin: int
    title_font_pt: int
    lyric_font_pt: int
    lyric_lines: int
    button_size: QSize
    controls_spacing: int
    close_font_px: int


SIZE_PRESETS = {
    "current": WidgetSizePreset("current", 420, 112, 12, 24, 5, 56, 5, 2, 8, 16, 282, 14, 66, 24, 12, 20, 20, 10, 10, 16, 2, QSize(18, 24), 6, 14),
    "compact": WidgetSizePreset("compact", 380, 96, 9, 22, 4, 49, 4, 2, 6, 14, 250, 12, 66, 24, 10, 20, 20, 8, 10, 14, 2, QSize(18, 24), 6, 14),
    "small": WidgetSizePreset("small", 340, 84, 7, 20, 3, 46, 3, 1, 5, 12, 224, 10, 58, 22, 8, 18, 18, 10, 9, 12, 2, QSize(16, 22), 5, 12),
    "mini": WidgetSizePreset("mini", 300, 74, 6, 18, 2, 41, 2, 1, 4, 10, 198, 8, 56, 22, 6, 18, 18, 6, 8, 10, 1, QSize(16, 22), 4, 12),
}
DEFAULT_SIZE_PRESET = "current"
```

- [ ] **Step 4: Store layout objects for later updates**

In `_setup_ui()`, replace local `layout`, `top_row`, and `controls_layout` variables with instance attributes:

```python
        self._panel_layout = QVBoxLayout(self._panel)
        self._panel_layout.setContentsMargins(16, 12, 16, 8)
        self._panel_layout.setSpacing(5)
```

Use `self._panel_layout.addWidget(...)` instead of `layout.addWidget(...)`.

Replace:

```python
        top_row = QHBoxLayout(self._top_row)
        top_row.setContentsMargins(0, 0, TOP_ROW_RIGHT_RESERVE, 0)
        top_row.setSpacing(0)
```

with:

```python
        self._top_row_layout = QHBoxLayout(self._top_row)
        self._top_row_layout.setContentsMargins(0, 0, TOP_ROW_RIGHT_RESERVE, 0)
        self._top_row_layout.setSpacing(0)
```

Use `self._top_row_layout.addWidget(...)`.

Replace:

```python
        controls_layout = QHBoxLayout(self._controls_cluster)
```

with:

```python
        self._controls_layout = QHBoxLayout(self._controls_cluster)
```

Use `self._controls_layout.addWidget(...)`.

- [ ] **Step 5: Add `apply_size_preset()`**

In `LyricsWidget.__init__`, after `_setup_timer()`:

```python
        self._size_preset_name = DEFAULT_SIZE_PRESET
        self._max_lyric_visual_lines = SIZE_PRESETS[DEFAULT_SIZE_PRESET].lyric_lines
```

Add methods:

```python
    @property
    def size_preset(self) -> str:
        return self._size_preset_name

    def apply_size_preset(self, name: str):
        preset = SIZE_PRESETS.get(name, SIZE_PRESETS[DEFAULT_SIZE_PRESET])
        self._size_preset_name = preset.name
        self._max_lyric_visual_lines = preset.lyric_lines

        self.setFixedSize(preset.width, preset.height)
        self._panel_layout.setContentsMargins(
            preset.left_margin,
            preset.top_padding,
            preset.right_margin,
            preset.bottom_padding,
        )
        self._panel_layout.setSpacing(preset.gap_after_top)
        self._top_row.setFixedHeight(preset.top_row_height)

        top_row_right_reserve = (
            preset.title_control_gap
            + preset.controls_width
            + preset.controls_close_gap
            + preset.close_width
        )
        self._top_row_layout.setContentsMargins(0, 0, top_row_right_reserve, 0)

        self._track_label.setFont(
            QFont(app_font_family(), preset.title_font_pt, QFont.Weight.DemiBold)
        )
        self._lyric_label.setFont(
            QFont(app_font_family(), preset.lyric_font_pt, QFont.Weight.Bold)
        )
        self._lyric_label.setFixedHeight(preset.lyric_lane_height)
        self._progress_bar.setFixedHeight(preset.progress_height)
        self._controls_cluster.setFixedSize(preset.controls_width, preset.controls_height)
        self._controls_layout.setSpacing(preset.controls_spacing)
        for button in (self._prev_btn, self._play_pause_btn, self._next_btn):
            button.set_button_size(preset.button_size)
        self._close_btn.setFixedSize(preset.close_width, preset.close_height)
        self._close_btn.setStyleSheet(
            f"QPushButton {{ color: {WHITE}; background: transparent; border: none; font-size: {preset.close_font_px}px; }}"
            f"QPushButton:hover {{ color: {SPOTIFY_GREEN}; }}"
        )
        self._position_overlay_controls()
        self.set_lyric_text(self._lyric_label.text())
```

At the end of `_setup_ui()`, replace `_position_overlay_controls()` with:

```python
        self.apply_size_preset(DEFAULT_SIZE_PRESET)
```

- [ ] **Step 6: Update lyric clamp call**

In `set_lyric_text()`, replace:

```python
        text = clamp_lyric_text(text, self._lyric_label.font(), width)
```

with:

```python
        text = clamp_lyric_text(
            text,
            self._lyric_label.font(),
            width,
            max_lines=self._max_lyric_visual_lines,
        )
```

- [ ] **Step 7: Update overlay positioning**

Replace `_position_overlay_controls()` with:

```python
    def _position_overlay_controls(self):
        preset = SIZE_PRESETS.get(self._size_preset_name, SIZE_PRESETS[DEFAULT_SIZE_PRESET])
        controls_x = (
            preset.left_margin
            + preset.title_width
            + preset.title_control_gap
        )
        close_x = controls_x + preset.controls_width + preset.controls_close_gap
        y = preset.top_padding
        self._controls_cluster.move(controls_x, y)
        self._close_btn.move(close_x, y)
```

- [ ] **Step 8: Run widget tests green**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_03_widget -q tests/test_widget.py tests/test_transport_button.py tests/test_lyric_clamp.py -v
```

Expected: PASS. If an existing geometry test expects current values, adjust it to read from `SIZE_PRESETS["current"]`.

- [ ] **Step 9: Commit Task 4**

```powershell
git add src/widget.py tests/test_widget.py
git commit -m "feat: apply fixed widget size presets"
```

---

## Task 5: Tray Size Submenu

**Why:** 使用者先從 tray menu 切換尺寸，不做 resize handle。

**Files:**
- Modify: `src/tray.py`
- Test: `tests/test_tray.py`

- [ ] **Step 1: Add failing tray tests**

Append to `tests/test_tray.py`:

```python
def test_menu_has_size_submenu_with_presets(qtbot):
    tray = _make_tray(on_size_changed=lambda name: None, size_preset="small")

    size_actions = [
        action for action in tray._menu.actions()
        if action.menu() is not None and action.text() == "Size"
    ]
    assert len(size_actions) == 1

    labels = [action.text() for action in tray._size_menu.actions()]
    assert labels == ["Current", "Compact", "Small", "Mini"]
    checked = [action.text() for action in tray._size_menu.actions() if action.isChecked()]
    assert checked == ["Small"]


def test_size_action_calls_callback(qtbot):
    calls = []
    tray = _make_tray(on_size_changed=lambda name: calls.append(name))

    mini_action = next(action for action in tray._size_menu.actions() if action.text() == "Mini")
    mini_action.trigger()

    assert calls == ["mini"]
```

Update `_make_tray()` callbacks:

```python
    callbacks = dict(
        on_activate=_noop,
        on_toggle=_noop,
        on_open_log=_noop,
        on_quit=_noop,
        on_size_changed=_noop,
        size_preset="current",
    )
```

- [ ] **Step 2: Run tray tests red**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_03_tray -q tests/test_tray.py -k size -v
```

Expected: FAIL because `TrayIcon.__init__` does not accept `on_size_changed` / `size_preset`.

- [ ] **Step 3: Implement size submenu**

In `src/tray.py`, update imports:

```python
from PyQt6.QtGui import QActionGroup, QBrush, QColor, QIcon, QPainter, QPixmap
```

Add constants:

```python
SIZE_ACTIONS = [
    ("Current", "current"),
    ("Compact", "compact"),
    ("Small", "small"),
    ("Mini", "mini"),
]
```

Change `TrayIcon.__init__` signature:

```python
    def __init__(
        self,
        on_activate,
        on_toggle,
        on_open_log,
        on_quit,
        on_size_changed=None,
        size_preset: str = "current",
        parent=None,
    ):
```

After the Open log action and before separator:

```python
        self._size_menu = self._menu.addMenu("Size")
        self._size_action_group = QActionGroup(self._size_menu)
        self._size_action_group.setExclusive(True)
        self._size_actions = {}
        for label, value in SIZE_ACTIONS:
            action = self._size_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(value == size_preset)
            self._size_action_group.addAction(action)
            self._size_actions[value] = action
            if on_size_changed is not None:
                action.triggered.connect(
                    lambda checked=False, preset=value: on_size_changed(preset)
                )
```

Add:

```python
    def set_size_preset(self, preset: str):
        if preset in self._size_actions:
            self._size_actions[preset].setChecked(True)
```

- [ ] **Step 4: Run tray tests green**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_03_tray -q tests/test_tray.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 5**

```powershell
git add src/tray.py tests/test_tray.py
git commit -m "feat: add tray size preset menu"
```

---

## Task 6: Main Wiring + Persistence

**Why:** 啟動要套用 config preset，tray 選擇要即時套用並保存。

**Files:**
- Modify: `src/main.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Add failing main tests**

Append to `tests/test_main.py`:

```python
def test_app_applies_config_size_preset_on_init():
    config = MagicMock()
    config.refresh_token = "existing_refresh"
    config.granted_scope = (
        "user-read-currently-playing user-modify-playback-state "
        "user-read-playback-state"
    )
    config.size_preset = "mini"
    widget = MagicMock()

    with (
        patch("src.main.Config", return_value=config),
        patch("src.main.LyricsWidget", return_value=widget),
        patch("src.main.SpotifyWorker", return_value=MagicMock()),
        patch("src.main.LyricsWorker", return_value=MagicMock()),
    ):
        App()

    widget.apply_size_preset.assert_called_once_with("mini")


def test_start_creates_tray_with_size_preset():
    app, config, _ = _make_app()
    config.client_id = "client"
    config.size_preset = "small"
    app._ensure_auth = MagicMock(return_value=True)
    qapp = MagicMock()

    with (
        patch("src.main.QApplication.instance", return_value=qapp),
        patch("src.main.TrayIcon") as tray_class,
    ):
        app.start()

    tray_class.assert_called_once()
    assert tray_class.call_args.kwargs["size_preset"] == "small"
    assert tray_class.call_args.kwargs["on_size_changed"] == app._on_size_preset_changed


def test_size_preset_change_updates_widget_and_config():
    app, config, widget = _make_app()
    app._tray = MagicMock()

    app._on_size_preset_changed("mini")

    widget.apply_size_preset.assert_called_once_with("mini")
    assert config.size_preset == "mini"
    config.save.assert_called_once()
    app._tray.set_size_preset.assert_called_once_with("mini")
```

- [ ] **Step 2: Run main tests red**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_03_main -q tests/test_main.py -k "size_preset" -v
```

Expected: FAIL because `App` does not apply or handle size presets.

- [ ] **Step 3: Apply size preset in `App.__init__`**

In `App.__init__`, after `self._widget = LyricsWidget()`:

```python
        self._widget.apply_size_preset(self._config.size_preset)
```

- [ ] **Step 4: Pass tray size callback**

In `App.start()`, update `TrayIcon(...)` call:

```python
        self._tray = TrayIcon(
            on_activate=self.raise_window,
            on_toggle=self._toggle_widget,
            on_open_log=self._open_log,
            on_quit=app.quit if app is not None else (lambda: None),
            on_size_changed=self._on_size_preset_changed,
            size_preset=self._config.size_preset,
        )
```

- [ ] **Step 5: Add handler**

Add in `App`:

```python
    def _on_size_preset_changed(self, preset: str):
        self._widget.apply_size_preset(preset)
        self._config.size_preset = self._widget.size_preset
        self._config.save()
        if self._tray is not None:
            self._tray.set_size_preset(self._widget.size_preset)
```

- [ ] **Step 6: Preserve size preset during shutdown save**

In `shutdown()`, after setting `window_y`:

```python
        config.size_preset = self._config.size_preset
```

This keeps `shutdown()` from overwriting a newly selected size with the default value when it reloads a fresh `Config`.

- [ ] **Step 7: Run main tests green**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_03_main -q tests/test_main.py -k "size_preset or start_creates_tray" -v
```

Expected: PASS.

- [ ] **Step 8: Commit Task 6**

```powershell
git add src/main.py tests/test_main.py
git commit -m "feat: wire size presets through tray"
```

---

## Task 7: Docs + Full Verification

**Why:** V2.03 is user-visible UI polish; roadmap and handoff should record it.

**Files:**
- Modify: `spotify_lyrics_widget.md`
- Modify: `docs/superpowers/plans/2026-05-25-roadmap.md`

- [ ] **Step 1: Run focused suite**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_03_focus -q tests/test_config.py tests/test_lyric_clamp.py tests/test_transport_button.py tests/test_widget.py tests/test_tray.py tests/test_main.py -v
```

Expected: PASS.

- [ ] **Step 2: Run full suite**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_03_full -q
```

Expected: all tests PASS. Baseline before V2.03 is `206 passed`; final count should be higher after new tests.

- [ ] **Step 3: Manual smoke**

Run:

```powershell
python run.pyw
```

Verify by eye:

1. Tray menu has `Size`.
2. Current / Compact / Small / Mini change widget size immediately.
3. Mini shows one lyric line with `...` when text is too long.
4. Hover controls do not move title in any preset.
5. Long title elides at rest and marquee works on hover.
6. Quit and relaunch restores the chosen preset.

- [ ] **Step 4: Update docs**

In `spotify_lyrics_widget.md`, update:

- Last updated date.
- Current version to `V2.03`.
- Completed list with size presets.
- Latest test record from Step 2.

In `docs/superpowers/plans/2026-05-25-roadmap.md`, add a V2.03 row:

```markdown
| **V2.03** | Size presets / density presets. Tray menu can switch Current, Compact, Small, and Mini. Mini uses one lyric line with ellipsis; other presets keep two visual lyric lines. |
```

- [ ] **Step 5: Commit Task 7**

```powershell
git add spotify_lyrics_widget.md docs/superpowers/plans/2026-05-25-roadmap.md
git commit -m "docs: record V2.03 size presets"
```

---

## Self-Review

**Spec coverage:**

- Fixed Current / Compact / Small / Mini presets: Task 4.
- Current as max/default: Tasks 1 and 4.
- Mini one-line lyric with ellipsis: Tasks 2 and 4.
- No freeform resize / no slider: no resize handle or slider tasks are included.
- Tray `Size` submenu: Task 5.
- Config persistence: Tasks 1 and 6.
- Top row horizontal budget: Task 4 tests title before controls for all presets.
- Full verification and docs: Task 7.

**Placeholder scan:** No `TBD`, `TODO`, placeholder steps, or unspecified "write tests" instructions.

**Type consistency:**

- Preset names are lowercase config values: `current`, `compact`, `small`, `mini`.
- User-facing tray labels are title case: `Current`, `Compact`, `Small`, `Mini`.
- Widget API is `apply_size_preset(name)` and `size_preset`.
- Tray callback is `on_size_changed(preset)`.
- Main handler is `_on_size_preset_changed(preset)`.

## Execution Handoff

Plan complete. Recommended execution is **Inline Execution** in this session, because the tasks touch shared widget/tray/main files and need quick visual/behavior review after implementation.
