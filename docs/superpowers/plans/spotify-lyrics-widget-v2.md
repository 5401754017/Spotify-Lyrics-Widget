# Spotify Lyrics Widget V2 Playback Controls + Marquee Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add hover-only Spotify-style playback controls and a hover-only long-title marquee without changing the widget's fixed 420x112 footprint or reintroducing layout jumps.

**Architecture:** Playback API calls run off the UI thread through `QThreadPool`/`QRunnable`; duplicate in-flight clicks are dropped and 429 responses set a local cooldown. The widget top row remains dark and fixed-height: title text is left-aligned, transport controls are absolute overlays visible only on hover, and the close button remains in its own far-right slot. The title uses a dedicated `MarqueeLabel` that elides at rest and scrolls only overflowing text while hovered.

**Tech Stack:** Python 3.12, PyQt6, httpx, pytest, pytest-qt. No new third-party dependencies.

**Revision note (2026-05-31 / renamed 2026-06-01):** This canonical V2 file contains the revised 2026-05-30 Claude x Codex plan. It replaced the old dated `2026-05-26-spotify-lyrics-widget-v2.md` path so future agents do not mistake the filename for an outdated plan. The previous 2026-05-26 content assumed fixed percentage top-row slots, predated V1.4/V1.5, and did not reflect the final user decisions: controls only appear on widget hover, individual button hover turns icons Spotify green, the center button uses play/pause glyphs, and lyrics stay Spotify green for V2.

---

## Current Baseline

- Branch baseline: `master` after V1.4/V1.5 merge, at V1.5 commit `60f380e`. The revised plan was drafted on `codex-v2-plan` at `3bba0dd`, folded into the dated V2 plan, then renamed to this stable canonical path.
- Current widget: fixed `420x112`, dark opaque frameless window, DWM rounded corners and Spotify-green DWM border.
- Current top row: centered `QLabel`, `OVERLAY_GUTTER_WIDTH = 92`, hover-only close button absolutely positioned at the top right.
- Current lyric lane: fixed `60px`, Spotify-green lyric/status text.
- Current progress bar: `2px`, Spotify-green fill.
- V1.5 logging is already in place; playback-control failures should use the same "concrete reason in log" style.

All pytest commands in this plan must avoid the broken default temp/cache path on this machine:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2 -q <args>
```

---

## Claude x Codex Consensus (2026-05-30)

User decisions:

- Playback controls are visible only on widget hover.
- Top-row layout may be redesigned; do not preserve the old 5-50 / 60-80 / 90-95 percentage slots.
- Controls should visually follow Spotify: previous, circular play/pause, next.
- Center button shows a play triangle when paused and two vertical pause bars while playing.
- Playlist add/picker, edge snap, and draggable width/resize are out of scope.

Final visual decision:

- Top row stays dark, not green.
- Title and transport icons are white by default.
- Individual button hover turns the icon Spotify green.
- Center play/pause button is a dark circle with a white icon by default; only the icon turns green on button hover.
- Lyrics stay Spotify green for V2. White lyrics are a later small visual tweak if desired.

Rejected/parked alternatives:

- Full Spotify-green top row: rejected for V2 because the tiny widget would read as stacked green bands (DWM border + top row + progress bar), and white text on `#1DB954` has weak contrast.
- Solid green center button: rejected for V2 because the border, lyrics, and progress already carry the green accent. A dark circle with hover-green icon is closer to Spotify's compact-player style.
- Playlist add/picker: deferred to a later version and must not be partially implemented here.

Top-row geometry consensus:

```text
Widget width: 420
Panel horizontal margins: 16 + 16
Usable content width: 388

0   16                         174        246                 390 410 420
|   title text, left aligned   | controls | title can elide   | X |   |
                                  prev play next
```

Implementation rule: controls and close button are absolute children of the panel/top area, not layout widgets. The title remains left-aligned in the layout and elides before the close button. Hiding/showing controls must not change the title label geometry, lyric lane geometry, or widget size. The controls sit visually above the top row only while hovered.

Height consensus:

```text
Original: TOP_ROW_HEIGHT 20 + LYRIC_LANE_HEIGHT 60 = 80
V2:       TOP_ROW_HEIGHT 24 + LYRIC_LANE_HEIGHT 56 = 80
```

The total widget height remains `112`.

---

## File Structure

| File | Status | Responsibility |
|------|--------|----------------|
| `src/auth.py` | Modify | Add `user-modify-playback-state`; add `has_required_scopes()` |
| `src/config.py` | Modify | Add `granted_scope` default/persistence |
| `src/playback.py` | Create | Build and dispatch playback-control HTTP requests off UI thread |
| `src/transport_button.py` | Create | Custom-painted Spotify-style previous/play/pause/next buttons |
| `src/marquee.py` | Create | `MarqueeLabel`: left-aligned/elided at rest, ping-pong scroll on hover |
| `src/widget.py` | Modify | Fixed top row, hover controls, play/pause state, marquee title |
| `src/main.py` | Modify | Build `PlaybackController`; wire widget signals; track play state; scope-aware auth |
| `tests/test_auth.py` | Modify | Required-scope helper tests |
| `tests/test_config.py` | Modify | `granted_scope` default/persistence |
| `tests/test_playback.py` | Create | Request mapping, worker dispatch, duplicate drop, 429 cooldown, logging |
| `tests/test_transport_button.py` | Create | Button modes, hover color state, fixed sizes |
| `tests/test_marquee.py` | Create | Overflow detection, hover-only animation, stop/reset |
| `tests/test_widget.py` | Modify | Top-row geometry, hover controls, signals, no layout jump |
| `tests/test_main.py` | Modify | Re-auth when scope stale; save scope; playback wiring |

