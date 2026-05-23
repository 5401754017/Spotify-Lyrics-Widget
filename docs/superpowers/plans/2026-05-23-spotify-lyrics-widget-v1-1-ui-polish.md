# Spotify Lyrics Widget V1.1 UI Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish the existing V1 lyrics widget with rounded corners, a green border, stronger track typography, stable hover behavior, and long-title eliding while keeping V2 playback controls / playlist features out of scope.

**Architecture:** Keep V1 module boundaries unchanged. `src/widget.py` remains the only production UI file touched for polish; `src/spotify_worker.py` gets no behavior change, only existing behavior is covered with an additional 204-response test. The widget uses a transparent outer frameless window with a styled inner panel, and the close button becomes an overlay so hover does not reflow labels.

**Tech Stack:** Python 3.12, PyQt6, pytest, pytest-qt

---

## File Structure

Modify only these files:

- `src/widget.py` — UI polish: transparent outer window, rounded inner panel, typography, close overlay, track label eliding.
- `tests/test_widget.py` — tests for style, typography, eliding, and no-jump hover behavior.
- `tests/test_spotify_worker.py` — test existing `204 No Content` idle playback behavior.

Do not add:

- Playback-control UI.
- Playlist UI.
- Spotify scopes.
- Auth changes.
- Packaging files.

---

## Task 1: Cover Spotify 204 No Content Idle State

**Files:**
- Modify: `tests/test_spotify_worker.py`
- Production code expected: none unless the test exposes a real regression in `src/spotify_worker.py`

- [ ] **Step 1: Add the failing or confirming test**

Append this test class to `tests/test_spotify_worker.py`:

```python
class TestSpotifyWorkerIdleResponse:
    @patch("src.spotify_worker.httpx.get")
    def test_204_emits_not_playing_and_resets_previous_state(self, mock_get):
        from src.spotify_worker import SpotifyWorker

        mock_get.return_value = MagicMock(status_code=204, text="")

        mock_config = MagicMock()
        mock_config.token_expires_at = int(time.time()) + 3600
        mock_config.access_token = "valid"

        worker = SpotifyWorker(mock_config)
        worker._previous_state = PlayerState(
            track_id="old",
            track_name="Old Song",
            track_uri="spotify:track:old",
            artist_name="Old Artist",
            album_name="Old Album",
            duration_ms=200000,
            progress_ms=10000,
            is_playing=True,
            is_track=True,
        )
        signals = []
        worker.not_playing.connect(lambda: signals.append("not_playing"))

        worker._poll_once()

        assert signals == ["not_playing"]
        assert worker._previous_state is None
```

- [ ] **Step 2: Run the focused test**

Run:

```bash
pytest tests/test_spotify_worker.py::TestSpotifyWorkerIdleResponse::test_204_emits_not_playing_and_resets_previous_state -v
```

Expected:

- PASS if current V1 behavior already works.
- If it fails, the failure should specifically show that `not_playing` was not emitted or `_previous_state` was not reset.

- [ ] **Step 3: Only if needed, fix `src/spotify_worker.py`**

The existing intended code path is:

```python
if response.status_code == 204 or (
    response.status_code == 200 and not response.text
):
    self.not_playing.emit()
    self._previous_state = None
    return
```

If the test fails, make `src/spotify_worker.py` match that behavior exactly.

- [ ] **Step 4: Run worker tests**

Run:

```bash
pytest tests/test_spotify_worker.py -v
```

Expected: all Spotify worker tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_spotify_worker.py src/spotify_worker.py
git commit -m "test: cover Spotify idle playback response"
```

If `src/spotify_worker.py` is unchanged, stage only `tests/test_spotify_worker.py`.

---

## Task 2: Add Widget Style and Typography Tests

**Files:**
- Modify: `tests/test_widget.py`
- Later production file: `src/widget.py`

- [ ] **Step 1: Add tests for translucent outer window, rounded panel, and stronger track font**

Add these tests to `tests/test_widget.py`:

```python
def test_widget_uses_translucent_outer_and_rounded_panel(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)

    assert widget.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert widget._panel.objectName() == "lyricsPanel"

    panel_style = widget._panel.styleSheet()
    assert "background-color: #121212" in panel_style
    assert "border: 1px solid #1DB954" in panel_style
    assert "border-radius: 12px" in panel_style


def test_track_label_font_is_larger_and_demibold(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)

    font = widget._track_label.font()
    assert font.pointSize() >= 10
    assert font.weight() >= QFont.Weight.DemiBold.value
