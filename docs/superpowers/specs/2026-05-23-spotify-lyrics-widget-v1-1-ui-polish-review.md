# Spotify Lyrics Widget V1.1 UI Polish - Review

Date: 2026-05-23

Target spec: `2026-05-23-spotify-lyrics-widget-v1-1-ui-polish.md`

Also covers: remaining V1 implementation issues found during review.

---

## Verdict

The V1.1 UI polish spec is well-scoped and actionable. The core idea (rounded corners, green border, no-jump hover) is correct. Fix the issues below before implementing.

---

## V1 Remaining Issues (fix before or alongside V1.1)

### 1. Missing test: Spotify worker 204 response

`tests/test_spotify_worker.py` does not test the `status_code=204` path in `_poll_once()`. This is the most common response when Spotify is idle (no active playback).

Fix: Add a test that mocks `httpx.get` returning 204, asserts `not_playing` signal is emitted and `_previous_state` is reset to `None`.

### 2. Long track name / artist overflow

`src/widget.py` `_track_label` uses `AlignCenter` but has no text elide or max width. When the track name or artist name is long, the label will either overflow the widget or force the widget to expand.

Fix: Set `_track_label` to use `Qt.TextElideMode.ElideRight` via `QFontMetrics` + `elidedText`, or set a fixed max width on the label and enable elide. This can be fixed as part of V1.1 typography changes.

### 3. LyricsWorker race condition (low risk, document only)

`lyrics_worker.py` `request_lyrics()` sets `_has_work = True` from the main thread while `run()` checks it from the worker thread. There is a narrow window where a request could be missed if `_has_work` is set between the while-check and the return. In practice, the next Spotify poll cycle will re-trigger the request within 1 second, so this is low risk. No code change needed now, but be aware of this if lyrics-not-loading bugs appear later.

---

## V1.1 Spec Issues

### 1. Background color `#090909` is too close to pure black

Current spec: `#090909`

Problem: The difference from `#000000` is imperceptible on most displays (luminance delta < 2%). The rounded corners and green border need visible contrast against the panel background to look intentional.

Spec change: Use `#121212` (Spotify's own dark background color) or `#181818`. Either provides enough contrast for the border and rounded corners to read clearly without losing the dark aesthetic.

### 2. Rounded corners require `WA_TranslucentBackground` on the outer widget

Current spec recommends a transparent outer `LyricsWidget` + inner panel with `border-radius`.

This is the correct structure, but the spec does not mention that `WA_TranslucentBackground` must be set on the outer `LyricsWidget` for rounded corners to work on Windows. Without it, the area outside the rounded corners will show opaque black rectangles instead of transparency.

Spec change: Add explicit requirement:

- Outer `LyricsWidget` must have `Qt.WidgetAttribute.WA_TranslucentBackground` set to `True`.
- The outer widget's own `background-color` must be `transparent` (not black).
- Only the inner panel (`#lyricsPanel`) should have the dark background.

Note: The current V1 code sets `WA_TranslucentBackground` to `False`. This must change in V1.1.

### 3. Drop the drag handle

Current spec says the drag handle is "optional".

Recommendation: Do not implement it. The entire widget is already draggable by clicking anywhere. A decorative pill adds visual noise and implementation complexity (positioning, sizing, color) without adding any capability. If users later report confusion about how to move the widget, it can be added then.

Spec change: Remove the drag handle from scope. The widget remains draggable by clicking anywhere on the panel.

### 4. Add long text handling spec

Current spec does not define behavior when track name, artist name, or lyric line exceeds the widget width.

Spec change: Add a section:

- **Track / artist label:** Single line, elide with ellipsis (`...`) on the right if text exceeds available width.
- **Lyric label:** Allow word wrap (already enabled in V1). If a single lyric line is very long (>3 visual lines), it may overflow vertically. Accept this as a known limitation; do not add scrolling or font shrinking.

### 5. Small: font weight terminology

Spec says "medium / demi-bold weight" for track/artist text. PyQt6's `QFont.Weight` enum does not have "demi-bold". The closest values are `QFont.Weight.Medium` (500) or `QFont.Weight.DemiBold` (600).

Spec change: Pick one. Recommend `QFont.Weight.DemiBold` (600) for the track/artist label to ensure it reads clearly at size 10-11.

---

## Summary of Required Spec Changes

| # | Change | Priority |
|---|--------|----------|
| 1 | Background color: `#090909` -> `#121212` or `#181818` | Must fix |
| 2 | Add `WA_TranslucentBackground` requirement for outer widget | Must fix |
| 3 | Remove drag handle from scope | Recommended |
| 4 | Add long text handling (elide track label, accept lyric wrap) | Must fix |
| 5 | Clarify font weight to `DemiBold` (600) | Nice to have |

## Summary of V1 Fixes to Include

| # | Change | Priority |
|---|--------|----------|
| 1 | Add 204 response test in `test_spotify_worker.py` | Should fix |
| 2 | Add track label text elide (can merge into V1.1 work) | Should fix |
| 3 | LyricsWorker race condition | Document only, no code change |