---

## Task 1: Add Playback Scope + One-Time Reauth

**Why:** Spotify playback control endpoints require `user-modify-playback-state`. Existing refresh tokens may have only `user-read-currently-playing`, so V2 must detect stale scope and run OAuth once instead of producing 403s forever.

**Files:**
- Modify: `src/auth.py`
- Modify: `src/config.py`
- Modify: `src/main.py`
- Test: `tests/test_auth.py`
- Test: `tests/test_config.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Add failing scope helper tests**

Append to `tests/test_auth.py`:

```python
def test_has_required_scopes_true_when_all_present():
    from src.auth import has_required_scopes

    granted = "user-read-currently-playing user-modify-playback-state"
    required = "user-read-currently-playing user-modify-playback-state"

    assert has_required_scopes(granted, required) is True


def test_has_required_scopes_ignores_order_and_extras():
    from src.auth import has_required_scopes

    granted = "extra user-modify-playback-state user-read-currently-playing"
    required = "user-read-currently-playing user-modify-playback-state"

    assert has_required_scopes(granted, required) is True


def test_has_required_scopes_false_when_missing():
    from src.auth import has_required_scopes

    granted = "user-read-currently-playing"
    required = "user-read-currently-playing user-modify-playback-state"

    assert has_required_scopes(granted, required) is False


def test_has_required_scopes_false_when_empty():
    from src.auth import has_required_scopes

    assert has_required_scopes("", "user-read-currently-playing") is False
```

- [ ] **Step 2: Run helper tests red**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2 -q tests/test_auth.py -k has_required_scopes -v
```

Expected: FAIL with `ImportError: cannot import name 'has_required_scopes'`.

- [ ] **Step 3: Implement scope helper in `src/auth.py`**

Change `SCOPES`:

```python
SCOPES = "user-read-currently-playing user-modify-playback-state"
```

Add after `is_token_expired()`:

```python
def has_required_scopes(granted: str, required: str) -> bool:
    """Return whether every required scope is present in the granted string."""
    granted_set = set((granted or "").split())
    return all(scope in granted_set for scope in required.split())
```

- [ ] **Step 4: Run helper tests green**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2 -q tests/test_auth.py -k has_required_scopes -v
```

Expected: PASS.

- [ ] **Step 5: Add failing config test for `granted_scope`**

Append to `tests/test_config.py`:

```python
def test_granted_scope_defaults_to_empty_string(tmp_path):
    from src.config import Config

    config = Config(tmp_path)

    assert config.granted_scope == ""
```

- [ ] **Step 6: Run config test red**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2 -q tests/test_config.py::test_granted_scope_defaults_to_empty_string -v
```

Expected: FAIL with `AttributeError`.

- [ ] **Step 7: Add `granted_scope` to `src/config.py`**

Add after `"token_expires_at": 0,`:

```python
        "granted_scope": "",
```

- [ ] **Step 8: Run config tests green**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2 -q tests/test_config.py -v
```

Expected: PASS.

- [ ] **Step 9: Add failing `App` auth tests**

Append to `tests/test_main.py`:

```python
def test_apply_token_result_saves_granted_scope():
    app, config, _ = _make_app()

    with patch("src.main.time.time", return_value=1000):
        app._apply_token_result(
            {
                "access_token": "access",
                "expires_in": 3600,
                "scope": "user-read-currently-playing user-modify-playback-state",
            }
        )

    assert config.granted_scope == "user-read-currently-playing user-modify-playback-state"
    config.save.assert_called_once()


def test_ensure_auth_reauths_when_scope_is_stale():
    app, config, _ = _make_app()
    config.refresh_token = "existing_refresh"
    config.granted_scope = "user-read-currently-playing"
    config.token_expires_at = 9_999_999_999

    with (
        patch(
            "src.main.run_oauth_flow",
            return_value={
                "access_token": "access",
                "expires_in": 3600,
                "scope": "user-read-currently-playing user-modify-playback-state",
            },
        ) as oauth,
        patch("src.main.refresh_access_token") as refresh,
    ):
        assert app._ensure_auth() is True

    oauth.assert_called_once_with(config.client_id)
    refresh.assert_not_called()
```

- [ ] **Step 10: Run `App` auth tests red**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2 -q tests/test_main.py -k "granted_scope or scope_is_stale" -v
```

Expected: FAIL because `granted_scope` is not saved and stale scope is not checked.

- [ ] **Step 11: Make `_ensure_auth` scope-aware without reintroducing silent except**

In `src/main.py`, change the auth import:

