# Spotify Lyrics Widget V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add hover-revealed playback controls (play/pause, next, prev) and a hover title marquee with a left-aligned rest state — without reintroducing the content-jumping that V1.2 fixed.

**Architecture:** Playback control HTTP calls run off the UI thread via `QThreadPool`/`QRunnable` (fire-and-forget, silent failure per spec). Adding the `user-modify-playback-state` scope forces a one-time re-auth, detected by comparing a stored `granted_scope` against the required scopes. Control buttons are absolutely-positioned overlay children inside the existing top-right gutter (`OVERLAY_GUTTER_WIDTH`, already reserved for the close button), so the title's available width never changes and nothing reflows. The title becomes a dedicated `MarqueeLabel` that left-aligns and elides at rest, and scrolls the full string (ping-pong) on hover only when it overflows.

**Tech Stack:** Python 3, PyQt6 (`QtCore`, `QtGui`, `QtWidgets`, `QtNetwork` already in use), httpx, pytest + pytest-qt. No new dependencies.

**Prerequisite:** V1.3 is implemented (this plan assumes `app_font_family()` exists and the tray icon is present, but does not depend on them functionally).

---

## File Structure

| File | Status | Responsibility |
|------|--------|----------------|
| `src/auth.py` | Modify | Add `user-modify-playback-state` to `SCOPES`; add `has_required_scopes()` |
| `src/config.py` | Modify | Add `granted_scope` to persisted defaults |
| `src/playback.py` | Create | Pure control-request builder + `PlaybackController` dispatching on `QThreadPool` |
| `src/marquee.py` | Create | `MarqueeLabel`: left-aligned/elided at rest, ping-pong scroll on hover |
| `src/widget.py` | Modify | Title → `MarqueeLabel`; add 3 overlay control buttons + hover show/hide + signals + `set_playing()` |
| `src/main.py` | Modify | Build `PlaybackController`; wire control signals; track `is_playing`; scope-aware `_ensure_auth`; save `granted_scope` |
| `tests/test_auth.py` | Modify | `has_required_scopes` cases |
| `tests/test_playback.py` | Create | Request builder mapping + dispatch-to-pool |
| `tests/test_marquee.py` | Create | Overflow detection, rest vs scroll, ping-pong reversal |
| `tests/test_widget.py` | Modify | Control buttons hover visibility, signals, `set_playing`; update the elide test for `MarqueeLabel` |
| `tests/test_main.py` | Modify | Scope-aware `_ensure_auth`; `granted_scope` saved; control wiring |

**All commands run from the project root.** `pytest.ini` sets `pythonpath = .`, `testpaths = tests`.

---

## Task 1: Add the playback scope with one-time re-auth

**Why:** Controlling playback needs the `user-modify-playback-state` scope. Tokens already stored were granted only `user-read-currently-playing`, so control calls would 403 until the user re-authorizes. Persisting the granted scope and comparing it to the required set lets the app detect the gap on startup and run OAuth once automatically.

**Files:**
- Modify: `src/auth.py:13`, add `has_required_scopes()`
- Modify: `src/config.py:9-16` (add `granted_scope`)
- Modify: `src/main.py` (`_ensure_auth`, `_apply_token_result`)
- Test: `tests/test_auth.py`, `tests/test_main.py`

- [ ] **Step 1: Write the failing test for `has_required_scopes`**

Add to `tests/test_auth.py`:

```python
def test_has_required_scopes_true_when_all_present():
    from src.auth import has_required_scopes

    granted = "user-read-currently-playing user-modify-playback-state"
    required = "user-read-currently-playing user-modify-playback-state"
    assert has_required_scopes(granted, required) is True


def test_has_required_scopes_ignores_order_and_extras():
    from src.auth import has_required_scopes

    granted = "user-modify-playback-state extra-scope user-read-currently-playing"
    required = "user-read-currently-playing user-modify-playback-state"
    assert has_required_scopes(granted, required) is True


def test_has_required_scopes_false_when_missing():
    from src.auth import has_required_scopes

    assert has_required_scopes("user-read-currently-playing", "user-read-currently-playing user-modify-playback-state") is False


def test_has_required_scopes_false_when_empty():
    from src.auth import has_required_scopes

    assert has_required_scopes("", "user-read-currently-playing") is False
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_auth.py -k has_required_scopes -v`
Expected: FAIL with `ImportError: cannot import name 'has_required_scopes'`.

