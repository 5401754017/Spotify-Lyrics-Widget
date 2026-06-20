# Widget Hover Settings Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the widget playback controls with hover-only settings, hide, and quit controls while keeping the tray as the fallback show/hide and quit entry point.

**Architecture:** Size selection moves from the tray menu into the widget hover controls. Playback control wiring is removed from the widget and app controller because playback is now handled by Spotify/taskbar controls. The tray becomes a small fallback menu with only show/hide and quit behavior.

**Tech Stack:** Python, PyQt6, pytest, pytest-qt, Windows system tray.

---

## Current Confirmed State

- Performance-saving work is already committed as `421a20b perf: reduce idle polling overhead`.
- Full verification for that commit passed with `python -m pytest -q` reporting `252 passed`.
- No extra performance documentation is needed right now because the behavior is covered by tests and the commit is narrow.

## Intended UI

```text
[ song title                         gear   -   x ]
[ lyric line                                       ]
[ progress                                         ]
```

Hover behavior:

- The three right-side controls are hidden by default.
- Hovering the widget shows `gear`, `-`, and `x`.
- `gear` opens the size menu: `Small`, `Medium`, `Large`.
- `-` hides the widget but keeps the app running in the tray.
- `x` exits the whole program through the current close path.

Tray behavior:

```text
Open / Hide
Quit
```

- Single-clicking the tray icon still toggles show/hide.
- The tray no longer owns size selection.

## Files And Responsibilities

- Modify `src/widget.py`
  - Remove playback button imports, signals, widgets, and layout.
  - Add hover-only settings, hide, and close buttons.
  - Emit widget-level signals for hide and size preset changes.
  - Keep layout stable across hover and across all size presets.

- Modify `src/main.py`
  - Remove `PlaybackController` construction and playback button signal wiring.
  - Wire widget hide requests to the existing hide/show behavior.
  - Wire widget size requests to `_on_size_preset_changed`.
  - Stop telling the tray about size preset changes.

- Modify `src/tray.py`
  - Remove size submenu state.
  - Keep tray icon creation and single-click toggle.
  - Add explicit `Open / Hide` menu action and keep `Quit`.

- Modify `tests/test_widget.py`
  - Replace playback-control expectations with settings/hide/close-control expectations.
  - Preserve existing layout stability tests.

- Modify `tests/test_main.py`
  - Replace playback wiring tests with widget settings/hide wiring tests.
  - Update tray constructor expectations.

- Modify `tests/test_tray.py`
  - Replace size menu tests with simplified tray menu tests.

- Delete `src/transport_button.py` and `tests/test_transport_button.py`
  - These become dead code when widget playback controls are removed.

- Keep `src/playback.py` and `tests/test_playback.py` for this pass
  - The Spotify playback API wrapper remains tested but unused by the widget. Deleting it can be a separate cleanup commit after confirming no future playback UI is planned.

## Task 1: Widget Tests For Hover Controls

**Files:**
- Modify: `tests/test_widget.py`

- [ ] **Step 1: Rename the hover visibility test**

Replace `test_transport_controls_are_hover_only_and_do_not_move_title` with:

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

- [ ] **Step 2: Replace the slot-order geometry test**

Replace `test_transport_controls_sit_between_title_and_close_slots` with:

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

- [ ] **Step 3: Replace the title-row alignment test**

Replace `test_transport_controls_align_with_title_row_height` with:

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

- [ ] **Step 4: Replace the title elision test**

Replace `test_title_label_elides_before_transport_controls_slot` with:

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

- [ ] **Step 5: Replace playback button signal tests**

Remove `test_play_pause_button_reflects_playing_state` and `test_transport_buttons_emit_widget_level_signals`. Add:

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

- [ ] **Step 6: Replace size preset layout test**

Replace `test_size_preset_keeps_title_before_controls` with:

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

- [ ] **Step 7: Run the widget test subset and confirm expected failures**

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

## Task 2: Implement Widget Hover Settings, Hide, And Close Controls

**Files:**
- Modify: `src/widget.py`

- [ ] **Step 1: Update imports**

Remove `TransportButton`. Add `QMenu` if it is not already imported:

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

- [ ] **Step 2: Replace control constants**

Replace playback-cluster constants with fixed hover-control slots:

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

- [ ] **Step 3: Replace size preset fields**

Change `WidgetSizePreset` so the control fields are:

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

Remove these fields from the dataclass:

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

- [ ] **Step 4: Update `SIZE_PRESETS` values**

Use these preset tuples so the total reserved right-side width stays close to the current layout:

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

- [ ] **Step 5: Replace widget signals**

Use these widget-level signals:

```python
    close_requested = pyqtSignal()
    hide_requested = pyqtSignal()
    size_preset_requested = pyqtSignal(str)
```

- [ ] **Step 6: Add a tiny button factory inside `_setup_ui`**

Inside `_setup_ui`, before creating the buttons, add:

```python
        def make_control_button(text: str) -> QPushButton:
            button = QPushButton(text, self._panel)
            button.setMouseTracking(True)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setVisible(False)
            return button
```

- [ ] **Step 7: Replace playback control creation**

