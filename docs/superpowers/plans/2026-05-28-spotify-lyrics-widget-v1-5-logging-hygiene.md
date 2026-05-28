# Spotify Lyrics Widget V1.5 — Logging Hygiene (Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the silent-exception gaps in the lyrics pipeline (and two adjacent silent paths) surfaced during V1.4 acceptance testing. Every failure mode and every emit decision must log a **concrete cause** — status code, exception class name, or specific reason — so production debugging never again requires elimination-by-inference.

**Architecture:** Three thin patches: (a) `lyrics_worker.run()` adds INFO/WARNING logs at every exit (cache hit, LRCLIB except, NetEase except, lyrics_ready emit, no_lyrics emit); (b) `fetch_lyrics_from_lrclib` adds INFO logs at /get and /search decision points; (c) `main.py:_ensure_auth` token pre-refresh and `spotify_worker._poll_once` network exception each get a single WARNING. `netease.py` already logs every failure concretely → untouched. No behaviour change: only log emission is added.

**Tech Stack:** Python stdlib `logging` (already configured via `src/logging_setup.py`); pytest with the `caplog` fixture for assertions on log records.

**Trigger / Context:** V1.4 manual verification on 2026-05-28 produced a real symptom ("歌詞沒辦法取得" for 等待你那天) whose root cause (LRCLIB `/search` `ReadTimeout` from transient throttling) was invisible in `widget.log` because `lyrics_worker.run()` swallows `LrclibUnavailableError` without logging. We confirmed the failure by re-running `httpx.get` outside the widget and timing it — but only because we had codebase access. In normal user-only use, the same failure would be undebuggable. The deeper "should LRCLIB-unavailable still trigger NetEase as salvage?" question is a **separate design decision** that requires Codex consensus per `memory/codex-consensus-and-validate-before-adopting.md` and is **explicitly out of scope** for V1.5.

---

## File Structure

| File | Status | Responsibility |
|------|--------|----------------|
| `src/lyrics_worker.py` | Modify | `run()` logs at every exit (cache hit / LRCLIB except / NetEase except / lyrics_ready emit / no_lyrics emit). `fetch_lyrics_from_lrclib` logs at /get decision, /search decision, hit/no-match. |
| `src/main.py` | Modify | Replace `except Exception: pass` at token pre-refresh (currently lines ~149–150) with a `logging.warning` that records the exception class + message and notes fall-through to OAuth. |
| `src/spotify_worker.py` | Modify | In `_poll_once`, add a `logging.warning` inside the `except (httpx.ConnectError, httpx.TimeoutException)` branch (currently lines ~172–176) recording exception class + message before the existing `network_error.emit()`. |
| `tests/test_lyrics_worker.py` | Modify | `caplog` asserts for each run() exit + fetch_lyrics_from_lrclib decision point. |
| `tests/test_main.py` | Modify | `caplog` assert that `_ensure_auth` warns on pre-refresh failure but still falls through. |
| `tests/test_spotify_worker.py` | Modify | `caplog` assert that `_poll_once` warns when the request raises `ConnectError`/`TimeoutException`. |

**Conventions used by this plan:**
- Project files call `logging.info(...)` / `logging.warning(...)` directly on the root logger (see `src/netease.py`). New code matches this; do **not** introduce a module logger.
- Tests use `caplog.set_level(logging.INFO)` (or `WARNING`) and assert with substring matches on `record.message`. Do **not** pin entire log strings — assertions are level + key substrings only, so future wording tweaks don't break tests.
- `caplog` is not yet used anywhere in this repo. The first task that adds it sets the precedent — keep it lean.

**All commands run from the project root.** `pytest.ini` sets `pythonpath = .`, `testpaths = tests`. To bypass the broken default `pytest-of-crayo` temp dir on this machine, run with:

```
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp -q <args>
```

---

## Task 1: Worker exit-point logging — LRCLIB & NetEase exception paths

**Why:** This is the gap that hid the V1.4 verification symptom. After this task, an LRCLIB `/search` timeout will produce a WARNING line naming the exception class and message before the `lyrics_unavailable` signal — no more guessing.