- [ ] **Step 3: Implement the scope change in `src/auth.py`**

Replace line 13:

```python
SCOPES = "user-read-currently-playing user-modify-playback-state"
```

Add this function (e.g. after `is_token_expired`):

```python
def has_required_scopes(granted: str, required: str) -> bool:
    """Whether the granted scope string covers every required scope."""
    granted_set = set(granted.split())
    return all(scope in granted_set for scope in required.split())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_auth.py -k has_required_scopes -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Add `granted_scope` to config**

In `src/config.py`, add to `_DEFAULTS` (after `"token_expires_at": 0,`):

```python
        "granted_scope": "",
```

- [ ] **Step 6: Write the failing tests for scope-aware auth in `tests/test_main.py`**

```python
def test_apply_token_result_saves_granted_scope():
    app, config, _ = _make_app()

    with patch("src.main.time.time", return_value=1000):
        app._apply_token_result(
            {
                "access_token": "a",
                "expires_in": 3600,
                "scope": "user-read-currently-playing user-modify-playback-state",
            }
        )

    assert config.granted_scope == "user-read-currently-playing user-modify-playback-state"


def test_ensure_auth_reauths_when_scope_is_stale():
    app, config, _ = _make_app()
    config.granted_scope = "user-read-currently-playing"  # missing modify scope
    config.token_expires_at = 9_999_999_999  # not expired

    with (
        patch("src.main.run_oauth_flow", return_value={"access_token": "a", "expires_in": 3600, "scope": "user-read-currently-playing user-modify-playback-state"}) as oauth,
        patch("src.main.time.time", return_value=0),
    ):
        assert app._ensure_auth() is True

    oauth.assert_called_once()
```

- [ ] **Step 7: Run the test to verify it fails**

Run: `pytest tests/test_main.py -k "granted_scope or scope_is_stale" -v`
Expected: FAIL — `granted_scope` not saved; `_ensure_auth` still takes the refresh path.

- [ ] **Step 8: Make `_ensure_auth` scope-aware and save the scope in `src/main.py`**

Add to the `src.auth` import line: `has_required_scopes`, `SCOPES`:

```python
from src.auth import SCOPES, has_required_scopes, is_token_expired, refresh_access_token
```

Replace `_ensure_auth` (lines 122-143) with:

```python
    def _ensure_auth(self) -> bool:
        scopes_ok = has_required_scopes(self._config.granted_scope, SCOPES)

        if (
            scopes_ok
            and self._config.refresh_token
            and not is_token_expired(self._config.token_expires_at)
        ):
            return True

        if scopes_ok and self._config.refresh_token:
            try:
                result = refresh_access_token(
                    self._config.refresh_token, self._config.client_id
                )
                self._apply_token_result(result)
                return True
            except Exception:
                pass

        try:
            self._apply_token_result(run_oauth_flow(self._config.client_id))
            return True
        except Exception as error:
            QMessageBox.critical(None, "Auth Failed", str(error))
            return False
```

In `_apply_token_result` (lines 145-150), persist the granted scope. Add before `self._config.save()`:

```python
        if "scope" in result:
            self._config.granted_scope = result["scope"]
```

- [ ] **Step 9: Run the test to verify it passes**

Run: `pytest tests/test_main.py tests/test_auth.py tests/test_config.py -v`
Expected: all PASS.

- [ ] **Step 10: Commit**

```bash
git add src/auth.py src/config.py src/main.py tests/test_auth.py tests/test_main.py
git commit -m "feat: add playback scope with one-time re-auth on scope change (V2)"
```

---

## Task 2: Playback control HTTP layer

**Why:** Control actions must not block the UI thread. A pure request-builder keeps the endpoint mapping testable; `PlaybackController` fires each call on `QThreadPool`. Failures are logged and otherwise silent (spec: "user notices via Spotify app").

**Files:**
- Create: `src/playback.py`
- Test: `tests/test_playback.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_playback.py`:

```python
from src.playback import PlaybackController, build_control_request