```

Also add this import at the top of `tests/test_widget.py`:

```python
from PyQt6.QtGui import QFont
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_widget.py::test_widget_uses_translucent_outer_and_rounded_panel tests/test_widget.py::test_track_label_font_is_larger_and_demibold -v
```

Expected:

- `test_widget_uses_translucent_outer_and_rounded_panel` FAILS because `_panel` does not exist and the outer widget is not translucent.
- `test_track_label_font_is_larger_and_demibold` FAILS because V1 uses size 9 regular track text.

---

## Task 3: Implement Rounded Inner Panel and Track Typography

**Files:**
- Modify: `src/widget.py`
- Test: `tests/test_widget.py`

- [ ] **Step 1: Update imports**

In `src/widget.py`, add `QFrame`:

```python
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
```

- [ ] **Step 2: Update color constants**

Replace:

```python
BLACK = "#000000"
```

with:

```python
PANEL_BACKGROUND = "#121212"
```

Keep:

```python
WHITE = "#FFFFFF"
SPOTIFY_GREEN = "#1DB954"
DARK_GRAY = "#282828"
```

- [ ] **Step 3: Make the outer window transparent**

In `_setup_window`, replace:

```python
self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
self.setFixedWidth(420)
self.setStyleSheet(f"background-color: {BLACK};")
```

with:

```python
self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
self.setFixedWidth(420)
self.setStyleSheet("background-color: transparent;")
```

- [ ] **Step 4: Put existing content inside `_panel`**

Rewrite the start of `_setup_ui` so the outer widget layout owns one panel:

```python
outer_layout = QVBoxLayout()
outer_layout.setContentsMargins(0, 0, 0, 0)
outer_layout.setSpacing(0)

self._panel = QFrame(self)
self._panel.setObjectName("lyricsPanel")
self._panel.setMouseTracking(True)
self._panel.setStyleSheet(
    f"#lyricsPanel {{ background-color: {PANEL_BACKGROUND}; "
    f"border: 1px solid {SPOTIFY_GREEN}; border-radius: 12px; }}"
)