```python
from src.auth import SCOPES, has_required_scopes, is_token_expired, refresh_access_token
```

Replace `_ensure_auth()` with:

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
            except Exception as error:
                logging.warning(
                    "Token pre-refresh failed: %s: %s; falling through to OAuth",
                    type(error).__name__, error,
                )

        try:
            self._apply_token_result(run_oauth_flow(self._config.client_id))
            return True
        except Exception as error:
            QMessageBox.critical(None, "Auth Failed", str(error))
            return False
```

In `_apply_token_result()`, before `self._config.save()`:

```python
        if "scope" in result:
            self._config.granted_scope = result["scope"]
```

- [ ] **Step 12: Run Task 1 tests green**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2 -q tests/test_auth.py tests/test_config.py tests/test_main.py -v
```

Expected: PASS. If `tests/test_main.py` alone crashes with exit `-1073740791`, also run it after `tests/test_widget.py`; record the crash as the known PyQt ordering issue, not a V2 auth failure.

- [ ] **Step 13: Commit Task 1**

```powershell
git add src/auth.py src/config.py src/main.py tests/test_auth.py tests/test_config.py tests/test_main.py
git commit -m "feat: add playback scope with one-time reauth (V2)"
```

---

## Task 2: Playback Control HTTP Layer

**Why:** Playback controls must not block the UI thread and must not hammer Spotify on repeated clicks or 429 responses.

**Files:**
- Create: `src/playback.py`
- Test: `tests/test_playback.py`

- [ ] **Step 1: Create failing playback tests**

Create `tests/test_playback.py`:

```python
import time
from unittest.mock import MagicMock, patch

import httpx


def test_build_control_request_maps_actions():
    from src.playback import build_control_request

    assert build_control_request("toggle", is_playing=True) == (
        "PUT",
        "https://api.spotify.com/v1/me/player/pause",
    )
    assert build_control_request("toggle", is_playing=False) == (
        "PUT",
        "https://api.spotify.com/v1/me/player/play",
    )
    assert build_control_request("next", is_playing=True) == (
        "POST",
        "https://api.spotify.com/v1/me/player/next",
    )
    assert build_control_request("previous", is_playing=True) == (
        "POST",
        "https://api.spotify.com/v1/me/player/previous",
    )


def test_controller_drops_duplicate_while_in_flight():
    from src.playback import PlaybackController

    pool = MagicMock()
    config = MagicMock(access_token="token")
    controller = PlaybackController(config, pool=pool)

    controller.toggle(is_playing=False)
    controller.toggle(is_playing=False)

    assert pool.start.call_count == 1


def test_controller_skips_dispatch_during_cooldown():
    from src.playback import PlaybackController

    pool = MagicMock()
    config = MagicMock(access_token="token")
    controller = PlaybackController(config, pool=pool)

    with patch("src.playback.time.monotonic", return_value=10.0):
        controller._cooldown_until = 20.0
        controller.next()

    pool.start.assert_not_called()


@patch("src.playback.httpx.request")
def test_task_logs_non_2xx_with_capped_body(mock_request, caplog):
    from src.playback import _ControlTask

    mock_request.return_value = MagicMock(status_code=403, text="x" * 400, headers={})
    on_done = MagicMock()
    task = _ControlTask(
        method="PUT",
        url="https://api.spotify.com/v1/me/player/play",
        access_token="token",
        on_done=on_done,
        on_rate_limited=MagicMock(),
    )

    task.run()

    assert any("Playback control failed" in r.message and "403" in r.message for r in caplog.records)
    assert any(len(r.message) < 260 for r in caplog.records if "Playback control failed" in r.message)
    on_done.assert_called_once()


@patch("src.playback.httpx.request")
def test_task_respects_retry_after_on_429(mock_request):
    from src.playback import _ControlTask

    mock_request.return_value = MagicMock(
        status_code=429,
        text="rate limited",
        headers={"Retry-After": "5"},
    )
    on_rate_limited = MagicMock()
    task = _ControlTask(
        method="POST",
        url="https://api.spotify.com/v1/me/player/next",
        access_token="token",
        on_done=MagicMock(),
        on_rate_limited=on_rate_limited,
    )

    task.run()

    on_rate_limited.assert_called_once_with(5)


@patch("src.playback.httpx.request")
def test_task_logs_request_exception(mock_request, caplog):
    from src.playback import _ControlTask

    mock_request.side_effect = httpx.ConnectError("offline")
    task = _ControlTask(
        method="POST",
        url="https://api.spotify.com/v1/me/player/next",
        access_token="token",
        on_done=MagicMock(),
        on_rate_limited=MagicMock(),
    )

    task.run()

    assert any("Playback control request failed" in r.message and "ConnectError" in r.message for r in caplog.records)
```

- [ ] **Step 2: Run playback tests red**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2 -q tests/test_playback.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.playback'`.

- [ ] **Step 3: Implement `src/playback.py`**

Create `src/playback.py`:

