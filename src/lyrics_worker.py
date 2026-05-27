import re
from dataclasses import dataclass
from enum import Enum, auto

import httpx
from PyQt6.QtCore import QThread, pyqtSignal

from src.lrc_parser import parse_lrc
from src.netease import NeteaseUnavailableError, fetch_lyrics_from_netease


LRCLIB_BASE = "https://lrclib.net/api"
DURATION_TOLERANCE_S = 5


class LrclibUnavailableError(Exception):
    """Raised when LRCLIB has a transient server or timeout failure."""


def _lrclib_json_or_unavailable(response):
    if response.status_code == 429:
        raise LrclibUnavailableError(f"lrclib rate limited: {response.status_code}")
    if response.status_code >= 500:
        raise LrclibUnavailableError(f"lrclib server error: {response.status_code}")
    if response.status_code != 200:
        return None  # e.g. /get 404 -> caller falls through to /search
    try:
        return response.json()
    except ValueError as error:
        raise LrclibUnavailableError(f"lrclib malformed JSON: {error}") from error


@dataclass
class TrackInfo:
    track_id: str
    track_name: str
    artist_name: str
    album_name: str
    duration_ms: int


class LyricsCache:
    """Session cache for lyrics lookups by Spotify track ID."""

    class _Sentinel(Enum):
        MISS = auto()
        NO_LYRICS = auto()

    MISS = _Sentinel.MISS
    NO_LYRICS = _Sentinel.NO_LYRICS

    def __init__(self):
        self._store = {}

    def get(self, track_id: str):
        return self._store.get(track_id, self.MISS)

    def set(self, track_id: str, lyrics: list[tuple[int, str]]):
        self._store[track_id] = lyrics

    def set_no_lyrics(self, track_id: str):
        self._store[track_id] = self.NO_LYRICS


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(
        r"\b(remaster(ed)?|deluxe|live|remix|version|edit|original)\b",
        "",
        text,
    )
    return text.strip()


def rank_search_results(
    results: list[dict],
    target_duration_s: int,
    target_track: str,
    target_artist: str,
) -> dict | None:
    """Return the closest synced LRCLIB search result."""
    normalized_track = _normalize(target_track)
    normalized_artist = _normalize(target_artist)
    candidates = []

    for result in results:
        if not result.get("syncedLyrics"):
            continue

        duration = result.get("duration", 0)
        duration_diff = abs(duration - target_duration_s)
        if duration_diff > DURATION_TOLERANCE_S:
            continue

        result_track = _normalize(result.get("trackName", ""))
        result_artist = _normalize(result.get("artistName", ""))
        name_match = (
            0
            if result_track == normalized_track
            else (
                5
                if normalized_track in result_track or result_track in normalized_track
                else 10
            )
        )
        artist_match = (
            0
            if result_artist == normalized_artist
            else (
                5
                if normalized_artist in result_artist
                or result_artist in normalized_artist
                else 10
            )
        )
        candidates.append((duration_diff + name_match + artist_match, result))

    if not candidates:
        return None

    candidates.sort(key=lambda candidate: candidate[0])
    return candidates[0][1]


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

    data = _lrclib_json_or_unavailable(response)
    if data:
        synced_lyrics = data.get("syncedLyrics")
        if synced_lyrics:
            return parse_lrc(synced_lyrics)

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
            return parse_lrc(best["syncedLyrics"])
    return None


class LyricsWorker(QThread):
    """Fetch lyrics in a worker thread when the track changes."""

    lyrics_ready = pyqtSignal(str, list)
    no_lyrics = pyqtSignal(str)
    lyrics_unavailable = pyqtSignal(str)

    def __init__(self, netease_fallback: bool = True):
        super().__init__()
        self._cache = LyricsCache()
        self._pending_track: TrackInfo | None = None
        self._has_work = False
        self._netease_fallback = netease_fallback

    def request_lyrics(self, track_info: TrackInfo):
        self._pending_track = track_info
        self._has_work = True
        if not self.isRunning():
            self.start()

    def run(self):
        while self._has_work:
            self._has_work = False
            info = self._pending_track
            if info is None:
                return

            cached = self._cache.get(info.track_id)
            if cached is not LyricsCache.MISS:
                if cached is LyricsCache.NO_LYRICS:
                    self.no_lyrics.emit(info.track_id)
                else:
                    self.lyrics_ready.emit(info.track_id, cached)
                return

            try:
                result = fetch_lyrics_from_lrclib(info)
            except (httpx.ConnectError, LrclibUnavailableError):
                self.lyrics_unavailable.emit(info.track_id)
                return

            if not result and self._netease_fallback:
                try:
                    result = fetch_lyrics_from_netease(
                        info.track_name, info.artist_name, info.duration_ms
                    )
                except NeteaseUnavailableError:
                    self.lyrics_unavailable.emit(info.track_id)
                    return

            if result:
                self._cache.set(info.track_id, result)
                self.lyrics_ready.emit(info.track_id, result)
            else:
                self._cache.set_no_lyrics(info.track_id)
                self.no_lyrics.emit(info.track_id)