Remove `_controls_cluster`, `_controls_layout`, `_prev_btn`, `_play_pause_btn`, and `_next_btn`. Create:

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

- [ ] **Step 8: Update `apply_size_preset`**

Replace the right-reserve and button sizing block with:

```python
        top_row_right_reserve = (
            preset.title_control_gap
            + preset.control_width * HOVER_CONTROL_COUNT
            + preset.control_gap * (HOVER_CONTROL_COUNT - 1)
        )
        self._top_row_layout.setContentsMargins(0, 0, top_row_right_reserve, 0)
```

Then style and size the buttons:

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

- [ ] **Step 9: Update `_position_overlay_controls`**

Use explicit right-side slots:

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

- [ ] **Step 10: Remove `set_playing`**

Delete:

```python
    def set_playing(self, is_playing: bool):
        self._play_pause_btn.set_mode("pause" if is_playing else "play")
```

- [ ] **Step 11: Update hover methods**

Replace hover visibility logic with:

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

- [ ] **Step 12: Run widget tests**

Run:

```powershell
python -m pytest tests/test_widget.py -q
```

Expected:

```text
tests/test_widget.py ... passed
```

- [ ] **Step 13: Commit widget-only work**

Run:

```powershell
git add src/widget.py tests/test_widget.py
git commit -m "feat: add widget hover settings controls"
```

## Task 3: Main App Wiring Without Playback Buttons

**Files:**
- Modify: `tests/test_main.py`
- Modify: `src/main.py`

- [ ] **Step 1: Update `_make_app` setup in tests**

No test should expect `PlaybackController` to be created for widget buttons. In `_make_app`, keep the existing patches for config, widget, SpotifyWorker, and LyricsWorker. Do not patch `src.main.PlaybackController`.

- [ ] **Step 2: Replace playback wiring test**

Replace `test_connect_signals_wires_playback_controls` with:

```python
def test_connect_signals_wires_widget_hide_and_size_controls():
    app, _, widget = _make_app()

    app._connect_signals()

    widget.hide_requested.connect.assert_called_once_with(app._toggle_widget)
    widget.size_preset_requested.connect.assert_called_once_with(
        app._on_size_preset_changed
    )
```

- [ ] **Step 3: Remove play/pause click test**

Delete `test_play_pause_click_uses_latest_play_state`.

- [ ] **Step 4: Replace playing-icon state test**

Replace `test_state_sync_updates_widget_playing_icon` with:

```python
def test_state_sync_resyncs_widget_timer_without_playing_icon():
    app, _, widget = _make_app()

    app._on_state_synced(1234, True, 10.0)

    assert app._is_playing is True
    widget.resync_local_timer.assert_called_once_with(1234, True, 10.0)
    widget.set_playing.assert_not_called()
```

- [ ] **Step 5: Update tray constructor test**

Change `test_start_creates_and_shows_tray` expected constructor call to:

```python
    tray_class.assert_called_once_with(
        on_toggle=app._toggle_widget,
        on_quit=qapp.quit,
    )
```

- [ ] **Step 6: Replace tray size-preset constructor test**

Replace `test_start_creates_tray_with_size_preset` with:

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

- [ ] **Step 7: Update size-preset change test**

In `test_size_preset_change_updates_widget_and_config`, remove tray expectations:

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

- [ ] **Step 8: Run main tests and confirm expected failures**

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

- [ ] **Step 9: Remove playback controller from app code**

In `src/main.py`, remove:

```python
from src.playback import PlaybackController
```

Remove from `App.__init__`:

```python
        self._playback = PlaybackController(self._config)
```

- [ ] **Step 10: Simplify tray construction**

Replace the `TrayIcon` call in `start` with:

```python
        self._tray = TrayIcon(
            on_toggle=self._toggle_widget,
            on_quit=app.quit if app is not None else (lambda: None),
        )
```

- [ ] **Step 11: Replace widget signal wiring**

In `_connect_signals`, remove:

```python
        self._widget.prev_clicked.connect(self._playback.previous)
        self._widget.next_clicked.connect(self._playback.next)
        self._widget.play_pause_clicked.connect(self._on_play_pause_clicked)
```

Add:

```python
        self._widget.hide_requested.connect(self._toggle_widget)
        self._widget.size_preset_requested.connect(self._on_size_preset_changed)
```

- [ ] **Step 12: Remove playback icon updates**

In `_on_state_synced`, remove:

```python
        self._widget.set_playing(is_playing)
```

In `_on_playback_toggled`, remove:

```python
        self._widget.set_playing(is_playing)
```

- [ ] **Step 13: Delete `_on_play_pause_clicked`**

Remove the whole method:

```python
    @pyqtSlot()
    def _on_play_pause_clicked(self):
        self._playback.toggle(self._is_playing)
        self._is_playing = not self._is_playing
        self._widget.set_playing(self._is_playing)
```

- [ ] **Step 14: Stop syncing tray size state**

In `_on_size_preset_changed`, remove:

```python
        if self._tray is not None:
            self._tray.set_size_preset(self._widget.size_preset)
```

- [ ] **Step 15: Run main tests**

Run:

```powershell
python -m pytest tests/test_main.py -q
```