```python
import logging
import time
from collections.abc import Callable

import httpx
from PyQt6.QtCore import QRunnable, QThreadPool


PLAY_URL = "https://api.spotify.com/v1/me/player/play"
PAUSE_URL = "https://api.spotify.com/v1/me/player/pause"
NEXT_URL = "https://api.spotify.com/v1/me/player/next"
PREVIOUS_URL = "https://api.spotify.com/v1/me/player/previous"
BODY_SNIPPET_LIMIT = 180
DEFAULT_RETRY_AFTER_SECONDS = 1


def build_control_request(action: str, is_playing: bool) -> tuple[str, str]:
    if action == "toggle":
        return ("PUT", PAUSE_URL if is_playing else PLAY_URL)
    if action == "next":
        return ("POST", NEXT_URL)
    if action == "previous":
        return ("POST", PREVIOUS_URL)
    raise ValueError(f"Unknown playback action: {action}")


class _ControlTask(QRunnable):
    def __init__(
        self,
        method: str,
        url: str,
        access_token: str,
        on_done: Callable[[], None],
        on_rate_limited: Callable[[int], None],
    ):
        super().__init__()
        self.method = method
        self.url = url
        self.access_token = access_token
        self.on_done = on_done
        self.on_rate_limited = on_rate_limited

    def run(self):
        try:
            response = httpx.request(
                self.method,
                self.url,
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5.0,
            )
            if response.status_code == 429:
                retry_after = _parse_retry_after(response)
                self.on_rate_limited(retry_after)
                logging.warning(
                    "Playback control rate limited: %s %s; retry after %s seconds",
                    self.method, self.url, retry_after,
                )
            elif response.status_code >= 300:
                logging.warning(
                    "Playback control failed: %s %s -> %s %s",
                    self.method,
                    self.url,
                    response.status_code,
                    _body_snippet(response.text),
                )
        except Exception as error:
            logging.warning(
                "Playback control request failed: %s %s: %s: %s",
                self.method,
                self.url,
                type(error).__name__,
                error,
            )
        finally:
            self.on_done()


def _parse_retry_after(response) -> int:
    try:
        return max(1, int(response.headers.get("Retry-After", DEFAULT_RETRY_AFTER_SECONDS)))
    except (TypeError, ValueError):
        return DEFAULT_RETRY_AFTER_SECONDS


def _body_snippet(text: str) -> str:
    text = (text or "").replace("\n", " ").strip()
    if len(text) <= BODY_SNIPPET_LIMIT:
        return text
    return f"{text[:BODY_SNIPPET_LIMIT]}..."


class PlaybackController:
    def __init__(self, config, pool=None):
        self._config = config
        self._pool = pool or QThreadPool.globalInstance()
        self._in_flight = False
        self._cooldown_until = 0.0

    def toggle(self, is_playing: bool):
        self._dispatch("toggle", is_playing)

    def next(self):
        self._dispatch("next", True)

    def previous(self):
        self._dispatch("previous", True)

    def _dispatch(self, action: str, is_playing: bool):
        if self._in_flight or time.monotonic() < self._cooldown_until:
            return
        method, url = build_control_request(action, is_playing)
        self._in_flight = True
        self._pool.start(
            _ControlTask(
                method,
                url,
                self._config.access_token,
                on_done=self._mark_done,
                on_rate_limited=self._set_cooldown,
            )
        )

    def _mark_done(self):
        self._in_flight = False

    def _set_cooldown(self, retry_after_seconds: int):
        self._cooldown_until = time.monotonic() + retry_after_seconds
```

- [ ] **Step 4: Run playback tests green**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2 -q tests/test_playback.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```powershell
git add src/playback.py tests/test_playback.py
git commit -m "feat: add playback control dispatcher (V2)"
```

---

## Task 3: Spotify-Style Transport Buttons + Fixed Hover Controls

**Why:** Text glyph buttons are not close enough to the requested Spotify-style controls, and layout-managed controls can shift the title. Custom-painted fixed-size buttons keep the UI compact and stable.

**Files:**
- Create: `src/transport_button.py`
- Modify: `src/widget.py`
- Test: `tests/test_transport_button.py`
- Test: `tests/test_widget.py`

- [ ] **Step 1: Create failing transport button tests**

Create `tests/test_transport_button.py`:

```python
from PyQt6.QtCore import QSize


def test_transport_button_fixed_sizes(qtbot):
    from src.transport_button import TransportButton

    previous = TransportButton("previous")
    play = TransportButton("play")
    qtbot.addWidget(previous)
    qtbot.addWidget(play)

    assert previous.size() == QSize(18, 24)
    assert play.size() == QSize(24, 24)


def test_transport_button_mode_can_switch_between_play_and_pause(qtbot):
    from src.transport_button import TransportButton

    button = TransportButton("play")
    qtbot.addWidget(button)

    button.set_mode("pause")
    assert button.mode == "pause"

    button.set_mode("play")
    assert button.mode == "play"
```

- [ ] **Step 2: Run transport tests red**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2 -q tests/test_transport_button.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/transport_button.py`**

Create `src/transport_button.py`:

```python
from PyQt6.QtCore import QPointF, QSize, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QPushButton


WHITE = "#FFFFFF"
SPOTIFY_GREEN = "#1DB954"
DARK_CIRCLE = "#282828"