**Files:**
- Modify: `src/lyrics_worker.py` `LyricsWorker.run()` (currently lines 196–231)
- Test: `tests/test_lyrics_worker.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_lyrics_worker.py`:

```python
import logging


def _pending_worker(netease_fallback):
    from src.lyrics_worker import LyricsWorker
    worker = LyricsWorker(netease_fallback=netease_fallback)
    worker._pending_track = TrackInfo("t1", "Song", "Artist", "Album", 180000)
    worker._has_work = True
    return worker


@patch("src.lyrics_worker.fetch_lyrics_from_lrclib",
       side_effect=LrclibUnavailableError("lrclib search timeout: read timed out"))
def test_run_warns_on_lrclib_unavailable_with_concrete_reason(mock_lrclib, qtbot, caplog):
    worker = _pending_worker(netease_fallback=False)
    caplog.set_level(logging.INFO, logger="root")
    worker.run()
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    infos = [r for r in caplog.records if r.levelname == "INFO"]
    assert any("LRCLIB failed" in r.message and "Song" in r.message
               and "LrclibUnavailableError" in r.message
               and "search timeout" in r.message for r in warnings), \
        f"expected concrete LRCLIB-failure warning, got: {[r.message for r in warnings]}"
    assert any("lyrics_unavailable" in r.message and "t1" in r.message for r in infos)


@patch("src.lyrics_worker.fetch_lyrics_from_netease")
@patch("src.lyrics_worker.fetch_lyrics_from_lrclib", return_value=None)
def test_run_warns_on_netease_unavailable_with_concrete_reason(mock_lrclib, mock_netease, qtbot, caplog):
    from src.netease import NeteaseUnavailableError
    mock_netease.side_effect = NeteaseUnavailableError("NetEase rate limited")
    worker = _pending_worker(netease_fallback=True)
    caplog.set_level(logging.INFO, logger="root")
    worker.run()
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert any("NetEase failed" in r.message and "Song" in r.message
               and "rate limited" in r.message for r in warnings), \
        f"expected concrete NetEase-failure warning, got: {[r.message for r in warnings]}"


@patch("src.lyrics_worker.fetch_lyrics_from_lrclib", return_value=[(1000, "hi")])
def test_run_logs_lyrics_ready_emit(mock_lrclib, qtbot, caplog):
    worker = _pending_worker(netease_fallback=False)
    caplog.set_level(logging.INFO, logger="root")
    worker.run()
    infos = [r for r in caplog.records if r.levelname == "INFO"]
    assert any("lyrics_ready" in r.message and "t1" in r.message
               and "1 lines" in r.message for r in infos)


@patch("src.lyrics_worker.fetch_lyrics_from_netease", return_value=None)
@patch("src.lyrics_worker.fetch_lyrics_from_lrclib", return_value=None)
def test_run_logs_no_lyrics_emit_with_both_miss(mock_lrclib, mock_netease, qtbot, caplog):
    worker = _pending_worker(netease_fallback=True)
    caplog.set_level(logging.INFO, logger="root")
    worker.run()
    infos = [r for r in caplog.records if r.levelname == "INFO"]
    assert any("no_lyrics" in r.message and "t1" in r.message
               and "both" in r.message.lower() for r in infos)


def test_run_logs_cache_hit_lyrics(qtbot, caplog):
    worker = _pending_worker(netease_fallback=True)
    worker._cache.set("t1", [(0, "cached")])
    caplog.set_level(logging.INFO, logger="root")
    worker.run()
    infos = [r for r in caplog.records if r.levelname == "INFO"]
    assert any("cache hit" in r.message and "t1" in r.message
               and "1 lines" in r.message for r in infos)


def test_run_logs_cache_hit_no_lyrics(qtbot, caplog):
    worker = _pending_worker(netease_fallback=True)
    worker._cache.set_no_lyrics("t1")
    caplog.set_level(logging.INFO, logger="root")
    worker.run()
    infos = [r for r in caplog.records if r.levelname == "INFO"]
    assert any("cache hit" in r.message and "t1" in r.message
               and "no lyrics" in r.message for r in infos)
```

- [ ] **Step 2: Run to verify they fail**

```
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp -q tests/test_lyrics_worker.py -k "logs_ or warns_on" -v
```

