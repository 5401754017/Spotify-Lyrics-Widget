# Spotify Lyrics Widget — V1.2 Stability & Polish — FINAL Consensus Plan

> Consensus plan from a Claude × Codex review debate (2 rounds, full agreement),
> grounded in the shipped V1.1 code on branch `codex/spotify-widget-v1-1-ui-polish`.
> Each task has a plain-language INTENT line and the technical specifics.

**Goal:** Make the widget stable and predictable — hide the console (with a log safety
net), stop the title/lyric from jumping, fix the clipped second lyric line, stop the
offline indicator from pushing content, prevent the multi-instance bug that broke
"currently playing" detection, and back off properly when Spotify rate-limits us (429).
No new Spotify features.

**Tech:** Python 3.12, PyQt6. Touch `src/main.py`, `src/widget.py`, and add `src/logging_setup.py`.
Add/adjust tests in `tests/`.

---

## Scope

**IN (V1.2):** Tasks 1–5 below.
**OUT (decided against):** Adaptive / content-driven window resizing. It reintroduces the
exact jumping that Task 2 fixes; a persistent always-on-top HUD should have a stable size.
**DEFERRED to V2:** Hover-triggered title marquee (see "V2 Future Notes"). V1.2 keeps the
simple `...` elide.

---

## Task 1 — Hide the console + add file logging (do these together)

INTENT: Stop the empty black terminal window from appearing, but make sure errors are
still recorded somewhere — because right now errors vanish silently (that is why the
"can't detect playing song" bug was invisible).

- Add `src/logging_setup.py`: configure Python `logging` to write to
  `%APPDATA%/spotify-lyrics-widget/widget.log` (rotating file handler, e.g. 1 MB x 3).
  Call it first thing in `main()`.
- Replace swallowed exceptions with logging:
  - `src/spotify_worker.py` `_refresh_token()` `except Exception:` → log the exception
    before returning False.
  - `src/spotify_worker.py` `_poll_once()` bare `except` → log before returning.
- Wrap `main()` startup in try/except: on any unhandled startup error, log it AND show a
  `QMessageBox.critical` so a no-console user still sees fatal failures.
- Non-console launch: provide a `pythonw.exe`-based launch (e.g. a `run.pyw` entry or a
  `.bat`/shortcut using `pythonw -m src.main`). Record that the eventual packaged build
  (future V3) uses PyInstaller `--windowed`.

VERIFY: launch via pythonw → no console window; force an error → it appears in widget.log
and a fatal one shows a QMessageBox.

---

## Task 2 — Fixed geometry: stop title/lyric jumping and clipped 2nd line

INTENT: The window currently only fixes its WIDTH, so when a lyric goes from 1 line to 2
lines the window grows/reflows — the title jumps and the 2nd line gets clipped (see user
screenshot of "7 Years"). Make the size constant.

- Give the window a FIXED HEIGHT (`setFixedHeight`, or fix the heights of each row so the
  total never changes). Keep `setFixedWidth(420)`.
- Title row pinned at the top.
- Lyric area: a FIXED-height lane tall enough for exactly TWO lines at the current font.
  The lyric label is vertically centered within this lane:
  - 1 line → centered in the lane.
  - 2 lines → fills the lane (no clipping).
  - longer than 2 lines → cap at 2 lines and elide/clip the remainder (do NOT grow the
    window).
- Progress bar stays a fixed 2px at the bottom, inset from the rounded border.

VERIFY: play songs whose lyric lines vary 1↔2 lines; the title and progress bar never
move; the 2nd line is never cut.

---

## Task 3 — Correct layout immediately on first show

INTENT: Right now, when you first open it, the layout is wrong (2nd line half-hidden) and
only "auto-corrects" after a moment. Make it correct from the first frame.

- Cause: elide width and overlay positions are computed in `_setup_ui` before the widget
  has its real size; they only fix up on the first `resizeEvent`.
- Fix: do a one-time layout/elide/overlay refresh in `showEvent` (or a single-shot
  `QTimer.singleShot(0, ...)` after show), and/or compute from the known fixed dimensions
  instead of live `.width()` reads.
- NOTE: Task 2's fixed geometry already removes most of this; this task ensures the very
  first paint is correct.

VERIFY: open the app while a 2-line-lyric song is playing → it is correct instantly, no
delayed shift.

---

