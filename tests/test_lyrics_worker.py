import logging
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.lyrics_worker import LrclibUnavailableError, LyricsCache, TrackInfo, fetch_lyrics_from_lrclib, rank_search_results


class TestFetchLyrics:
    @patch("src.lyrics_worker.httpx.get")
    def test_exact_match_with_synced_lyrics(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "syncedLyrics": "[00:05.00] Hello\n[00:10.00] World",
                "plainLyrics": "Hello\nWorld",
            },
        )
        info = TrackInfo(
            track_id="t1",
            track_name="Song",
            artist_name="Artist",
            album_name="Album",
            duration_ms=180000,
        )
        result = fetch_lyrics_from_lrclib(info)
        assert result is not None
        assert len(result) == 2
        assert result[0] == (5000, "Hello")

    @patch("src.lyrics_worker.httpx.get")
    def test_exact_match_no_synced_lyrics_falls_to_search(self, mock_get):
        mock_get.side_effect = [
            MagicMock(
                status_code=200,
                json=lambda: {"syncedLyrics": None, "plainLyrics": "Hello"},
            ),
            MagicMock(
                status_code=200,
                json=lambda: [
                    {
                        "syncedLyrics": "[00:05.00] Found it",
                        "trackName": "Song",
                        "artistName": "Artist",
                        "duration": 180,
                    }
                ],
            ),
        ]
        info = TrackInfo(
            track_id="t1",
            track_name="Song",
            artist_name="Artist",
            album_name="Album",
            duration_ms=180000,
        )
        result = fetch_lyrics_from_lrclib(info)
        assert result is not None
        assert result[0] == (5000, "Found it")

    @patch("src.lyrics_worker.httpx.get")
    def test_both_fail_returns_none(self, mock_get):
        mock_get.side_effect = [
            MagicMock(status_code=404, json=lambda: {}),
            MagicMock(status_code=200, json=lambda: []),
        ]
        info = TrackInfo(
            track_id="t1",
            track_name="Song",
            artist_name="Artist",
            album_name="Album",
            duration_ms=180000,
        )
        result = fetch_lyrics_from_lrclib(info)
        assert result is None

    @patch("src.lyrics_worker.httpx.get")
    def test_network_error_raises(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("No internet")
        info = TrackInfo(
            track_id="t1",
            track_name="Song",
            artist_name="Artist",
            album_name="Album",
            duration_ms=180000,
        )
        import pytest

        with pytest.raises(httpx.ConnectError):
            fetch_lyrics_from_lrclib(info)

    @patch("src.lyrics_worker.httpx.get")
    def test_5xx_raises_unavailable(self, mock_get):
        from src.lyrics_worker import LrclibUnavailableError

        mock_get.return_value = MagicMock(status_code=503)
        info = TrackInfo(
            track_id="t1",
            track_name="Song",
            artist_name="Artist",
            album_name="Album",
            duration_ms=180000,
        )
        import pytest

        with pytest.raises(LrclibUnavailableError):
            fetch_lyrics_from_lrclib(info)

    @patch("src.lyrics_worker.httpx.get")
    def test_search_5xx_raises_unavailable(self, mock_get):
        from src.lyrics_worker import LrclibUnavailableError

        mock_get.side_effect = [
            MagicMock(status_code=404, json=lambda: {}),
            MagicMock(status_code=500),
        ]
        info = TrackInfo(
            track_id="t1",
            track_name="Song",
            artist_name="Artist",
            album_name="Album",
            duration_ms=180000,
        )
        import pytest

        with pytest.raises(LrclibUnavailableError):
            fetch_lyrics_from_lrclib(info)


class TestRankSearchResults:
    def test_prefers_closest_duration(self):
        results = [
            {
                "syncedLyrics": "[00:01.00] A",
                "trackName": "Song",
                "artistName": "Artist",
                "duration": 300,
            },
            {
                "syncedLyrics": "[00:01.00] B",
                "trackName": "Song",
                "artistName": "Artist",
                "duration": 181,
            },
        ]
        best = rank_search_results(
            results,
            target_duration_s=180,
            target_track="Song",
            target_artist="Artist",
        )
        assert best["duration"] == 181

    def test_skips_results_without_synced_lyrics(self):
        results = [
            {
                "syncedLyrics": None,
                "trackName": "Song",
                "artistName": "Artist",
                "duration": 180,
            },
            {
                "syncedLyrics": "[00:01.00] B",
                "trackName": "Song",
                "artistName": "Artist",
                "duration": 180,
            },
        ]
        best = rank_search_results(
            results,
            target_duration_s=180,
            target_track="Song",
            target_artist="Artist",
        )
        assert best["syncedLyrics"] == "[00:01.00] B"

    def test_rejects_all_without_synced(self):
        results = [
            {
                "syncedLyrics": None,
                "trackName": "Song",
                "artistName": "Artist",
                "duration": 180,
            }
        ]
        best = rank_search_results(
            results,
            target_duration_s=180,
            target_track="Song",
            target_artist="Artist",
        )
        assert best is None

    def test_rejects_duration_beyond_tolerance(self):
        results = [
            {
                "syncedLyrics": "[00:01.00] A",
                "trackName": "Song",
                "artistName": "Artist",
                "duration": 300,
            }
        ]
        best = rank_search_results(
            results,
            target_duration_s=180,
            target_track="Song",
            target_artist="Artist",
        )
        assert best is None

    def test_empty_results(self):
        best = rank_search_results(
            [],
            target_duration_s=180,
            target_track="Song",
            target_artist="Artist",
        )
        assert best is None

    def test_normalized_matching_ignores_punctuation(self):
        results = [
            {
                "syncedLyrics": "[00:01.00] A",
                "trackName": "Don't Stop Me Now",
                "artistName": "Queen",
                "duration": 180,
            }
        ]
        best = rank_search_results(
            results,
            target_duration_s=180,
            target_track="Dont Stop Me Now",
            target_artist="Queen",
        )
        assert best is not None

    def test_normalized_matching_ignores_remaster_suffix(self):
        results = [
            {
                "syncedLyrics": "[00:01.00] A",
                "trackName": "Bohemian Rhapsody - Remastered 2011",
                "artistName": "Queen",
                "duration": 355,
            }
        ]
        best = rank_search_results(
            results,
            target_duration_s=354,
            target_track="Bohemian Rhapsody",
            target_artist="Queen",
        )
        assert best is not None

    def test_rejects_wrong_title_even_if_artist_and_duration_match(self):
        results = [
            {
                "syncedLyrics": "[00:01.00] A",
                "trackName": "So Innocent",
                "artistName": "Shiloh Dynasty",
                "duration": 180,
            }
        ]
        best = rank_search_results(
            results,
            target_duration_s=180,
            target_track="Novocaine",
            target_artist="Shiloh Dynasty",
        )
        assert best is None

    def test_prefers_exact_name_over_partial(self):
        results = [
            {
                "syncedLyrics": "[00:01.00] A",
                "trackName": "Hello",
                "artistName": "Adele",
                "duration": 180,
            },
            {
                "syncedLyrics": "[00:01.00] B",
                "trackName": "Hello World",
                "artistName": "Adele",
                "duration": 180,
            },
        ]
        best = rank_search_results(
            results,
            target_duration_s=180,
            target_track="Hello",
            target_artist="Adele",
        )
        assert best["trackName"] == "Hello"


class TestLyricsCache:
    def test_cache_hit(self):
        cache = LyricsCache()
        cache.set("t1", [(5000, "Hello")])
        assert cache.get("t1") == [(5000, "Hello")]

    def test_cache_miss(self):
        cache = LyricsCache()
        assert cache.get("unknown") is cache.MISS

    def test_cache_no_lyrics(self):
        cache = LyricsCache()
        cache.set_no_lyrics("t2")
        assert cache.get("t2") is cache.NO_LYRICS

    def test_cache_does_not_store_transient_failure(self):
        cache = LyricsCache()
        assert cache.get("t3") is cache.MISS


def test_lrclib_429_is_unavailable_not_miss():
    from src.lyrics_worker import LrclibUnavailableError, fetch_lyrics_from_lrclib, TrackInfo

    info = TrackInfo("t1", "Song", "Artist", "Album", 180000)
    with patch("src.lyrics_worker.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=429, headers={"Retry-After": "30"}, text="rl")
        with pytest.raises(LrclibUnavailableError):
            fetch_lyrics_from_lrclib(info)


def test_lrclib_malformed_json_is_unavailable_not_crash():
    from src.lyrics_worker import LrclibUnavailableError, fetch_lyrics_from_lrclib, TrackInfo

    info = TrackInfo("t1", "Song", "Artist", "Album", 180000)
    bad = MagicMock(status_code=200, text="<html>")
    bad.json.side_effect = ValueError("no json")
    with patch("src.lyrics_worker.httpx.get", return_value=bad):
        with pytest.raises(LrclibUnavailableError):
            fetch_lyrics_from_lrclib(info)


def _pending_worker(netease_fallback):
    from src.lyrics_worker import LyricsWorker
    worker = LyricsWorker(netease_fallback=netease_fallback)
    worker._pending_track = TrackInfo("t1", "Song", "Artist", "Album", 180000)
    worker._has_work = True
    return worker


@patch("src.lyrics_worker.fetch_lyrics_from_netease", return_value=[(1000, "ne")])
@patch("src.lyrics_worker.fetch_lyrics_from_lrclib", return_value=None)
def test_falls_back_to_netease_when_lrclib_misses(mock_lrclib, mock_netease, qtbot):
    worker = _pending_worker(netease_fallback=True)
    ready = []
    worker.lyrics_ready.connect(lambda tid, lyr: ready.append((tid, lyr)))
    worker.run()
    mock_netease.assert_called_once_with("Song", "Artist", 180000)
    assert ready == [("t1", [(1000, "ne")])]


@patch("src.lyrics_worker.fetch_lyrics_from_netease")
@patch("src.lyrics_worker.fetch_lyrics_from_lrclib", return_value=None)
def test_netease_not_called_when_disabled(mock_lrclib, mock_netease, qtbot):
    worker = _pending_worker(netease_fallback=False)
    misses = []
    worker.no_lyrics.connect(lambda tid: misses.append(tid))
    worker.run()
    mock_netease.assert_not_called()
    assert misses == ["t1"]


@patch("src.lyrics_worker.fetch_lyrics_from_netease", return_value=[(1000, "ne")])
@patch("src.lyrics_worker.fetch_lyrics_from_lrclib", side_effect=LrclibUnavailableError("rl"))
def test_lrclib_unavailable_tries_netease_salvage(mock_lrclib, mock_netease, qtbot):
    worker = _pending_worker(netease_fallback=True)
    ready, unavailable = [], []
    worker.lyrics_ready.connect(lambda tid, lyr: ready.append((tid, lyr)))
    worker.lyrics_unavailable.connect(lambda tid: unavailable.append(tid))
    worker.run()
    mock_netease.assert_called_once_with("Song", "Artist", 180000)
    assert ready == [("t1", [(1000, "ne")])]
    assert unavailable == []
    assert worker._cache.get("t1") == [(1000, "ne")]


@patch("src.lyrics_worker.fetch_lyrics_from_netease", return_value=None)
@patch("src.lyrics_worker.fetch_lyrics_from_lrclib", side_effect=LrclibUnavailableError("rl"))
def test_lrclib_unavailable_netease_miss_does_not_cache_no_lyrics(mock_lrclib, mock_netease, qtbot):
    worker = _pending_worker(netease_fallback=True)
    unavailable, misses = [], []
    worker.lyrics_unavailable.connect(lambda tid: unavailable.append(tid))
    worker.no_lyrics.connect(lambda tid: misses.append(tid))
    worker.run()
    mock_netease.assert_called_once_with("Song", "Artist", 180000)
    assert unavailable == ["t1"]
    assert misses == []
    assert worker._cache.get("t1") is worker._cache.MISS


@patch("src.lyrics_worker.fetch_lyrics_from_netease")
@patch("src.lyrics_worker.fetch_lyrics_from_lrclib", return_value=None)
def test_netease_unavailable_emits_unavailable_without_caching(mock_lrclib, mock_netease, qtbot):
    from src.netease import NeteaseUnavailableError
    mock_netease.side_effect = NeteaseUnavailableError("rl")
    worker = _pending_worker(netease_fallback=True)
    unavailable, misses = [], []
    worker.lyrics_unavailable.connect(lambda tid: unavailable.append(tid))
    worker.no_lyrics.connect(lambda tid: misses.append(tid))
    worker.run()
    assert unavailable == ["t1"] and misses == []
    assert worker._cache.get("t1") is worker._cache.MISS


@patch("src.lyrics_worker.fetch_lyrics_from_netease", return_value=None)
@patch("src.lyrics_worker.fetch_lyrics_from_lrclib", return_value=None)
def test_both_miss_caches_no_lyrics(mock_lrclib, mock_netease, qtbot):
    worker = _pending_worker(netease_fallback=True)
    worker.run()
    assert worker._cache.get("t1") is worker._cache.NO_LYRICS


# ---- V1.5 Task 1: worker exit-point logging ----


@patch("src.lyrics_worker.fetch_lyrics_from_lrclib",
       side_effect=LrclibUnavailableError("lrclib search timeout: read timed out"))
def test_run_warns_on_lrclib_unavailable_with_concrete_reason(mock_lrclib, qtbot, caplog):
    worker = _pending_worker(netease_fallback=False)
    caplog.set_level(logging.INFO)
    worker.run()
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    infos = [r for r in caplog.records if r.levelname == "INFO"]
    assert any("LRCLIB unavailable" in r.message and "Song" in r.message
               and "search timeout" in r.message for r in warnings), \
        f"expected concrete LRCLIB-failure warning, got: {[r.message for r in warnings]}"
    assert any("lyrics_unavailable" in r.message and "t1" in r.message for r in infos)


@patch("src.lyrics_worker.fetch_lyrics_from_netease")
@patch("src.lyrics_worker.fetch_lyrics_from_lrclib", return_value=None)
def test_run_warns_on_netease_unavailable_with_concrete_reason(mock_lrclib, mock_netease, qtbot, caplog):
    from src.netease import NeteaseUnavailableError
    mock_netease.side_effect = NeteaseUnavailableError("NetEase rate limited")
    worker = _pending_worker(netease_fallback=True)
    caplog.set_level(logging.INFO)
    worker.run()
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert any("NetEase failed" in r.message and "Song" in r.message
               and "rate limited" in r.message for r in warnings), \
        f"expected concrete NetEase-failure warning, got: {[r.message for r in warnings]}"


@patch("src.lyrics_worker.fetch_lyrics_from_lrclib", return_value=[(1000, "hi")])
def test_run_logs_lyrics_ready_emit(mock_lrclib, qtbot, caplog):
    worker = _pending_worker(netease_fallback=False)
    caplog.set_level(logging.INFO)
    worker.run()
    infos = [r for r in caplog.records if r.levelname == "INFO"]
    assert any("lyrics_ready" in r.message and "t1" in r.message
               and "1 lines" in r.message for r in infos)


@patch("src.lyrics_worker.fetch_lyrics_from_netease", return_value=None)
@patch("src.lyrics_worker.fetch_lyrics_from_lrclib", return_value=None)
def test_run_logs_no_lyrics_emit_with_both_miss(mock_lrclib, mock_netease, qtbot, caplog):
    worker = _pending_worker(netease_fallback=True)
    caplog.set_level(logging.INFO)
    worker.run()
    infos = [r for r in caplog.records if r.levelname == "INFO"]
    assert any("no_lyrics" in r.message and "t1" in r.message
               and "both" in r.message.lower() for r in infos)


def test_run_logs_cache_hit_lyrics(qtbot, caplog):
    worker = _pending_worker(netease_fallback=True)
    worker._cache.set("t1", [(0, "cached")])
    caplog.set_level(logging.INFO)
    worker.run()
    infos = [r for r in caplog.records if r.levelname == "INFO"]
    assert any("cache hit" in r.message and "t1" in r.message
               and "1 lines" in r.message for r in infos)


def test_run_logs_cache_hit_no_lyrics(qtbot, caplog):
    worker = _pending_worker(netease_fallback=True)
    worker._cache.set_no_lyrics("t1")
    caplog.set_level(logging.INFO)
    worker.run()
    infos = [r for r in caplog.records if r.levelname == "INFO"]
    assert any("cache hit" in r.message and "t1" in r.message
               and "no lyrics" in r.message for r in infos)


# ---- V1.5 Task 2: LRCLIB fetch decision-point logging ----


class TestLrclibFetchLogs:
    @patch("src.lyrics_worker.httpx.get")
    def test_get_hit_logs_one_line(self, mock_get, caplog):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"syncedLyrics": "[00:01.00]hi"},
        )
        info = TrackInfo("t1", "Song", "Artist", "Album", 180000)
        caplog.set_level(logging.INFO)
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
        caplog.set_level(logging.INFO)
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
        caplog.set_level(logging.INFO)
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
        caplog.set_level(logging.INFO)
        result = fetch_lyrics_from_lrclib(info)
        assert result is None
        messages = [r.message for r in caplog.records]
        assert any("/search no acceptable match" in m and "1 results" in m for m in messages)