Expected: 6 FAIL — no log records captured at all (worker is silent today).

- [ ] **Step 3: Implement in `src/lyrics_worker.py`**

Add `import logging` at the top of the file (next to the existing `import re`).

Replace `LyricsWorker.run()` (currently lines 196–231) with the following. Behaviour is unchanged; only `logging.*` calls are added, and the two `except` clauses now bind the exception so we can include its class + message in the warning.

```python
    def run(self):
        while self._has_work:
            self._has_work = False
            info = self._pending_track
            if info is None:
                return

            cached = self._cache.get(info.track_id)
            if cached is not LyricsCache.MISS:
                if cached is LyricsCache.NO_LYRICS:
                    logging.info("cache hit for %s (track_id=%s, no lyrics)", info.track_name, info.track_id)
                    self.no_lyrics.emit(info.track_id)
                else:
                    logging.info("cache hit for %s (track_id=%s, %d lines)", info.track_name, info.track_id, len(cached))
                    self.lyrics_ready.emit(info.track_id, cached)
                return

            try:
                result = fetch_lyrics_from_lrclib(info)
            except (httpx.ConnectError, LrclibUnavailableError) as error:
                logging.warning(
                    "LRCLIB failed for %s (track_id=%s): %s: %s",
                    info.track_name, info.track_id, type(error).__name__, error,
                )
                logging.info("emit lyrics_unavailable for %s (track_id=%s, no cache write)",
                             info.track_name, info.track_id)
                self.lyrics_unavailable.emit(info.track_id)
                return

            if not result and self._netease_fallback:
                try:
                    result = fetch_lyrics_from_netease(
                        info.track_name, info.artist_name, info.duration_ms
                    )
                except NeteaseUnavailableError as error:
                    logging.warning(
                        "NetEase failed for %s (track_id=%s): %s: %s",
                        info.track_name, info.track_id, type(error).__name__, error,
                    )
                    logging.info("emit lyrics_unavailable for %s (track_id=%s, no cache write)",
                                 info.track_name, info.track_id)
                    self.lyrics_unavailable.emit(info.track_id)
                    return

            if result:
                self._cache.set(info.track_id, result)
                logging.info("emit lyrics_ready for %s (track_id=%s, %d lines)",
                             info.track_name, info.track_id, len(result))
                self.lyrics_ready.emit(info.track_id, result)
            else:
                self._cache.set_no_lyrics(info.track_id)
                logging.info(
                    "emit no_lyrics for %s (track_id=%s, both LRCLIB and NetEase confirmed miss, caching NO_LYRICS)",
                    info.track_name, info.track_id,
                )
                self.no_lyrics.emit(info.track_id)
```

(The two `info.track_id`-only log payloads use the existing `info` in scope; no new fields are introduced anywhere else in the codebase.)

- [ ] **Step 4: Run to verify pass**

```
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp -q tests/test_lyrics_worker.py -v
```

Expected: full file PASSES — six new tests + all existing tests.

- [ ] **Step 5: Commit**

```
git add src/lyrics_worker.py tests/test_lyrics_worker.py
git commit -m "feat(log): worker run() logs concrete reason at every exit (V1.5)"
```

---

## Task 2: `fetch_lyrics_from_lrclib` decision-point logging

**Why:** `httpx` logs each HTTP request with status code, but it does not say what the worker concluded — was `/get 200` a hit or a 200-with-no-syncedLyrics fall-through? Was `/search 200` a hit or "ranking rejected everything"? Today's audit could not answer this without running the code by hand. After this task, the log answers it directly.

**Files:**
- Modify: `src/lyrics_worker.py` `fetch_lyrics_from_lrclib` (currently lines 127–173)
- Test: `tests/test_lyrics_worker.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_lyrics_worker.py`:

```python
class TestLrclibFetchLogs:
    @patch("src.lyrics_worker.httpx.get")
    def test_get_hit_logs_one_line(self, mock_get, caplog):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"syncedLyrics": "[00:01.00]hi"},
        )
        info = TrackInfo("t1", "Song", "Artist", "Album", 180000)
        caplog.set_level(logging.INFO, logger="root")
        result = fetch_lyrics_from_lrclib(info)
        assert result == [(1000, "hi")]
        assert any("LRCLIB /get hit" in r.message and "Song" in r.message
                   and "1 lines" in r.message for r in caplog.records)

    @patch("src.lyrics_worker.httpx.get")
    def test_get_404_then_search_hit_logs_both(self, mock_get, caplog):
        mock_get.side_effect = [
            MagicMock(status_code=404, text="not found"),
            MagicMock(status_code=200, json=lambda: [
                {"trackName": "Song", "artistName": "Artist",
                 "duration": 180, "syncedLyrics": "[00:02.00]yo"},
            ]),
        ]
        info = TrackInfo("t1", "Song", "Artist", "Album", 180000)
        caplog.set_level(logging.INFO, logger="root")
        result = fetch_lyrics_from_lrclib(info)
        assert result == [(2000, "yo")]
        messages = [r.message for r in caplog.records]
        assert any("/get 404" in m and "trying /search" in m for m in messages)
        assert any("LRCLIB /search hit" in m and "1 lines" in m for m in messages)

    @patch("src.lyrics_worker.httpx.get")
    def test_get_200_no_synced_then_search_empty_logs_fall_through_and_no_match(self, mock_get, caplog):
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"syncedLyrics": None, "plainLyrics": "x"}),
            MagicMock(status_code=200, json=lambda: []),
        ]
        info = TrackInfo("t1", "Song", "Artist", "Album", 180000)
        caplog.set_level(logging.INFO, logger="root")
        result = fetch_lyrics_from_lrclib(info)
        assert result is None
        messages = [r.message for r in caplog.records]
        assert any("/get 200 no syncedLyrics" in m and "trying /search" in m for m in messages)
        assert any("/search no acceptable match" in m and "0 results" in m for m in messages)

    @patch("src.lyrics_worker.httpx.get")
    def test_search_ranking_rejects_all_logs_concrete_reason(self, mock_get, caplog):
        mock_get.side_effect = [
            MagicMock(status_code=404, text=""),
            MagicMock(status_code=200, json=lambda: [
                {"trackName": "Other", "artistName": "Other",
                 "duration": 999, "syncedLyrics": "[00:01.00]x"},
            ]),
        ]
        info = TrackInfo("t1", "Song", "Artist", "Album", 180000)
        caplog.set_level(logging.INFO, logger="root")
        result = fetch_lyrics_from_lrclib(info)
        assert result is None
        messages = [r.message for r in caplog.records]
        assert any("/search no acceptable match" in m and "1 results" in m for m in messages)
```

- [ ] **Step 2: Run to verify they fail**

```
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp -q tests/test_lyrics_worker.py::TestLrclibFetchLogs -v
```

Expected: 4 FAIL — log records missing.

- [ ] **Step 3: Implement in `src/lyrics_worker.py`**

Rewrite `fetch_lyrics_from_lrclib` (currently lines 127–173) to add the four decision-point log calls. Behaviour and return values are identical; only `logging.info` calls are added.

```python
def fetch_lyrics_from_lrclib(info: TrackInfo) -> list[tuple[int, str]] | None:
    """Fetch parsed synced lyrics, or None after a confirmed no-lyrics result."""
    duration_s = info.duration_ms // 1000

    try:
        response = httpx.get(
            f"{LRCLIB_BASE}/get",
            params={
                "track_name": info.track_name,
                "artist_name": info.artist_name,
                "album_name": info.album_name,
                "duration": duration_s,
            },
            timeout=10.0,
        )
    except httpx.TimeoutException as error:
        raise LrclibUnavailableError(f"lrclib timeout: {error}") from error

    get_status = response.status_code
    data = _lrclib_json_or_unavailable(response)
    synced = (data or {}).get("syncedLyrics") if isinstance(data, dict) else None
    if synced:
        parsed = parse_lrc(synced)
        logging.info("LRCLIB /get hit for %s (%d lines)", info.track_name, len(parsed))
        return parsed
    if get_status == 200:
        logging.info("LRCLIB /get 200 no syncedLyrics for %s, trying /search", info.track_name)
    else:
        logging.info("LRCLIB /get %d for %s, trying /search", get_status, info.track_name)

    try:
        response = httpx.get(
            f"{LRCLIB_BASE}/search",
            params={
                "track_name": info.track_name,
                "artist_name": info.artist_name,
            },
            timeout=10.0,
        )
    except httpx.TimeoutException as error:
        raise LrclibUnavailableError(f"lrclib search timeout: {error}") from error

    data = _lrclib_json_or_unavailable(response)
    if isinstance(data, list) and data:
        best = rank_search_results(
            data,
            target_duration_s=duration_s,
            target_track=info.track_name,
            target_artist=info.artist_name,
        )
        if best and best.get("syncedLyrics"):
            parsed = parse_lrc(best["syncedLyrics"])
            logging.info(
                "LRCLIB /search hit for %s (%d lines, ranked from %d results)",
                info.track_name, len(parsed), len(data),
            )
            return parsed
        logging.info(
            "LRCLIB /search no acceptable match for %s (%d results)",
            info.track_name, len(data),
        )
        return None
    logging.info("LRCLIB /search no acceptable match for %s (0 results)", info.track_name)
    return None
```