layout = QVBoxLayout(self._panel)
layout.setContentsMargins(16, 12, 16, 8)
layout.setSpacing(5)
outer_layout.addWidget(self._panel)
self.setLayout(outer_layout)
```

Then keep adding `top_row`, `_track_label`, `_offline_label`, `_lyric_label`, and `_progress_bar` to `layout`.

Remove the old final line:

```python
self.setLayout(layout)
```

- [ ] **Step 5: Update track label font**

Replace:

```python
self._track_label.setFont(QFont("Segoe UI", 9))
```

with:

```python
self._track_label.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
self._track_label.setSingleLine(True)
```

- [ ] **Step 6: Run focused style tests**

Run:

```bash
pytest tests/test_widget.py::test_widget_uses_translucent_outer_and_rounded_panel tests/test_widget.py::test_track_label_font_is_larger_and_demibold -v
```

Expected: both tests PASS.

- [ ] **Step 7: Run full widget tests**

Run:

```bash
pytest tests/test_widget.py -v
```

Expected: existing widget tests may fail only where hover still reflows. Those failures are addressed in Task 4.

---

## Task 4: Add Hover No-Jump Tests and Overlay Close Button

**Files:**
- Modify: `tests/test_widget.py`
- Modify: `src/widget.py`

- [ ] **Step 1: Add no-jump hover tests**

Add this helper and tests to `tests/test_widget.py`:

```python
def _shown_widget(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.update_track_info("Stable Song", "Stable Artist")
    widget.set_lyric_text("Stable lyric")
    widget.show()
    qtbot.wait(50)
    return widget


def test_hover_does_not_move_track_label(qtbot):
    widget = _shown_widget(qtbot)

    before = widget._track_label.geometry()
    widget._on_enter_hover()
    qtbot.wait(50)
    after_enter = widget._track_label.geometry()
    widget._on_leave_hover()
    qtbot.wait(50)
    after_leave = widget._track_label.geometry()

    assert after_enter == before
    assert after_leave == before


def test_hover_does_not_move_lyric_label(qtbot):
    widget = _shown_widget(qtbot)

    before = widget._lyric_label.geometry()
    widget._on_enter_hover()
    qtbot.wait(50)
    after_enter = widget._lyric_label.geometry()
    widget._on_leave_hover()
    qtbot.wait(50)
    after_leave = widget._lyric_label.geometry()

    assert after_enter == before
    assert after_leave == before
```

- [ ] **Step 2: Run tests to verify they fail against the current close-button layout**

Run:

```bash
pytest tests/test_widget.py::test_hover_does_not_move_track_label tests/test_widget.py::test_hover_does_not_move_lyric_label -v
```

Expected:

- At least the track label test FAILS because the close button is currently inside `top_row` and `setVisible()` changes layout allocation.

- [ ] **Step 3: Move close button out of layout**

In `src/widget.py`, remove this line from `_setup_ui`:

```python
top_row.addWidget(self._close_btn)
```

Create the close button with `_panel` as parent:

```python
self._close_btn = QPushButton("x", self._panel)
```

Keep:

```python
self._close_btn.setFixedSize(20, 20)
self._close_btn.clicked.connect(self.close)
self._close_btn.setVisible(False)
```

- [ ] **Step 4: Add overlay positioning**

Add this method to `LyricsWidget`:

```python
def _position_overlay_controls(self):
    if hasattr(self, "_close_btn"):
        self._close_btn.move(self._panel.width() - 30, 8)
```

Add `resizeEvent`:

```python
def resizeEvent(self, event):
    self._position_overlay_controls()
    super().resizeEvent(event)
```

At the end of `_setup_ui`, after creating `_close_btn` and panel layout, call:

```python
self._position_overlay_controls()
```

- [ ] **Step 5: Run hover tests**

Run:

```bash
pytest tests/test_widget.py::test_close_button_visible_on_hover tests/test_widget.py::test_hover_does_not_move_track_label tests/test_widget.py::test_hover_does_not_move_lyric_label -v
```

Expected: all three tests PASS.

- [ ] **Step 6: Run full widget tests**

Run:

```bash
pytest tests/test_widget.py -v
```

Expected: all widget tests PASS.

---

## Task 5: Add Long Track / Artist Eliding

**Files:**
- Modify: `tests/test_widget.py`
- Modify: `src/widget.py`

- [ ] **Step 1: Add long text tests**

Add these tests to `tests/test_widget.py`:

```python
def test_long_track_info_elides_without_resizing_widget(qtbot):
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
    assert widget._track_label.text().endswith("...")


def test_track_label_reelides_from_full_text_on_resize(qtbot):
    widget = LyricsWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.wait(50)
    widget.update_track_info(
        "A Very Long Song Title For Resize Testing",
        "A Very Long Artist Name",
    )
    first = widget._track_label.text()

    widget.resize(520, widget.height())
    widget._refresh_track_label_text()
    second = widget._track_label.text()

    assert widget._track_text_full == "A Very Long Song Title For Resize Testing - A Very Long Artist Name"
    assert len(second) >= len(first)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_widget.py::test_long_track_info_elides_without_resizing_widget tests/test_widget.py::test_track_label_reelides_from_full_text_on_resize -v
```

Expected:

- FAIL because `_track_text_full` and `_refresh_track_label_text()` do not exist and long text is not elided.

- [ ] **Step 3: Implement full text storage and eliding**

In `LyricsWidget.__init__`, after timer setup state, add:

```python
self._track_text_full = ""
```

Replace `update_track_info` with:

```python
def update_track_info(self, track_name: str, artist_name: str):
    self._track_text_full = f"{track_name} - {artist_name}"
    self._refresh_track_label_text()
```

Add:

```python
def _refresh_track_label_text(self):
    if not self._track_text_full:
        self._track_label.setText("")
        return
    width = max(self._track_label.width(), 1)
    text = self._track_label.fontMetrics().elidedText(
        self._track_text_full,
        Qt.TextElideMode.ElideRight,
        width,
    )
    self._track_label.setText(text)
```

Update `resizeEvent` to refresh eliding:

```python
def resizeEvent(self, event):
    self._position_overlay_controls()
    self._refresh_track_label_text()
    super().resizeEvent(event)
```

- [ ] **Step 4: Run long-text tests**

Run:

```bash
pytest tests/test_widget.py::test_long_track_info_elides_without_resizing_widget tests/test_widget.py::test_track_label_reelides_from_full_text_on_resize -v
```

Expected: both tests PASS.

- [ ] **Step 5: Run full widget tests**

Run:

```bash
pytest tests/test_widget.py -v
```

Expected: all widget tests PASS.

---

## Task 6: Final Automated and Manual Verification

**Files:**
- No planned source edits unless verification exposes a defect.

- [ ] **Step 1: Run the full automated test suite**

Run:

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 2: Launch the app for manual UI verification**

Run:

```bash
python -m src.main
```

Expected:

- Existing saved Spotify config is reused.
- Widget opens without asking for client_id again.
- Rounded corners and `#1DB954` outline are visible.
- Track / artist text is visibly stronger than V1.
- Hovering repeatedly does not move song title, artist, lyric, offline label, or progress bar.
- Close button appears on hover and can still close the widget.
- Dragging works from the main panel.
- Long title / artist text elides instead of resizing the widget.
- Lyrics still update while music plays.

- [ ] **Step 3: Fix any manual issues with tests first**

If a defect appears, write a failing test in `tests/test_widget.py` or `tests/test_spotify_worker.py` before changing production code.

- [ ] **Step 4: Run final tests again**

Run:

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit V1.1 UI polish**

```bash
git add src/widget.py src/spotify_worker.py tests/test_widget.py tests/test_spotify_worker.py
git commit -m "feat: polish V1.1 widget UI"
```

If `src/spotify_worker.py` is unchanged, do not stage it.

---

## Self-Review Notes

- Spec coverage: rounded corners, green border, translucent outer widget, stronger track font, no-jump hover, long track eliding, and Spotify 204 test all map to tasks above.
- V2 scope check: no task adds playback controls, playlist actions, new scopes, auth changes, or packaging.
- Type consistency: the plan uses existing `LyricsWidget`, `_track_label`, `_lyric_label`, `_close_btn`, `SpotifyWorker`, and `PlayerState` names. New planned widget members are `_panel`, `_track_text_full`, `_refresh_track_label_text()`, and `_position_overlay_controls()`.

