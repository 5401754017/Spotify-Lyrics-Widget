from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.lyrics_worker import LyricsCache, TrackInfo, fetch_lyrics_from_lrclib, rank_search_results


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
