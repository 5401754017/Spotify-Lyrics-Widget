# Spotify Lyrics Widget — V1.1 UI Polish — FINAL Consensus Plan

> Consensus plan produced by a Claude × Codex review debate (2 rounds, full agreement).
> This supersedes `2026-05-23-spotify-lyrics-widget-v1-1-ui-polish.md`.
> Scope is UI polish only. V2 (playback controls / playlist) stays out of scope.

**Goal:** Polish the existing V1 lyrics widget — rounded corners, green border, softer
`#121212` panel, stronger DemiBold track typography, no-jump hover, long-title eliding —
WITHOUT changing core V1 behavior, and only after V1 is confirmed working live.

**Tech:** Python 3.12, PyQt6, pytest, pytest-qt. Touch only `src/widget.py`,
`tests/test_widget.py`, `tests/test_spotify_worker.py`.

---

## What changed vs the previous plan (the consensus deltas)

1. **Added Task 0: a live V1 smoke gate, run by the USER** (the build agent cannot do
   real OAuth). V1.1 polish does not start until V1 is confirmed working live.
2. **Offline indicator becomes an overlay too** — not just the close button — because it
   has the identical layout-jump defect. Added a geometry-stability test for it.
3. **Separator stays `" - "` (hyphen).** The prior review's "restore em dash" was based on
   a misreading of the source (actual code uses a hyphen).
4. **Close glyph upgraded `"x"` -> `"✕"` as an explicit, intentional polish** (not a
   "restoration"). The button is being rewritten into an overlay anyway.
5. **Shared right-side overlay gutter**, wide enough for the worst case (close button +
   offline label both visible). Eliding subtracts this gutter so long titles never paint
   under the overlays, and the two overlays never overlap each other.
6. **Elide test fixed:** `endswith("...")` is wrong — `QFontMetrics.elidedText()` returns
   the Unicode ellipsis `…` (U+2026). Assert the displayed text differs from the full
   stored text AND is shorter, and that widget width is unchanged.
7. **Task 3 layout instructions rewritten precisely** (see Task 3).
8. **Drag-after-panel risk noted** + manual check. If drag breaks, forward `_panel` mouse
   events to the outer window; do NOT make `_close_btn` mouse-transparent.

---

## Task 0 — Live V1 Smoke Gate (USER-RUN, blocking)

> NOT an agent task. Real OAuth needs the user's browser, Spotify Premium, and their own
> registered `client_id` on their Windows machine. The build agent must STOP and ask the
> user to perform this, and must not fabricate a pass.

User checklist (all must pass before any polish work):

- [ ] `python -m src.main` launches without crashing.
- [ ] First run: client_id prompt works; system browser opens; Spotify OAuth (PKCE)
      completes; token persists to `%APPDATA%/spotify-lyrics-widget/config.json`.
- [ ] With a real track playing: song name + artist show; **synced lyrics advance
      line-by-line in time** with playback.
- [ ] Pause freezes the line; resume continues; skip/seek resyncs within ~1s.
- [ ] Window is frameless, always-on-top, and draggable; position is restored on relaunch.
- [ ] A track with no synced lyrics shows "no synced lyrics" (no crash).

If anything fails: fix V1 first using TDD (write a failing test, then fix), and only then
proceed to Task 1.

---

## Task 1 — Cover Spotify 204 No Content Idle State

(Unchanged from the prior plan.) Add `TestSpotifyWorkerIdleResponse` to
`tests/test_spotify_worker.py`: mock `httpx.get` returning `status_code=204, text=""`,
assert `not_playing` is emitted and `_previous_state` resets to `None`. Run the focused
test; if it fails, make `src/spotify_worker.py` match the intended 204 path. Commit
(stage `src/spotify_worker.py` only if it actually changed).

---

## Task 2 — Add Widget Style + Typography Tests (expect-fail first)

Add to `tests/test_widget.py` (and `from PyQt6.QtGui import QFont`):

```python
def test_widget_uses_translucent_outer_and_rounded_panel(qtbot):
    widget = LyricsWidget(); qtbot.addWidget(widget)
    assert widget.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert widget._panel.objectName() == "lyricsPanel"
    style = widget._panel.styleSheet().lower().replace(" ", "")
    assert "#121212" in style
    assert "#1db954" in style
    assert "border-radius:" in style and "0px" not in style.split("border-radius:")[1][:4]

def test_track_label_font_is_larger_and_demibold(qtbot):
    widget = LyricsWidget(); qtbot.addWidget(widget)
    font = widget._track_label.font()
    assert font.pointSize() >= 10
    assert font.weight() >= QFont.Weight.DemiBold.value
```

Run them; both FAIL (no `_panel`, outer not translucent, track font still size 9 regular).

---

## Task 3 — Rounded Inner Panel, Transparent Outer, Track Typography

Precise layout structure (consensus):

- Outer `LyricsWidget`: `WA_TranslucentBackground=True`, stylesheet
  `background-color: transparent;`, keep `setFixedWidth(420)`, keep
  `FramelessWindowHint | WindowStaysOnTopHint | Tool`.
- Inner `_panel = QFrame(self)`, `objectName("lyricsPanel")`, `setMouseTracking(True)`,
  stylesheet:
  ```
  #lyricsPanel { background-color: #121212; border: 1px solid #1DB954; border-radius: 12px; }
  ```
- Outer layout: zero margins/spacing, holds only `_panel`.
- **Panel layout contains ONLY:** `top_row` (which contains ONLY `_track_label`),
  then `_lyric_label`, then `_progress_bar`.