Expected:

```text
tests/test_main.py ... passed
```

- [ ] **Step 16: Commit main wiring**

Run:

```powershell
git add src/main.py tests/test_main.py
git commit -m "refactor: remove widget playback control wiring"
```

## Task 4: Simplify Tray Menu

**Files:**
- Modify: `tests/test_tray.py`
- Modify: `src/tray.py`

- [ ] **Step 1: Update tray test factory**

Replace `_make_tray` with:

```python
def _make_tray(**overrides):
    callbacks = dict(
        on_toggle=_noop,
        on_quit=_noop,
    )
    callbacks.update(overrides)
    return TrayIcon(**callbacks)
```

- [ ] **Step 2: Replace tray menu tests**

Replace `test_menu_has_size_and_quit`, `test_menu_has_size_submenu_with_presets`, and `test_size_action_calls_callback` with:

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

- [ ] **Step 3: Run tray tests and confirm expected failures**

Run:

```powershell
python -m pytest tests/test_tray.py -q
```

Expected before implementation:

```text
FAILED tests/test_tray.py::test_menu_has_open_hide_and_quit
FAILED tests/test_tray.py::test_open_hide_menu_action_calls_on_toggle
```

- [ ] **Step 4: Remove size menu code from tray**

In `src/tray.py`, remove:

```python
from PyQt6.QtGui import QActionGroup, QIcon
```

Use:

```python
from PyQt6.QtGui import QIcon
```

Remove:

```python
SIZE_ACTIONS = [
    ("Small", "small"),
    ("Medium", "medium"),
    ("Large", "large"),
]
```

- [ ] **Step 5: Simplify `TrayIcon.__init__`**

Use this constructor:

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

- [ ] **Step 6: Remove tray size sync API**

Delete:

```python
    def set_size_preset(self, preset: str):
        if preset in self._size_actions:
            self._size_actions[preset].setChecked(True)
```

- [ ] **Step 7: Run tray tests**

Run:

```powershell
python -m pytest tests/test_tray.py -q
```

Expected:

```text
tests/test_tray.py ... passed
```

- [ ] **Step 8: Commit tray simplification**

Run:

```powershell
git add src/tray.py tests/test_tray.py
git commit -m "refactor: simplify tray menu"
```

## Task 5: Delete Dead Transport Button Module

**Files:**
- Delete: `src/transport_button.py`
- Delete: `tests/test_transport_button.py`

- [ ] **Step 1: Confirm no production imports remain**

Run:

```powershell
rg -n "TransportButton|transport_button" src tests
```

Expected:

```text
tests/test_transport_button.py:...
```

Only the test file should remain before deletion.

- [ ] **Step 2: Delete dead files**

Run as separate commands:

```powershell
Remove-Item -LiteralPath src\transport_button.py
```

```powershell
Remove-Item -LiteralPath tests\test_transport_button.py
```

- [ ] **Step 3: Confirm no imports remain**

Run:

```powershell
rg -n "TransportButton|transport_button" src tests
```

Expected:

```text
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
python -m pytest tests/test_widget.py tests/test_main.py tests/test_tray.py -q
```

Expected:

```text
tests/test_widget.py tests/test_main.py tests/test_tray.py ... passed
```

- [ ] **Step 5: Commit deletion**

Run:

```powershell
git add src/transport_button.py tests/test_transport_button.py
git commit -m "refactor: remove unused transport button"
```

## Task 6: Full Verification

**Files:**
- No code edits.

- [ ] **Step 1: Run full test suite**

Run:

```powershell
python -m pytest -q
```

Expected:

```text
passed
```

- [ ] **Step 2: Confirm git state**

Run:

```powershell
git status --short
```

Expected:

```text
```

- [ ] **Step 3: Manual desktop verification**

Launch the app with the normal local command used during development. Verify:

```text
1. Widget launches and lyrics still update.
2. Hover shows gear, -, and x without moving title, lyric, or progress bar.
3. Gear opens Small / Medium / Large.
4. Choosing each size changes the widget and persists after restart.
5. - hides the widget and the tray icon can restore it.
6. x exits the app and leaves no running widget process.
7. Tray menu shows only Open / Hide and Quit.
8. Tray single-click still toggles widget visibility.
```

- [ ] **Step 4: Final commit check**

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

## Self-Review

- Spec coverage:
  - Widget settings popup is covered by Task 1 and Task 2.
  - Widget hide button is covered by Task 1, Task 2, and Task 3.
  - Close button keeps the existing close path through `self.close()` and `close_requested`.
  - Tray show/hide fallback is covered by Task 3 and Task 4.
  - Playback controls are removed from widget and app wiring in Task 2 and Task 3.

- Placeholder scan:
  - No task depends on an unspecified future decision.
  - The only intentionally deferred cleanup is deleting `src/playback.py`, because the tested API wrapper may still be useful if playback controls return later.

- Type consistency:
  - `hide_requested` is a no-argument signal.
  - `size_preset_requested` emits the preset string used by `_on_size_preset_changed`.
  - The widget button names are `_settings_btn`, `_hide_btn`, and `_close_btn` across tests and implementation.