def test_toggle_when_playing_pauses():
    assert build_control_request("toggle", is_playing=True) == (
        "PUT",
        "https://api.spotify.com/v1/me/player/pause",
    )


def test_toggle_when_paused_plays():
    assert build_control_request("toggle", is_playing=False) == (
        "PUT",
        "https://api.spotify.com/v1/me/player/play",
    )


def test_next_and_previous():
    assert build_control_request("next", is_playing=False) == (
        "POST",
        "https://api.spotify.com/v1/me/player/next",
    )
    assert build_control_request("previous", is_playing=False) == (
        "POST",
        "https://api.spotify.com/v1/me/player/previous",
    )


class _FakePool:
    def __init__(self):
        self.started = []

    def start(self, runnable):
        self.started.append(runnable)


def test_controller_dispatches_to_pool(qtbot):
    config = type("C", (), {"access_token": "tok"})()
    pool = _FakePool()
    controller = PlaybackController(config, pool=pool)

    controller.next()
    controller.toggle(is_playing=True)

    assert len(pool.started) == 2
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_playback.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.playback'`.

- [ ] **Step 3: Implement `src/playback.py`**

```python
import logging

import httpx
from PyQt6.QtCore import QObject, QRunnable, QThreadPool

_BASE = "https://api.spotify.com/v1/me/player"


def build_control_request(action: str, is_playing: bool) -> tuple[str, str]:
    """Map a control action to an (HTTP method, URL) pair."""
    if action == "toggle":
        return ("PUT", f"{_BASE}/pause") if is_playing else ("PUT", f"{_BASE}/play")
    if action == "next":
        return ("POST", f"{_BASE}/next")
    if action == "previous":
        return ("POST", f"{_BASE}/previous")
    raise ValueError(f"unknown action: {action}")


class _ControlTask(QRunnable):
    def __init__(self, method: str, url: str, access_token: str):
        super().__init__()
        self._method = method
        self._url = url
        self._token = access_token

    def run(self):
        try:
            httpx.request(
                self._method,
                self._url,
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=5.0,
            )
        except Exception:
            logging.exception("Playback control request failed")


class PlaybackController(QObject):
    """Fire-and-forget Spotify playback control off the UI thread."""

    def __init__(self, config, pool=None):
        super().__init__()
        self._config = config
        self._pool = pool or QThreadPool.globalInstance()

    def _dispatch(self, action: str, is_playing: bool = False):
        method, url = build_control_request(action, is_playing)
        self._pool.start(_ControlTask(method, url, self._config.access_token))

    def toggle(self, is_playing: bool):
        self._dispatch("toggle", is_playing)

    def next(self):
        self._dispatch("next")

    def previous(self):
        self._dispatch("previous")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_playback.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/playback.py tests/test_playback.py
git commit -m "feat: add off-thread playback control HTTP layer (V2)"
```

---

## Task 3: Hover playback control buttons in the widget