class TransportButton(QPushButton):
    """Spotify-style fixed-size transport icon button."""

    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)
        self.setFlat(True)
        self.setStyleSheet("background: transparent; border: none;")
        self.setFixedSize(QSize(24, 24) if mode in {"play", "pause"} else QSize(18, 24))

    def set_mode(self, mode: str):
        if mode not in {"previous", "play", "pause", "next"}:
            raise ValueError(f"Unknown transport button mode: {mode}")
        self.mode = mode
        self.setFixedSize(QSize(24, 24) if mode in {"play", "pause"} else QSize(18, 24))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        icon_color = QColor(SPOTIFY_GREEN if self.underMouse() else WHITE)

        if self.mode in {"play", "pause"}:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(DARK_CIRCLE))
            painter.drawEllipse(0, 0, 24, 24)

        painter.setBrush(icon_color)
        painter.setPen(QPen(icon_color, 2))

        if self.mode == "play":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(
                QPolygonF(
                    [
                        QPointF(10, 7),
                        QPointF(10, 17),
                        QPointF(17, 12),
                    ]
                )
            )
        elif self.mode == "pause":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(8, 7, 3, 10, 1, 1)
            painter.drawRoundedRect(14, 7, 3, 10, 1, 1)
        elif self.mode == "previous":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(3, 7, 2, 10)
            painter.drawPolygon(
                QPolygonF([QPointF(15, 7), QPointF(15, 17), QPointF(6, 12)])
            )
        elif self.mode == "next":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(13, 7, 2, 10)
            painter.drawPolygon(
                QPolygonF([QPointF(3, 7), QPointF(3, 17), QPointF(12, 12)])
            )
```

- [ ] **Step 4: Run transport tests green**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2 -q tests/test_transport_button.py -v
```

Expected: PASS.

- [ ] **Step 5: Add failing widget control tests**

Append to `tests/test_widget.py`:

```python
def test_transport_controls_are_hover_only_and_do_not_move_title(qtbot):
    from src.widget import LyricsWidget

    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    widget.update_track_info("A very long song title that needs eliding", "Artist")

    title_before = widget._track_label.geometry()
    assert not widget._controls_cluster.isVisible()

    widget._on_enter_hover()
    title_hover = widget._track_label.geometry()

    assert widget._controls_cluster.isVisible()
    assert title_hover == title_before

    widget._on_leave_hover()
    assert not widget._controls_cluster.isVisible()
    assert widget._track_label.geometry() == title_before


def test_transport_controls_have_own_center_slot_and_close_has_own_slot(qtbot):
    from src.widget import LyricsWidget

    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    widget._on_enter_hover()

    controls = widget._controls_cluster.geometry()
    close = widget._close_btn.geometry()

    assert 170 <= controls.left() <= 180
    assert controls.width() == 72
    assert close.left() >= 360
    assert controls.right() < close.left()


def test_play_pause_button_reflects_playing_state(qtbot):
    from src.widget import LyricsWidget

    widget = LyricsWidget()
    qtbot.addWidget(widget)

    widget.set_playing(True)
    assert widget._play_pause_btn.mode == "pause"

    widget.set_playing(False)
    assert widget._play_pause_btn.mode == "play"
```

- [ ] **Step 6: Run widget control tests red**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2 -q tests/test_widget.py -k "transport_controls or play_pause_button" -v
```

Expected: FAIL because `_controls_cluster`, `set_playing`, and transport buttons do not exist.

- [ ] **Step 7: Implement fixed top-row controls in `src/widget.py`**

Make these changes:

1. Add import:

```python
from src.transport_button import TransportButton
```

2. Change constants:

```python
TOP_ROW_HEIGHT = 24
LYRIC_LANE_HEIGHT = 56
CONTROLS_CLUSTER_WIDTH = 72
CONTROLS_CLUSTER_HEIGHT = 24
```

Remove `OVERLAY_GUTTER_WIDTH`.

3. Add signals to `LyricsWidget`:

```python
    prev_clicked = pyqtSignal()
    play_pause_clicked = pyqtSignal()
    next_clicked = pyqtSignal()
```

4. In `_setup_ui()`, keep `_top_row` layout title-only:

```python
        self._track_label = QLabel("")
        self._track_label.setFont(QFont(app_font_family(), 10, QFont.Weight.DemiBold))
        self._track_label.setStyleSheet(f"color: {WHITE};")
        self._track_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        top_row.addWidget(self._track_label, stretch=1)
```

5. Create controls as absolute overlay children after `_close_btn`:

```python
        self._controls_cluster = QWidget(self._panel)
        self._controls_cluster.setFixedSize(CONTROLS_CLUSTER_WIDTH, CONTROLS_CLUSTER_HEIGHT)
        self._controls_cluster.setMouseTracking(True)
        controls_layout = QHBoxLayout(self._controls_cluster)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(6)

        self._prev_btn = TransportButton("previous", self._controls_cluster)
        self._play_pause_btn = TransportButton("play", self._controls_cluster)
        self._next_btn = TransportButton("next", self._controls_cluster)
        controls_layout.addWidget(self._prev_btn)
        controls_layout.addWidget(self._play_pause_btn)
        controls_layout.addWidget(self._next_btn)

        self._prev_btn.clicked.connect(self.prev_clicked)
        self._play_pause_btn.clicked.connect(self.play_pause_clicked)
        self._next_btn.clicked.connect(self.next_clicked)
        self._controls_cluster.setVisible(False)
