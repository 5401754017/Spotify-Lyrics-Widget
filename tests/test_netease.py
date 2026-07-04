from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.netease import (
    NeteaseUnavailableError,
    fetch_lyrics_from_netease,
    rank_netease_songs,
    search_netease,
)


@pytest.fixture(autouse=True)
def reset_cooldown(monkeypatch):
    monkeypatch.setattr("src.netease._cooldown_until", 0.0, raising=False)


def _song(song_id, name, artist, duration_ms):
    return {"id": song_id, "name": name, "artists": [{"name": artist}],
            "duration": duration_ms, "album": {"name": "Album"}}


class TestRanking:
    def test_traditional_query_matches_simplified_result(self):
        songs = [_song(1, "晴天", "周杰伦", 269000)]
        ranked = rank_netease_songs(songs, "晴天", "周杰倫", target_duration_s=269)
        assert ranked and ranked[0]["id"] == 1

    def test_prefers_closest_duration_as_tiebreaker(self):
        songs = [_song(1, "Song", "Artist", 300000), _song(2, "Song", "Artist", 181000)]
        ranked = rank_netease_songs(songs, "Song", "Artist", target_duration_s=180)
        assert ranked[0]["id"] == 2

    def test_rejects_weak_text_match_even_if_duration_close(self):
        songs = [_song(1, "Totally Different", "Nobody", 180000)]
        assert rank_netease_songs(songs, "Song", "Artist", target_duration_s=180) == []

    def test_rejects_wrong_title_even_if_artist_matches(self):
        # Regression: "So Innocent" (same artist) was used as lyrics for "Novocaine"
        songs = [_song(1, "So Innocent", "Shiloh Dynasty", 150000)]
        assert rank_netease_songs(songs, "Novocaine", "Shiloh Dynasty", target_duration_s=137) == []

    def test_returns_at_most_three(self):
        songs = [_song(i, "Song", "Artist", 180000) for i in range(6)]
        assert len(rank_netease_songs(songs, "Song", "Artist", 180)) <= 3


class TestSearch:
    @patch("src.netease.httpx.get")
    def test_returns_song_list(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200,
            json=lambda: {"result": {"songs": [_song(1, "Song", "Artist", 180000)]}})
        assert search_netease("Song", "Artist")[0]["id"] == 1

    @patch("src.netease.httpx.get")
    def test_non_200_raises_unavailable(self, mock_get):
        mock_get.return_value = MagicMock(status_code=403, text="blocked", json=lambda: {})
        with pytest.raises(NeteaseUnavailableError):
            search_netease("Song", "Artist")


class TestFetch:
    @patch("src.netease.httpx.get")
    def test_skips_untimed_cover_uses_next_candidate(self, mock_get):
        # search → 2 candidates; first lyric untimed (cover), second timed
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"result": {"songs": [
                _song(11, "Song", "Artist", 180000), _song(12, "Song", "Artist", 180500)]}}),
            MagicMock(status_code=200, json=lambda: {"lrc": {"lyric": "plain no timestamps"}}),
            MagicMock(status_code=200, json=lambda: {"lrc": {"lyric": "[00:05.00] 你好"}}),
        ]
        result = fetch_lyrics_from_netease("Song", "Artist", 180000)
        assert result == [(5000, "你好")]

    @patch("src.netease.httpx.get")
    def test_filters_credit_lines_and_traditionalizes(self, mock_get):
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"result": {"songs": [_song(11, "光年之外", "邓紫棋", 235000)]}}),
            MagicMock(status_code=200, json=lambda: {"lrc": {"lyric":
                "[00:00.00] 作词 : 邓紫棋\n[00:05.00] 梦想"}}),
        ]
        result = fetch_lyrics_from_netease("光年之外", "鄧紫棋", 235000)
        assert result == [(5000, "夢想")]  # credit dropped, 梦→夢 Traditionalized

    @patch("src.netease.httpx.get")
    def test_no_candidate_returns_none(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"result": {"songs": []}})
        assert fetch_lyrics_from_netease("Song", "Artist", 180000) is None

    @patch("src.netease.httpx.get")
    def test_all_candidates_untimed_returns_none(self, mock_get):
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"result": {"songs": [_song(11, "Song", "Artist", 180000)]}}),
            MagicMock(status_code=200, json=lambda: {"lrc": {"lyric": "plain"}}),
        ]
        assert fetch_lyrics_from_netease("Song", "Artist", 180000) is None

    @patch("src.netease.httpx.get")
    def test_network_error_raises_unavailable(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("no internet")
        with pytest.raises(NeteaseUnavailableError):
            fetch_lyrics_from_netease("Song", "Artist", 180000)

    @patch("src.netease.httpx.get")
    def test_429_sets_cooldown_then_skips_http(self, mock_get):
        mock_get.return_value = MagicMock(status_code=429, headers={"Retry-After": "30"}, text="rl", json=lambda: {})
        with pytest.raises(NeteaseUnavailableError):
            fetch_lyrics_from_netease("Song", "Artist", 180000)
        mock_get.reset_mock()
        with pytest.raises(NeteaseUnavailableError):
            fetch_lyrics_from_netease("Song", "Artist", 180000)
        mock_get.assert_not_called()

    @patch("src.netease.httpx.get")
    def test_non_429_unavailable_also_sets_cooldown(self, mock_get):
        mock_get.return_value = MagicMock(status_code=403, text="blocked", json=lambda: {})
        with pytest.raises(NeteaseUnavailableError):
            fetch_lyrics_from_netease("Song", "Artist", 180000)
        mock_get.reset_mock()
        with pytest.raises(NeteaseUnavailableError):
            fetch_lyrics_from_netease("Song", "Artist", 180000)
        mock_get.assert_not_called()