**Why:** Three flat icon buttons (prev / play-pause / next) overlay the existing top-right gutter and appear on hover alongside the close button — no layout row is added, so the title width is unchanged and nothing reflows (honours V1.2's fixed-geometry rule). The play/pause glyph reflects current state.

**Files:**
- Modify: `src/widget.py` (buttons, positioning, hover, signals, `set_playing`)
- Test: `tests/test_widget.py`
- Modify: `src/main.py` (wire signals, track `is_playing`)
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing tests for the control buttons**

Add to `tests/test_widget.py`:

```python
def test_control_buttons_hidden_at_rest(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    assert widget._prev_btn.isVisible() is False
    assert widget._play_pause_btn.isVisible() is False
    assert widget._next_btn.isVisible() is False


def test_control_buttons_show_on_hover(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.wait(20)
    widget._on_enter_hover()
    assert widget._prev_btn.isVisible() is True
    assert widget._next_btn.isVisible() is True
    widget._on_leave_hover()
    assert widget._prev_btn.isVisible() is False


def test_control_buttons_emit_signals(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)

    with qtbot.waitSignal(widget.next_clicked, timeout=500):
        widget._next_btn.click()
    with qtbot.waitSignal(widget.prev_clicked, timeout=500):
        widget._prev_btn.click()
    with qtbot.waitSignal(widget.play_pause_clicked, timeout=500):
        widget._play_pause_btn.click()


def test_set_playing_swaps_play_pause_glyph(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.set_playing(True)
    playing_glyph = widget._play_pause_btn.text()
    widget.set_playing(False)
    assert widget._play_pause_btn.text() != playing_glyph
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_widget.py -k "control_buttons or set_playing" -v`
Expected: FAIL — `_prev_btn` etc. do not exist.

- [ ] **Step 3: Add the control buttons in `src/widget.py`**

Add signals to the class (next to `close_requested = pyqtSignal()` at line 34):

```python
    prev_clicked = pyqtSignal()
    next_clicked = pyqtSignal()
    play_pause_clicked = pyqtSignal()
```

In `_setup_ui`, after the `_close_btn` block (after line 100, before `layout.addWidget(self._top_row)`), create the three control buttons as children of `self._panel`:

```python
        self._prev_btn = self._make_control_button("⏮")
        self._play_pause_btn = self._make_control_button("▶")
        self._next_btn = self._make_control_button("⏭")
        self._prev_btn.clicked.connect(self.prev_clicked)
        self._play_pause_btn.clicked.connect(self.play_pause_clicked)
        self._next_btn.clicked.connect(self.next_clicked)
        for button in (self._prev_btn, self._play_pause_btn, self._next_btn):
            button.setVisible(False)
```

Add a helper method to the class (near `_position_overlay_controls`):

```python
    def _make_control_button(self, glyph: str) -> QPushButton:
        button = QPushButton(glyph, self._panel)
        button.setFixedSize(20, 20)
        button.setStyleSheet(
            f"QPushButton {{ color: {WHITE}; background: transparent; border: none; font-size: 12px; }}"
            f"QPushButton:hover {{ color: {SPOTIFY_GREEN}; }}"
        )
        return button
```

Position the buttons inside the gutter, left of the close button, in `_position_overlay_controls`. Replace that method (lines 201-207) with:

```python
    def _position_overlay_controls(self):
        panel_width = max(self._panel.width(), self.width())
        if hasattr(self, "_close_btn"):
            self._close_btn.move(panel_width - 30, 8)
        if hasattr(self, "_offline_label"):
            self._offline_label.move(panel_width - OVERLAY_GUTTER_WIDTH, 9)
        if hasattr(self, "_next_btn"):
            # Row of three controls just left of the close button, within the gutter.
            self._next_btn.move(panel_width - 54, 8)
            self._play_pause_btn.move(panel_width - 76, 8)
            self._prev_btn.move(panel_width - 98, 8)
```

Update hover handlers (lines 250-254) to toggle the control buttons too:

```python
    def _on_enter_hover(self):
        self._close_btn.setVisible(True)
        self._prev_btn.setVisible(True)
        self._play_pause_btn.setVisible(True)
        self._next_btn.setVisible(True)

    def _on_leave_hover(self):
        self._close_btn.setVisible(False)
        self._prev_btn.setVisible(False)
        self._play_pause_btn.setVisible(False)
        self._next_btn.setVisible(False)
```

Add `set_playing` (near the other public setters):

```python
    def set_playing(self, is_playing: bool):
        self._play_pause_btn.setText("⏸" if is_playing else "▶")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_widget.py -k "control_buttons or set_playing" -v`
Expected: PASS.

- [ ] **Step 5: Write the failing test for control wiring in `tests/test_main.py`**

```python
def test_connect_signals_wires_playback_controls():
    app, _, widget = _make_app()
    app._playback = MagicMock()

    app._connect_signals()

    widget.next_clicked.connect.assert_called_once_with(app._playback.next)
    widget.prev_clicked.connect.assert_called_once_with(app._playback.previous)


def test_state_synced_updates_play_state():
    app, _, widget = _make_app()
    app._on_state_synced(1000, True, 123.0)
    assert app._is_playing is True
    widget.set_playing.assert_called_with(True)
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `pytest tests/test_main.py -k "playback_controls or play_state" -v`
Expected: FAIL — no `_playback`, no `_is_playing`, signals not wired.

- [ ] **Step 7: Wire playback into `App` in `src/main.py`**

Add import:

```python
from src.playback import PlaybackController
```

In `App.__init__`, after `self._lyrics_worker = LyricsWorker()`:

```python
        self._playback = PlaybackController(self._config)
        self._is_playing = False
```

In `_connect_signals` (after the existing connects), add:

```python
        self._widget.prev_clicked.connect(self._playback.previous)
        self._widget.next_clicked.connect(self._playback.next)
        self._widget.play_pause_clicked.connect(self._on_play_pause_clicked)
```

Update `_on_state_synced` (lines 184-186) to track and reflect play state:

```python
    @pyqtSlot(int, bool, float)
    def _on_state_synced(self, progress_ms: int, is_playing: bool, local_ts: float):
        self._is_playing = is_playing
        self._widget.set_playing(is_playing)
        self._widget.resync_local_timer(progress_ms, is_playing, local_ts)
```

Add the play/pause handler near `raise_window`:

```python
    def _on_play_pause_clicked(self):
        self._playback.toggle(self._is_playing)
```

- [ ] **Step 8: Run the test to verify it passes**

Run: `pytest tests/test_main.py -v`
Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add src/widget.py src/main.py tests/test_widget.py tests/test_main.py
git commit -m "feat: add hover playback control buttons wired to controller (V2)"
```

---

## Task 4: Title left-align + hover marquee

**Why:** The title is currently `AlignCenter` but sits lopsided because only a right gutter is reserved. Left-aligning fixes that and is the natural rest state for a marquee. A dedicated `MarqueeLabel` keeps fixed geometry and clipped painting: elided + left-aligned at rest, slow ping-pong of the full string on hover, and only when the title overflows. It scrolls the rendered string offset (never substring-slices), so CJK/Unicode stays correct.

**Files:**
- Create: `src/marquee.py`
- Test: `tests/test_marquee.py`
- Modify: `src/widget.py` (replace `_track_label` QLabel with `MarqueeLabel`; hover start/stop; track-change reset)
- Modify: `tests/test_widget.py` (update the elide test for `MarqueeLabel`)

- [ ] **Step 1: Write the failing tests for `MarqueeLabel`**

Create `tests/test_marquee.py`:

```python
from PyQt6.QtGui import QFont

from src.marquee import MarqueeLabel


def _label(qtbot, width=100):
    label = MarqueeLabel()
    label.setFont(QFont("Arial", 10))
    label.resize(width, 20)
    qtbot.addWidget(label)
    return label


def test_short_text_does_not_overflow(qtbot):
    label = _label(qtbot, width=400)
    label.setText("hi")
    assert label._overflows() is False


def test_long_text_overflows(qtbot):
    label = _label(qtbot, width=40)
    label.setText("a very long title that will not fit in forty pixels")
    assert label._overflows() is True


def test_start_marquee_only_animates_when_overflowing(qtbot):
    short = _label(qtbot, width=400)
    short.setText("hi")
    short.start_marquee()
    assert short._timer.isActive() is False

    long = _label(qtbot, width=40)
    long.setText("a very long title that will not fit at all here")
    long.start_marquee()
    assert long._timer.isActive() is True
    long.stop_marquee()


def test_stop_marquee_resets_offset(qtbot):
    label = _label(qtbot, width=40)
    label.setText("a very long title that will not fit at all here")
    label.start_marquee()
    label._tick()
    assert label._offset != 0
    label.stop_marquee()
    assert label._offset == 0
    assert label._timer.isActive() is False


def test_tick_reverses_direction_at_end(qtbot):
    label = _label(qtbot, width=40)
    label.setText("a very long title that will not fit at all here")
    label._direction = 1
    for _ in range(2000):
        label._tick()
    # After enough ticks it must have hit the right edge and turned back.
    assert label._direction == -1
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_marquee.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.marquee'`.

- [ ] **Step 3: Implement `src/marquee.py`**

```python
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFontMetrics, QPainter
from PyQt6.QtWidgets import QWidget

_SCROLL_INTERVAL_MS = 40
_STEP_PX = 1


class MarqueeLabel(QWidget):
    """Left-aligned, elided at rest; ping-pong scroll of the full string on hover."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ""
        self._color = QColor("#FFFFFF")
        self._offset = 0
        self._direction = 1
        self._timer = QTimer(self)
        self._timer.setInterval(_SCROLL_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)

    def setText(self, text: str):
        self._text = text
        self._reset_scroll()
        self.update()

    def text(self) -> str:
        return self._text

    def set_color(self, color_hex: str):
        self._color = QColor(color_hex)
        self.update()

    def _text_width(self) -> int:
        return QFontMetrics(self.font()).horizontalAdvance(self._text)

    def _overflows(self) -> bool:
        return self._text_width() > self.width()

    def start_marquee(self):
        if self._overflows() and not self._timer.isActive():
            self._timer.start()

    def stop_marquee(self):
        self._timer.stop()
        self._reset_scroll()
        self.update()

    def _reset_scroll(self):
        self._offset = 0
        self._direction = 1

    def _tick(self):
        max_offset = max(0, self._text_width() - self.width())
        self._offset += self._direction * _STEP_PX
        if self._offset >= max_offset:
            self._offset = max_offset
            self._direction = -1
        elif self._offset <= 0:
            self._offset = 0
            self._direction = 1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(self._color)
        metrics = QFontMetrics(self.font())
        baseline = (self.height() + metrics.ascent() - metrics.descent()) // 2
        if self._timer.isActive():
            painter.drawText(-self._offset, baseline, self._text)
        else:
            elided = metrics.elidedText(
                self._text, Qt.TextElideMode.ElideRight, self.width()
            )
            if elided.endswith("…"):
                elided = f"{elided[:-1]}..."
            painter.drawText(0, baseline, elided)
        painter.end()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_marquee.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Replace the title label with `MarqueeLabel` in `src/widget.py`**

Add the import (after `from src.fonts import app_font_family`):

```python
from src.marquee import MarqueeLabel
```

Replace the `_track_label` construction (lines 86-90) with:

```python
        self._track_label = MarqueeLabel(self._top_row)
        self._track_label.setFont(QFont(app_font_family(), 10, QFont.Weight.DemiBold))
        self._track_label.set_color(WHITE)
        top_row.addWidget(self._track_label, stretch=1)
        top_row.addSpacing(OVERLAY_GUTTER_WIDTH)
```

Simplify `update_track_info` (lines 141-143) — the marquee handles eliding, so just set the text:

```python
    def update_track_info(self, track_name: str, artist_name: str):
        self._track_text_full = f"{track_name} — {artist_name}"
        self._track_label.setText(self._track_text_full)
```

Delete the now-unused `_refresh_track_label_text` method (lines 209-226) and its two call sites in `showEvent` (line 266) and `resizeEvent` (line 271). The `MarqueeLabel` re-elides itself on paint when resized.

Start/stop the marquee on hover. Update `_on_enter_hover` / `_on_leave_hover`:

```python
    def _on_enter_hover(self):
        self._close_btn.setVisible(True)
        self._prev_btn.setVisible(True)
        self._play_pause_btn.setVisible(True)
        self._next_btn.setVisible(True)
        self._track_label.start_marquee()

    def _on_leave_hover(self):
        self._close_btn.setVisible(False)
        self._prev_btn.setVisible(False)
        self._play_pause_btn.setVisible(False)
        self._next_btn.setVisible(False)
        self._track_label.stop_marquee()
```

Reset the marquee on track change: `setText` already resets scroll, so no extra work — confirm `update_track_info` calls `setText`.

- [ ] **Step 6: Update the elide test in `tests/test_widget.py`**

The old `test_long_track_info_elides_without_resizing_widget` asserted `widget._track_label.text().endswith("...")`. `MarqueeLabel.text()` now returns the full (un-elided) string, and eliding happens at paint. Replace that test with one that verifies fixed width + overflow detection:

```python
def test_long_track_info_keeps_width_and_overflows(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.wait(50)
    initial_width = widget.width()

    widget.update_track_info(
        "This Is An Extremely Long Track Name That Should Not Fit In The Widget",
        "An Extremely Long Artist Name That Should Also Be Elided",
    )
    qtbot.wait(50)

    assert widget.width() == initial_width
    assert widget._track_label.text().startswith("This Is An Extremely Long")
    assert widget._track_label._overflows() is True
```

- [ ] **Step 7: Run the affected suites to verify they pass**

Run: `pytest tests/test_widget.py tests/test_marquee.py -v`
Expected: all PASS.

- [ ] **Step 8: Run the full suite**

Run: `pytest -v`
Expected: all PASS.

- [ ] **Step 9: Manual verification**

Run `pythonw run.pyw`. Verify:
1. **One-time re-auth:** on first launch after upgrading, the browser opens for re-authorization (because the stored scope lacks `user-modify-playback-state`). After approving, it does not prompt again on subsequent launches.
2. **Controls (Spotify Premium required):** hover the widget — ⏮ ▶/⏸ ⏭ appear in the top-right next to ✕, and the lyric line stays fully visible (no downward shift). Click play/pause — Spotify toggles and the glyph updates within ~1s. Next/prev change tracks. Leave hover — controls disappear.
3. **Title at rest:** the title is left-aligned (not centered), and a long title shows `...` at the right.
4. **Marquee:** hover a track whose title is long enough to overflow — the title scrolls (slow ping-pong) and stops/resets on leave and on track change. A short title does not scroll.
5. **No jumping:** widget height/width never change across hover, track change, or play/pause.

- [ ] **Step 10: Commit**

```bash
git add src/marquee.py src/widget.py tests/test_marquee.py tests/test_widget.py
git commit -m "feat: left-align title + hover ping-pong marquee (V2)"
```

---

## Self-Review

**Spec coverage** (against updated `2026-05-22-...-design.md` → "V2 — Playback Controls & Title Marquee"):
- Hover control row (play/pause, next, prev) → Task 3 (overlay in gutter, no reflow per the layout decision) + Task 2 (HTTP).
- OAuth scope `user-modify-playback-state` only → Task 1 (playlist scopes explicitly not added).
- Title left-align at rest → Task 4 Step 5.
- Hover marquee, full-string scroll, overflow-only, CJK-safe → Task 4 (`MarqueeLabel`, offset-based, never substring-slices).
- Playlist add/picker → correctly absent (deferred phase per the spec).

**Placeholder scan:** No "TBD"/"handle errors"/"similar to" placeholders; all steps carry complete code.

**Type/name consistency:** `has_required_scopes(granted, required)` and `SCOPES` defined in Task 1, imported/used in `main.py` and tested. `build_control_request(action, is_playing)` and `PlaybackController(config, pool=None)` with `.toggle/.next/.previous` consistent across Task 2 module, tests, and Task 3 wiring (`self._playback.next`, `.previous`, `_on_play_pause_clicked` → `.toggle`). Widget signals `prev_clicked`/`next_clicked`/`play_pause_clicked` and `set_playing()` defined in Task 3 and consumed in `main.py` Step 7 + tests. `MarqueeLabel.setText/text/start_marquee/stop_marquee/_overflows/_tick/_offset/_direction/_timer` consistent between Task 4 module, its tests, and the widget integration.

**Cross-task ordering:** Task 1 (scope) is independent. Task 2 (HTTP) is independent. Task 3 depends on Task 2 (wires controller). Task 4 is independent of 1–3 but shares `widget.py` hover handlers with Task 3 — Step 5 of Task 4 shows the merged hover handlers, so do Task 3 before Task 4.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-26-spotify-lyrics-widget-v2.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks.

**2. Inline Execution** — execute in this session with checkpoints.

**Which approach?** (Note: not for now — V1.3 should ship first, and the V1.4 spec still needs your input.)
