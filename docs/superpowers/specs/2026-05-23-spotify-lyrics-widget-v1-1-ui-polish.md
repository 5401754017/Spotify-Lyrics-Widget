# Spotify Lyrics Widget V1.1 UI Polish Design

Date: 2026-05-23

---

## Goal

Refine the existing V1 floating lyrics widget so it feels softer and more polished without changing the core V1 behavior or adding V2 playback / playlist features.

This is a V1.1 visual polish pass. V1 already proves auth, Spotify polling, lyrics lookup, sync timing, and persistence. V1.1 should make the same widget look better and remove hover-induced layout movement.

---

## Scope

### In Scope

- Rounded widget corners.
- Thin Spotify-green outer border.
- Slightly softer dark panel background instead of flat pure black.
- Larger and slightly bolder song / artist text.
- Preserve one-line synced lyrics as the primary visual focus.
- Prevent track title, artist, and lyric layout from shifting when hovering.
- Elide long track / artist text so it cannot overflow or resize the widget.
- Keep close button available on hover.
- Tests for no-jump hover behavior and typography/style invariants.

### Out of Scope

- Playback controls.
- Playlist add / picker.
- New Spotify scopes.
- New auth behavior.
- Packaging.
- System tray.
- Transparency / glass blur effects.

---

## Visual Direction

The widget should feel like a compact desktop overlay, closer to a small polished system control than a square debug panel.

Target look:

- Background: Spotify dark gray `#121212`.
- Border: `1px` Spotify green `#1DB954`.
- Corner radius: `10-14px`.
- Padding: enough breathing room so text and progress do not touch the edge.
- Progress bar: still 2px, but inset from the rounded border.
- Track / artist: white, `Segoe UI` or system sans, size `10-11`, `QFont.Weight.DemiBold` (600).
- Lyric: Spotify green, size around `16-17`, bold, centered.
- Close button: top-right, hover-only visual, but it must not affect layout.

The existing Spotify black-green identity stays, but the result should be less sharp and less like a rectangular HUD.

No decorative drag handle in V1.1. The full panel remains draggable by clicking and holding anywhere on the widget.

---

## Hover Behavior

Current problem:

- The close button is inside the top row layout.
- Hover calls `setVisible(True)` / `setVisible(False)`.
- The layout recalculates when the close button appears.
- Track text and lyric area visually shift.

Required behavior:

- Hover may reveal the close button, but content geometry must not change.
- Track label geometry should remain stable before and after hover.
- Lyric label geometry should remain stable before and after hover.

Preferred implementation:

- Make the close button an absolute overlay child of the widget or panel.
- Position it in `resizeEvent`, for example near the top-right inside the border.
- Hide/show the overlay button on hover. Since it is not in the layout, this does not reflow content.

Acceptable fallback:

- Keep the close button in layout but reserve its fixed space permanently and only change opacity / text color on hover.
- This is less clean than overlay positioning but also prevents jumping.

---

## Implementation Shape

Keep `src/widget.py` as the only production UI file for this pass.

Recommended structure:

- Use a transparent outer `LyricsWidget` window.
- Set `Qt.WidgetAttribute.WA_TranslucentBackground` to `True` on the outer `LyricsWidget`.
- The outer widget stylesheet must be transparent, not black.
- Add an inner panel widget or frame with object name like `lyricsPanel`.
- Apply stylesheet to the panel:

```css
#lyricsPanel {
  background-color: #121212;
  border: 1px solid #1DB954;
  border-radius: 12px;
}
```

- Put the existing labels/progress inside that panel layout.
- Keep all current public methods stable:
  - `update_track_info`
  - `set_lyrics`
  - `set_lyric_text`
  - `set_duration`
  - `update_progress`
  - `resync_local_timer`
  - `show_no_lyrics`
  - `show_not_playing`
  - `show_not_a_track`
  - `show_unavailable`
  - `show_offline`
  - `hide_offline`
- Move close button out of the layout or reserve its layout space permanently.
- Avoid adding new one-off helper functions unless the layout code becomes hard to read.

---

## Long Text Handling

- Track / artist label: single line. If the text exceeds the available label width, elide on the right with `...`.
- Track / artist eliding should update when the widget is resized or when track info changes.
- Store the full unelided track label text separately so resizing can re-elide from the original string.
- Lyric label: keep word wrap enabled. If one lyric line becomes taller than roughly three visual lines, accept it as a known limitation for V1.1. Do not add scrolling, font shrinking, or a marquee.

---

## Remaining V1 Fixes To Include

- Add a Spotify worker test for the `204 No Content` currently-playing response. It should assert `not_playing` emits and `_previous_state` resets to `None`.
- Add long track / artist eliding as part of the V1.1 typography work.
- Keep the known `LyricsWorker.request_lyrics()` narrow race in mind, but do not change it in V1.1 unless a reproducible lyrics-not-loading bug appears.

---

## Testing

Update existing widget tests rather than creating a broad new test suite.

Add or adjust tests for:

- Widget still creates and has frameless / always-on-top flags.
- Track label font is larger or bolder than V1.
- Rounded panel style includes a border radius and green border.
- Outer widget uses translucent background while the inner panel owns the visible background.
- Long track / artist text elides instead of expanding or overflowing the widget.
- Hovering does not change `_track_label.geometry()`.
- Hovering does not change `_lyric_label.geometry()`.
- Close button still appears on hover and hides on leave.
- Spotify worker handles `204 No Content` by emitting `not_playing` and clearing previous state.
- Existing progress, no lyrics, not playing, offline indicator tests still pass.

Manual check:

- Launch the app with Spotify playing.
- Hover on and off repeatedly.
- Confirm no visible text jump.
- Confirm rounded corners and green outline are visible.
- Confirm dragging still works from the main panel.
- Confirm close button is usable.
- Confirm a long title / artist line does not resize the widget or overlap the close button.

---

## Version Placement

This belongs in V1.1, before V2.

Reason:

- It improves the already-working V1 widget.
- It does not require new Spotify scopes or new user workflows.
- V2 should stay focused on playback controls and playlist behavior.