```

6. Replace `_position_overlay_controls()`:

```python
    def _position_overlay_controls(self):
        panel_width = max(self._panel.width(), self.width())
        self._close_btn.move(panel_width - 30, 8)
        controls_x = (panel_width - CONTROLS_CLUSTER_WIDTH) // 2
        self._controls_cluster.move(controls_x, 8)
```

At the V1.5 baseline, `_panel` fills the fixed `420px` widget (`x=0, width=420`), so this places the `72px` controls cluster at `left=174`. The geometry tests assert the cluster's left edge, not its center.

Task 3 does not change `_refresh_track_label_text()`. Title eliding, title width behavior, and marquee behavior are owned by Task 4 after `MarqueeLabel` is introduced.

7. Add `set_playing()`:

```python
    def set_playing(self, is_playing: bool):
        self._play_pause_btn.set_mode("pause" if is_playing else "play")
```

8. Update hover handlers:

```python
    def _on_enter_hover(self):
        self._close_btn.setVisible(True)
        self._controls_cluster.setVisible(True)

    def _on_leave_hover(self):
        if self.underMouse():
            return
        self._close_btn.setVisible(False)
        self._controls_cluster.setVisible(False)
```

- [ ] **Step 8: Run widget control tests green**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2 -q tests/test_widget.py -k "transport_controls or play_pause_button or close_button_visible_on_hover or hover_does_not_move" -v
```

Expected: PASS.

- [ ] **Step 9: Commit Task 3**

```powershell
git add src/transport_button.py src/widget.py tests/test_transport_button.py tests/test_widget.py
git commit -m "feat: add hover-only Spotify transport controls (V2)"
```

---

## Task 4: Hover-Only Title Marquee

**Why:** V2's title lives in a left-aligned top-row slot. Long titles should remain elided at rest and scroll only while hovered, without substring slicing CJK text.

**Files:**
- Create: `src/marquee.py`
- Modify: `src/widget.py`
- Test: `tests/test_marquee.py`
- Test: `tests/test_widget.py`

- [ ] **Step 1: Create failing marquee tests**

Create `tests/test_marquee.py`:

```python
def test_marquee_elides_at_rest(qtbot):
    from src.marquee import MarqueeLabel

    label = MarqueeLabel()
    qtbot.addWidget(label)
    label.resize(80, 24)
    label.setText("a very long title that cannot fit")

    assert label.text() == "a very long title that cannot fit"
    assert label._offset == 0
    assert not label._timer.isActive()


def test_start_marquee_only_animates_when_overflowing(qtbot):
    from src.marquee import MarqueeLabel

    short = MarqueeLabel()
    qtbot.addWidget(short)
    short.resize(300, 24)
    short.setText("short")
    short.start_marquee()
    assert not short._timer.isActive()

    long = MarqueeLabel()
    qtbot.addWidget(long)
    long.resize(80, 24)
    long.setText("這是一首非常非常長的歌名")
    long.start_marquee()
    assert long._timer.isActive()


def test_stop_marquee_resets_offset(qtbot):
    from src.marquee import MarqueeLabel

    label = MarqueeLabel()
    qtbot.addWidget(label)
    label.resize(80, 24)
    label.setText("a very long title that cannot fit")
    label.start_marquee()
    label._offset = 12

    label.stop_marquee()

    assert label._offset == 0
    assert not label._timer.isActive()
```

- [ ] **Step 2: Run marquee tests red**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2 -q tests/test_marquee.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/marquee.py`**

Create `src/marquee.py`:

```python
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QLabel


MARQUEE_INTERVAL_MS = 40
MARQUEE_STEP_PX = 1
MARQUEE_END_PAUSE_TICKS = 18