- **`_close_btn` and `_offline_label` are overlay children of `_panel`** — created with
  `_panel` as parent, NOT added to any layout. They are positioned in `resizeEvent` via
  `_position_overlay_controls()`.
- Color constants: replace `BLACK = "#000000"` with `PANEL_BACKGROUND = "#121212"`;
  keep `WHITE`, `SPOTIFY_GREEN`, `DARK_GRAY`. Confirm `BLACK` has no other references.
- Track label font: `QFont("Segoe UI", 10, QFont.Weight.DemiBold)`. Do NOT call
  `setSingleLine()` (no such method on QLabel; it is single-line by default).

Run focused style tests -> PASS. Some hover/elide tests still fail until Tasks 4–5.

---

## Task 4 — Overlay Close Button + Overlay Offline Indicator + No-Jump Tests

Tests (add to `tests/test_widget.py`):

```python
def _shown_widget(qtbot):
    w = LyricsWidget(); qtbot.addWidget(w)
    w.update_track_info("Stable Song", "Stable Artist")
    w.set_lyric_text("Stable lyric"); w.show(); qtbot.wait(50)
    return w

def test_hover_does_not_move_track_label(qtbot):
    w = _shown_widget(qtbot); before = w._track_label.geometry()
    w._on_enter_hover(); qtbot.wait(50); a = w._track_label.geometry()
    w._on_leave_hover(); qtbot.wait(50); b = w._track_label.geometry()
    assert a == before and b == before

def test_hover_does_not_move_lyric_label(qtbot):
    w = _shown_widget(qtbot); before = w._lyric_label.geometry()
    w._on_enter_hover(); qtbot.wait(50); a = w._lyric_label.geometry()
    w._on_leave_hover(); qtbot.wait(50); b = w._lyric_label.geometry()
    assert a == before and b == before

def test_offline_toggle_does_not_move_labels(qtbot):
    w = _shown_widget(qtbot)
    t0, l0 = w._track_label.geometry(), w._lyric_label.geometry()
    w.show_offline(); qtbot.wait(50)
    assert w._track_label.geometry() == t0 and w._lyric_label.geometry() == l0
    w.hide_offline(); qtbot.wait(50)
    assert w._track_label.geometry() == t0 and w._lyric_label.geometry() == l0
```

Implementation:

- Remove `_close_btn` and `_offline_label` from the layout. Create both as children of
  `_panel`.
- Close button: `QPushButton("✕", self._panel)`, fixed 20×20, keep transparent styling
  (white text, hover -> green), `clicked.connect(self.close)`, `setVisible(False)`.
- Offline label: keep as a small overlay label (`! offline`, red), `setVisible(False)`.
- `_position_overlay_controls()`: position both inside a single reserved right-side
  gutter at the panel top. The gutter width = close button + offline label widths +
  spacing (worst case both visible), so they never overlap each other. Call it at the
  end of `_setup_ui` and from `resizeEvent`.
- Keep `_on_enter_hover`/`_on_leave_hover` toggling the close button only.

Run hover + offline + close-on-hover tests -> PASS.

---

## Task 5 — Long Track / Artist Eliding (gutter-aware)

Test:

```python
def test_long_track_info_elides_without_resizing_widget(qtbot):
    w = LyricsWidget(); qtbot.addWidget(w); w.show(); qtbot.wait(50)
    w0 = w.width()
    full = "This Is An Extremely Long Track Name - An Extremely Long Artist Name"
    w.update_track_info("This Is An Extremely Long Track Name",
                        "An Extremely Long Artist Name")
    qtbot.wait(50)
    assert w.width() == w0                       # fixed width preserved
    assert w._track_label.text() != full         # was elided
    assert len(w._track_label.text()) < len(full) # shorter (robust vs the … char)
```

Implementation:

- Store full text: `self._track_text_full = ""` in `__init__`.
- `update_track_info`: set `self._track_text_full = f"{track_name} - {artist_name}"`
  (HYPHEN), then `self._refresh_track_label_text()`.
- `_refresh_track_label_text()`: elide with `Qt.TextElideMode.ElideRight` to
  **(track label width − right gutter)** so text never runs under the overlays.
- `resizeEvent`: call `_position_overlay_controls()` then `_refresh_track_label_text()`.
- Do NOT keep any `endswith("...")` assertion or a `resize(520, …)` test (the widget is
  fixed-width by design).

Run -> PASS.

---

## Task 6 — Final Automated + Manual Verification

- [ ] `pytest -v` — all pass.
- [ ] Manual launch `python -m src.main` (reuses saved config, no re-auth):
  - Rounded corners + `#1DB954` outline visible; panel is `#121212`, not pure black.
  - Track/artist visibly stronger than V1.
  - Hover on/off repeatedly: song title, artist, lyric, progress bar, and **offline
    label toggling** do not move anything.
  - Close button (`✕`) appears on hover and closes the app.
  - **Dragging still works from the panel** (known risk: the `_panel` child covers the
    outer window). If drag breaks, forward `_panel` mouse events to the outer window —
    do NOT make `_close_btn` mouse-transparent.
  - Long title/artist elides instead of resizing, and does not paint under the overlays.
  - Lyrics still advance while playing.
- [ ] If a defect appears: write a failing test first, then fix.
- [ ] `pytest -v` again — all pass. Commit `feat: polish V1.1 widget UI`.