- [ ] **Step 4: Run to verify pass**

```
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp -q tests/test_lyrics_worker.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```
git add src/lyrics_worker.py tests/test_lyrics_worker.py
git commit -m "feat(log): LRCLIB fetch logs /get and /search decision points (V1.5)"
```

---

## Task 3: `_ensure_auth` token pre-refresh — replace silent `pass` with warning

**Why:** `main.py:149` is `except Exception: pass`. This directly violates the project rule "看得見：把錯誤寫進 log，不要 except: pass" (`C:\Users\crayo\.claude\CLAUDE.md`). The intent is correct — fall through to full OAuth — but the failure must be visible.

**Files:**
- Modify: `src/main.py` `App._ensure_auth` (currently lines ~138–158; the relevant `except` is at ~149)
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_main.py`:

```python
import logging


def test_ensure_auth_warns_when_pre_refresh_fails_then_falls_through(caplog):
    app, config, _widget = _make_app()
    config.token_expires_at = 0  # force expired so the pre-refresh branch runs
    with (
        patch("src.main.is_token_expired", return_value=True),
        patch("src.main.refresh_access_token", side_effect=RuntimeError("refresh boom")),
        patch("src.main.run_oauth_flow",
              return_value={"access_token": "new", "expires_in": 3600}),
    ):
        caplog.set_level(logging.WARNING, logger="root")
        assert app._ensure_auth() is True

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert any("token pre-refresh failed" in r.message.lower()
               and "RuntimeError" in r.message
               and "refresh boom" in r.message
               and "oauth" in r.message.lower() for r in warnings), \
        f"expected pre-refresh fall-through warning, got: {[r.message for r in warnings]}"
```

- [ ] **Step 2: Run to verify it fails**

```
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp -q tests/test_main.py::test_ensure_auth_warns_when_pre_refresh_fails_then_falls_through -v
```

Expected: FAIL — no warning emitted today.

- [ ] **Step 3: Implement in `src/main.py`**

Add `import logging` near the top of `src/main.py` if not already present (search for `^import logging` first — many modules already have it).

Replace the silent except in `App._ensure_auth`:

```python
        if self._config.refresh_token:
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
```

- [ ] **Step 4: Run to verify pass**

```
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp -q tests/test_main.py -v
```

Expected: PASS (new test + all existing).

- [ ] **Step 5: Commit**

```
git add src/main.py tests/test_main.py
git commit -m "feat(log): warn on token pre-refresh failure instead of silent pass (V1.5)"
```

---

## Task 4: `spotify_worker._poll_once` — log network exception before emitting signal

**Why:** When Spotify is unreachable, today's `except (httpx.ConnectError, httpx.TimeoutException)` emits `network_error` but writes nothing to the log. If the user reports "widget said offline at 9 pm", we have no trace of when it started, what the exception was, or whether it was a timeout vs. connect failure. A single warning closes the gap.

**Files:**
- Modify: `src/spotify_worker.py` `_poll_once` (network-exception branch is at lines ~172–176)
- Test: `tests/test_spotify_worker.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_spotify_worker.py`:

```python
import logging


@patch("src.spotify_worker.httpx.get")
def test_poll_once_warns_with_concrete_reason_on_network_error(mock_get, caplog):
    from src.spotify_worker import SpotifyWorker
    mock_get.side_effect = httpx.ConnectError("no internet")
    config = MagicMock(
        access_token="tok", refresh_token="r", client_id="c",
        token_expires_at=time.time() + 3600,
    )
    worker = SpotifyWorker(config)
    caplog.set_level(logging.WARNING, logger="root")
    worker._poll_once()

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert any("Spotify currently-playing" in r.message
               and "ConnectError" in r.message
               and "no internet" in r.message for r in warnings), \
        f"expected concrete network-failure warning, got: {[r.message for r in warnings]}"
```

- [ ] **Step 2: Run to verify it fails**

```
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp -q tests/test_spotify_worker.py::test_poll_once_warns_with_concrete_reason_on_network_error -v
```

Expected: FAIL — no warning emitted today.

- [ ] **Step 3: Implement in `src/spotify_worker.py`**

Replace the exception branch in `_poll_once` (lines ~172–176):

```python
        try:
            response = self._make_spotify_request()
        except (httpx.ConnectError, httpx.TimeoutException) as error:
            logging.warning(
                "Spotify currently-playing request failed: %s: %s",
                type(error).__name__, error,
            )
            if not self._network_failed:
                self._network_failed = True
                self.network_error.emit()
            return
        except Exception:
            logging.exception("Unexpected error while polling Spotify")
            return
```

(`logging` is already imported in this file — see line ~135. No new import.)

- [ ] **Step 4: Run to verify pass**