class MarqueeLabel(QLabel):
    """Left-aligned, elided at rest; ping-pong scroll on hover if overflowing."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._full_text = text
        self._offset = 0
        self._direction = 1
        self._pause_ticks = 0
        self._timer = QTimer(self)
        self._timer.setInterval(MARQUEE_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    def setText(self, text: str):
        self._full_text = text
        self._offset = 0
        self._direction = 1
        self._pause_ticks = 0
        super().setText(text)
        self.update()

    def text(self) -> str:
        return self._full_text

    def start_marquee(self):
        if self._overflows():
            self._timer.start()

    def stop_marquee(self):
        self._timer.stop()
        self._offset = 0
        self._direction = 1
        self._pause_ticks = 0
        self.update()

    def _overflows(self) -> bool:
        return self.fontMetrics().horizontalAdvance(self._full_text) > self.width()

    def _tick(self):
        if not self._overflows():
            self.stop_marquee()
            return
        if self._pause_ticks > 0:
            self._pause_ticks -= 1
            return

        max_offset = max(0, self.fontMetrics().horizontalAdvance(self._full_text) - self.width())
        self._offset += self._direction * MARQUEE_STEP_PX
        if self._offset >= max_offset:
            self._offset = max_offset
            self._direction = -1
            self._pause_ticks = MARQUEE_END_PAUSE_TICKS
        elif self._offset <= 0:
            self._offset = 0
            self._direction = 1
            self._pause_ticks = MARQUEE_END_PAUSE_TICKS
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(self.palette().color(self.foregroundRole()))
        if self._timer.isActive():
            painter.drawText(-self._offset, 0, self.fontMetrics().horizontalAdvance(self._full_text), self.height(), int(self.alignment()), self._full_text)
            return
        elided = self.fontMetrics().elidedText(
            self._full_text,
            Qt.TextElideMode.ElideRight,
            self.width(),
        )
        if elided.endswith("…"):
            elided = f"{elided[:-1]}..."
        painter.drawText(self.rect(), int(self.alignment()), elided)
```

- [ ] **Step 4: Run marquee tests green**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2 -q tests/test_marquee.py -v
```

Expected: PASS.

- [ ] **Step 5: Integrate `MarqueeLabel` in `src/widget.py`**

Change import:

```python
from src.marquee import MarqueeLabel
```

Replace `_track_label = QLabel("")` with:

```python
        self._track_label = MarqueeLabel("")
```

Simplify `update_track_info()`:

```python
    def update_track_info(self, track_name: str, artist_name: str):
        self._track_text_full = f"{track_name} — {artist_name}"
        self._track_label.setText(self._track_text_full)
```

Keep `_refresh_track_label_text()` as a no-op compatibility shim for existing tests/call sites:

```python
    def _refresh_track_label_text(self):
        self._track_label.update()
```

Update hover handlers:

```python
    def _on_enter_hover(self):
        self._close_btn.setVisible(True)
        self._controls_cluster.setVisible(True)
        self._track_label.start_marquee()

    def _on_leave_hover(self):
        if self.underMouse():
            return
        self._close_btn.setVisible(False)
        self._controls_cluster.setVisible(False)
        self._track_label.stop_marquee()
```

- [ ] **Step 6: Update old title-elide test and add widget marquee integration test**

Replace `tests/test_widget.py::test_long_track_info_elides_without_resizing_widget` with:

```python
def test_long_track_info_overflows_without_resizing_widget(qtbot):
    from src.marquee import MarqueeLabel

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
    assert isinstance(widget._track_label, MarqueeLabel)
    assert widget._track_label.text().startswith("This Is An Extremely Long Track Name")
    assert widget._track_label._overflows() is True
```

Append to `tests/test_widget.py`:

```python
def test_hover_starts_and_stops_title_marquee(qtbot):
    from src.widget import LyricsWidget

    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    widget.update_track_info(
        "This is a very long title that should overflow the top row by a wide margin",
        "An equally long artist name",
    )

    widget._on_enter_hover()
    assert widget._track_label._timer.isActive()

    widget._on_leave_hover()
    assert not widget._track_label._timer.isActive()
    assert widget._track_label._offset == 0
```

- [ ] **Step 7: Run marquee + widget tests green**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2 -q tests/test_marquee.py tests/test_widget.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit Task 4**

```powershell
git add src/marquee.py src/widget.py tests/test_marquee.py tests/test_widget.py
git commit -m "feat: add hover title marquee (V2)"
```

---

## Task 5: Wire Controls Into `App`

**Why:** The UI controls must call the playback dispatcher and update the play/pause icon from Spotify's authoritative playback state.

**Files:**
- Modify: `src/main.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Add failing main wiring tests**

Append to `tests/test_main.py`:

```python
def test_connect_signals_wires_playback_controls():
    app, _, widget = _make_app()
    app._playback = MagicMock()

    app._connect_signals()

    widget.prev_clicked.connect.assert_called_once_with(app._playback.previous)
    widget.next_clicked.connect.assert_called_once_with(app._playback.next)
    widget.play_pause_clicked.connect.assert_called_once_with(app._on_play_pause_clicked)


def test_play_pause_click_uses_latest_play_state():
    app, _, _ = _make_app()
    app._playback = MagicMock()
    app._is_playing = True

    app._on_play_pause_clicked()

    app._playback.toggle.assert_called_once_with(True)


def test_state_sync_updates_widget_playing_icon():
    app, _, widget = _make_app()

    app._on_state_synced(1234, True, 10.0)

    assert app._is_playing is True
    widget.set_playing.assert_called_once_with(True)
```

- [ ] **Step 2: Run main wiring tests red**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2 -q tests/test_main.py -k "playback_controls or play_pause_click or state_sync_updates" -v
```

Expected: FAIL because `_playback`, `_is_playing`, and `_on_play_pause_clicked` do not exist.

- [ ] **Step 3: Implement main wiring**

In `src/main.py`, add import:

```python
from src.playback import PlaybackController
```

Keep the existing `pyqtSlot` import from `PyQt6.QtCore`; current `src/main.py` already imports it.

In `App.__init__()`, after creating `_lyrics_worker`:

```python
        self._playback = PlaybackController(self._config)
        self._is_playing = False
```

In `_connect_signals()`, after Spotify worker signal wiring:

```python
        self._widget.prev_clicked.connect(self._playback.previous)
        self._widget.next_clicked.connect(self._playback.next)
        self._widget.play_pause_clicked.connect(self._on_play_pause_clicked)
```

In `_on_state_synced()`:

```python
        self._is_playing = is_playing
        self._widget.set_playing(is_playing)
```

Add:

```python
    @pyqtSlot()
    def _on_play_pause_clicked(self):
        self._playback.toggle(self._is_playing)
```

In `_on_playback_toggled()`:

```python
        self._is_playing = is_playing
        self._widget.set_playing(is_playing)
```

- [ ] **Step 4: Run main wiring tests green**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2 -q tests/test_main.py -k "playback_controls or play_pause_click or state_sync_updates" -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 5**

```powershell
git add src/main.py tests/test_main.py
git commit -m "feat: wire playback controls into app (V2)"
```

---

## Task 6: Full Verification + Roadmap Note

**Why:** V2 changes OAuth, UI layout, worker dispatch, and visual interaction. Finish with automated tests plus a short live verification checklist.

**Files:**
- Modify: `docs/superpowers/plans/2026-05-25-roadmap.md`

- [ ] **Step 1: Run full suite**

Run:

```powershell
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_v2_full -q
```

Expected: all tests PASS. Current baseline before V2 is `161 passed`; V2 should add tests, so the final count will be higher.

- [ ] **Step 2: Manual smoke checklist**

Run the widget from the V2 branch:

```powershell
python run.py
```

Verify:

1. First launch after V2 opens browser for Spotify reauthorization exactly once because stored scope lacks `user-modify-playback-state`.
2. Relaunch after authorizing does not prompt again.
3. Hover shows previous / circular play-pause / next / close; leaving hover hides all controls.
4. Hover previous, play/pause, and next individually; each icon turns Spotify green (`#1DB954`) only while that button is hovered, then returns to white.
5. Hover controls do not move title, lyric lane, or progress bar.
6. Center button shows pause bars while Spotify is playing and play triangle while paused.
7. Clicking play/pause toggles Spotify and updates the icon within the next poll.
8. Next/previous change tracks.
9. Long title is left-aligned and elided at rest; while hovered, it scrolls only if overflowing.
10. Lyrics remain Spotify green.
11. `widget.log` records playback API failures or 429 cooldowns if they occur.

- [ ] **Step 3: Update roadmap**

In `docs/superpowers/plans/2026-05-25-roadmap.md`, update the V2 row after implementation with final V2 commit hashes and this summary:

```markdown
| **V2** | Playback controls + title marquee. Hover-only Spotify-style previous/play-pause/next controls, one-time reauth for `user-modify-playback-state`, off-UI-thread playback requests with duplicate/429 brakes, dark fixed top row with white controls that turn green on button hover, and left-aligned hover marquee for overflowing titles. Playlist features remain deferred. |
```

- [ ] **Step 4: Commit Task 6**

```powershell
git add docs/superpowers/plans/2026-05-25-roadmap.md
git commit -m "docs: record V2 playback controls and marquee verification"
```

---

## Out of Scope

- Playlist add button.
- Playlist picker.
- Playlist OAuth scopes.
- Drag-to-resize width.
- Edge snap.
- White lyrics. Lyrics stay Spotify green in V2; white lyrics can be a later small visual polish.
- Green top-row band.
- Public packaging / PyInstaller.

---

## Self-Review

**Spec coverage:**

- Hover-only controls: Task 3.
- Spotify-style previous/play-pause/next buttons: Task 3.
- Play triangle vs pause bars based on state: Tasks 3 and 5.
- Spotify green as accent on button hover, while lyrics remain green: Task 3.
- One-time reauth for playback scope: Task 1.
- Off-UI-thread playback API calls with duplicate and 429 brakes: Task 2.
- Left-aligned title and hover-only marquee: Task 4.
- No layout jump / fixed 420x112 footprint: Tasks 3, 4, 6.
- V1.5-style concrete logging for failures: Task 2.

**Placeholder scan:** none. Every task includes file paths, test code, implementation snippets, commands, and expected outcomes.

**Type/name consistency:**

- `has_required_scopes(granted, required)` is defined in Task 1 and consumed by `main.py`.
- `PlaybackController.toggle/next/previous` are defined in Task 2 and wired in Task 5.
- `TransportButton.set_mode()` and `.mode` are defined in Task 3 and consumed by `LyricsWidget.set_playing()`.
- `MarqueeLabel.setText/text/start_marquee/stop_marquee` are defined in Task 4 and consumed by `LyricsWidget`.

**Execution order:** Task 1 and Task 2 are independent. Task 3 depends on `TransportButton`. Task 4 modifies the same hover handlers as Task 3, so do Task 3 before Task 4. Task 5 depends on Task 2 and Task 3. Task 6 is final.

---

## Execution Handoff

Plan complete. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, faster iteration.
2. **Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, with checkpoints.