## Task 4 — Offline indicator must not push content

INTENT: The red "! offline" message currently sits above the title, so when it appears
(network drop) it shoves the title down. Make it float without disturbing anything.

- Currently `_offline_label` is `layout.insertWidget(0, ...)` — in the layout.
- Change it to an overlay child of `_panel`, positioned via `_position_overlay_controls()`
  (same approach the close button already uses), toggled by show/hide without touching
  the layout.
- Reserve a shared right-side overlay gutter wide enough for close button + offline label
  together, so they never overlap each other or the title.

VERIFY: toggling offline does not move the title, lyric, or progress bar.

---

## Task 5 — One instance only + clean shutdown (fixes the "can't detect song" bug)

INTENT: This was the real bug. An old instance from a previous launch kept running in the
background; opening new ones created multiple instances fighting over Spotify token
refresh, corrupting auth so none could read "currently playing". (We confirmed a zombie
`python -m src.main` from the prior day and killed it.)

- Single-instance guard: on startup, if an instance is already running, focus/raise the
  existing window and exit the new one (e.g. a lock file in `%APPDATA%`, a named mutex, or
  a `QLocalServer`/`QLocalSocket`).
- Clean shutdown: ensure closing the widget fully stops the `SpotifyWorker` thread and
  exits the process (no lingering background poller). Verify `aboutToQuit`/`shutdown`
  actually terminates the thread; `wait()` then exit.
- Do not let shutdown clobber tokens: `shutdown()` should persist ONLY window position
  (re-load config, update x/y, save) so a closing instance never overwrites a fresher
  token written by the refresh path.

VERIFY: open the widget; try to open a second → it focuses the first, no second process.
Close it → no `python -m src.main` left in Task Manager. Open/close repeatedly → still
detects the playing song.

---

## Task 6 — Honor Spotify rate limits (429 Retry-After)

INTENT: The widget polls every 1 second and has NO handling for Spotify's `429 Too Many
Requests`. A non-200 response is currently swallowed, so the widget just goes blank. During
this work we hit a REAL 429 with `Retry-After` ≈ 15 hours, caused by the zombie +
multi-instance hammering. The widget must back off, not keep hammering (which extends the
ban).

- In `src/spotify_worker.py`, handle `response.status_code == 429`:
  - Read the `Retry-After` response header (seconds). Stop polling for that duration
    (cap it sensibly, e.g. don't sleep the thread for 15h — sleep in short checks so
    `stop()` still works), then resume. NEVER keep polling at 1s through a 429.
  - Log the 429 and the Retry-After value (uses Task 1 logging).
  - Emit a signal so the UI shows a "rate limited — retrying" state instead of going blank.
- Optional: small exponential backoff on repeated 429s.
- Together with Task 5 (single instance), this prevents the hammering that caused the ban.

VERIFY: mock a 429 with a `Retry-After` header → the worker stops polling for that period,
the UI shows a rate-limited state, and polling resumes afterward. Continuing to poll during
a ban is the bug being fixed.

---

## Final Verification (user-run, live)

Run on the real machine with Spotify playing (the build agent cannot do live OAuth):
- No console window; widget.log is being written.
- 1↔2 line lyrics: nothing jumps, 2nd line never clipped, correct from first frame.
- Offline toggling does not move content.
- Only one instance can run; closing leaves no zombie; repeated open/close still works.
- Lyrics still sync line-by-line.

---

## V2 Future Notes (do NOT build in V1.2)

**Hover title marquee** (decided: hover-triggered, not always-on; built with V2 controls):
- Static elided title at rest; on hover, scroll the FULL title in its (now narrower,
  because controls appear) space.
- Dedicated `MarqueeLabel` with fixed geometry and clipped painting; never resize the
  label or mutate layout during scroll.
- Only animate when `fontMetrics.horizontalAdvance(full_title) > available_width`.
- Start on hover after a short pause; stop/reset on leave, track change, and when control
  visibility/width changes.
- Use a dedicated timer or `QPropertyAnimation`; do NOT reuse the 150ms lyric UI timer.
- Slow ping-pong (not endless wraparound); scroll the rendered full string/offset, never
  substring-slice (keeps CJK/Unicode correct).

**Optional later:** user-resizable WIDTH (drag a corner, persist to config) — only if the
fixed size ever feels limiting. Not content-driven auto-resize.