```
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp -q tests/test_spotify_worker.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```
git add src/spotify_worker.py tests/test_spotify_worker.py
git commit -m "feat(log): warn with concrete reason on Spotify network exception (V1.5)"
```

---

## Task 5: Manual smoke + docs touch-up

- [ ] **Step 1: Full suite**

```
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp -q
```

Expected: all PASS (149 existing + the new ones from Tasks 1–4).

- [ ] **Step 2: Live smoke — capture three log fingerprints**

Launch the widget (`pythonw run.pyw`). Play three tracks chosen to exercise each path:

1. A song you know is on LRCLIB (e.g. one of the Crowd Lu tracks used during V1.4 verification) → `widget.log` must contain `LRCLIB /get hit for <track> (<N> lines)` and `emit lyrics_ready for <track> ... <N> lines`.
2. A song you know is an LRCLIB miss but NetEase has (e.g. `小宇宙 / 呂允` — confirmed in V1.4 acceptance) → `widget.log` must contain `LRCLIB /get 404 ... trying /search`, `LRCLIB /search no acceptable match ...`, the existing `NetEase fallback hit: ...`, and `emit lyrics_ready for <track> ... <N> lines`.
3. Force an LRCLIB unavailable by setting your network to airplane mode briefly while triggering a fetch (or just trust the negative test — this is the path V1.4 verification revealed). The log must contain `LRCLIB failed for <track> ...: <ExceptionClass>: <message>` and `emit lyrics_unavailable for <track>`.

If any expected line is missing, return to the relevant task — do not paper over.

- [ ] **Step 3: Update the roadmap + V1.4 plan**

In `docs/superpowers/plans/2026-05-25-roadmap.md`:

- Add a new row to the Roadmap table after V1.4: `**V1.5** | Logging hygiene (commits …). Closes silent `except` paths in `lyrics_worker.run()`, adds `/get` and `/search` decision logs in `fetch_lyrics_from_lrclib`, replaces `except Exception: pass` in `App._ensure_auth` with a warning, logs the `_poll_once` network exception before emitting `network_error`. No behaviour change. |`
- In "Current state (done)" add an entry summarising V1.5 with the commit hashes from Tasks 1–4.

In `docs/superpowers/plans/2026-05-26-spotify-lyrics-widget-v1-4.md` (the V1.4 plan), add a short "Verification recorded" subsection at the end of Task 6 noting the three live NetEase hits in `widget.log` on 2026-05-28 (`等待你那天`, `記得呼吸`, `空拍`) and the LRCLIB-unavailable symptom that motivated V1.5.

- [ ] **Step 4: Commit docs**

```
git add docs/superpowers/plans/2026-05-25-roadmap.md docs/superpowers/plans/2026-05-26-spotify-lyrics-widget-v1-4.md
git commit -m "docs: record V1.5 logging hygiene + V1.4 verification (V1.5)"
```

---

## Out of scope for V1.5 (do not implement here)

These were considered during the audit and explicitly deferred:

- **Design change: route LRCLIB-unavailable into NetEase as a salvage path.** This changes user-visible behaviour and inverts the V1.4 spec's intentional gate. Per `memory/codex-consensus-and-validate-before-adopting.md`, this requires Codex consensus + a live experiment first. Track it in a separate spec/plan, not here.
- **`Retry-After` parse fallbacks (`spotify_worker.py:238`, `netease.py:62`)** — silently fall back to defaults. Edge case only triggered by malformed server headers; not worth the noise for a single-user tool.
- **`auth.py` raise sites and `App._ensure_auth` OAuth-flow failure** — surface via `QMessageBox.critical` and the existing startup `logging.exception("Unhandled startup error")`. The user always sees a dialog; this is not silent.
- **`widget.py:111` DWM failure** — already logged with `logging.warning("DWM attribute request failed: %s", exc)`. Untouched.
- **`netease.py`** — every failure (cooldown, request error, 429, non-200, malformed JSON, no candidate, no timed lyric) is already logged with a concrete reason. Untouched.

---

## Self-Review

**Coverage of the requirements captured in the discussion (2026-05-28):**

| Discussion item | Task covering it |
|---|---|
| `lyrics_worker.run()` LRCLIB except is silent | Task 1 |
| `lyrics_worker.run()` NetEase except is silent | Task 1 |
| `lyrics_worker.run()` emits give no trace of which song / which path | Task 1 |
| Cache hit (lyrics / no_lyrics) gives no log trace | Task 1 |
| `fetch_lyrics_from_lrclib` decisions (`/get` 200-no-synced vs 404, `/search` rejected-all vs hit) are invisible | Task 2 |
| `main.py:149 except Exception: pass` violates "no silent except" rule | Task 3 |
| `spotify_worker._poll_once` connect/timeout exception is silent | Task 4 |
| Every log line carries concrete cause (status code / exception class / specific reason) | Tasks 1–4 — assertions in tests check class names + reason substrings |
| Out-of-scope design change (LRCLIB-unavailable → NetEase salvage) requires Codex consensus, not direct edits | "Out of scope" section |

**Placeholder scan:** none. Every step shows the exact code, the exact pytest command, and the exact commit message.

**Type / name consistency:** `info.track_name`, `info.track_id`, `info.duration_ms`, `info.artist_name`, `info.album_name` (from `TrackInfo` in `src/lyrics_worker.py:33`); `LrclibUnavailableError` from `src.lyrics_worker`; `NeteaseUnavailableError` from `src.netease`; `LyricsCache.MISS` / `LyricsCache.NO_LYRICS` sentinels from `src/lyrics_worker.py:49–50`; `_lrclib_json_or_unavailable` helper (line 20). All used consistently across tasks.

**No new behaviour:** every diff in Tasks 1–4 only adds `logging.*` calls plus the `as error` binding on existing `except` clauses. Signal emissions, return values, cache writes, and control flow are unchanged. Tests that pass today continue to pass after each task.

---

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-05-28-spotify-lyrics-widget-v1-5-logging-hygiene.md`.

Branch decision (to confirm with the user before Task 1): V1.4 is on `feature/v1-4-netease-fallback` and unmerged. V1.5 is a strict superset of V1.4 (no rebase risk; only additive log calls). Two reasonable options:

1. **Stack V1.5 onto the V1.4 branch** — single PR carries both V1.4 (feature, already verified) and V1.5 (hygiene). Simplest.
2. **Merge V1.4 first, then branch V1.5 off the merged master** — keeps each version isolated in history.

Task order is the execution order: Task 1 → 2 → 3 → 4 → 5. Each task ends in a green test run + commit, so a worker can stop after any task without leaving the tree broken.
