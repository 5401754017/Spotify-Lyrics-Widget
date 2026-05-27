import logging
import re
import time

import httpx
import zhconv

from src.lrc_parser import parse_lrc

NETEASE_SEARCH_URL = "https://music.163.com/api/search/get/web"
NETEASE_LYRIC_URL = "https://music.163.com/api/song/lyric"
MAX_CANDIDATES = 3
DURATION_TOLERANCE_S = 5
DEFAULT_RETRY_AFTER_S = 30
DEFAULT_UNAVAILABLE_BACKOFF_S = 60
_HEADERS = {
    "Referer": "https://music.163.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
}
_CREDIT_PREFIXES = {
    "作词", "作曲", "编曲", "制作人", "出品", "监制", "演唱", "演奏", "和声",
    "混音", "录音", "母带", "producer", "composer", "lyricist", "arranger", "mixing",
}
_cooldown_until = 0.0


class NeteaseUnavailableError(RuntimeError):
    """NetEase temporarily unavailable; caller must not cache this as a miss."""


def _to_simplified(text: str) -> str:
    return zhconv.convert(text or "", "zh-cn")


def _to_traditional(text: str) -> str:
    return zhconv.convert(text or "", "zh-tw")


def _normalize(text: str) -> str:
    text = _to_simplified(text).lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\b(remaster(ed)?|deluxe|live|remix|version|edit|original)\b", "", text)
    return text.strip()


def _cooldown_remaining() -> float:
    return max(0.0, _cooldown_until - time.monotonic())


def _set_cooldown(seconds: int) -> None:
    global _cooldown_until
    _cooldown_until = time.monotonic() + max(1, seconds)


def _retry_after_seconds(response) -> int:
    value = response.headers.get("Retry-After")
    if not value:
        return DEFAULT_RETRY_AFTER_S
    try:
        return max(1, int(value))
    except ValueError:
        return DEFAULT_RETRY_AFTER_S


def _request_json(url: str, params: dict) -> dict:
    remaining = _cooldown_remaining()
    if remaining > 0:
        logging.warning("NetEase fallback unavailable: cooldown active for %.0fs", remaining)
        raise NeteaseUnavailableError("NetEase cooldown active")
    try:
        response = httpx.get(url, params=params, headers=_HEADERS, timeout=5.0)
    except httpx.RequestError as exc:
        _set_cooldown(DEFAULT_UNAVAILABLE_BACKOFF_S)
        logging.warning("NetEase fallback unavailable: request error: %s", exc)
        raise NeteaseUnavailableError("NetEase request failed") from exc

    if response.status_code == 429:
        retry_after = _retry_after_seconds(response)
        _set_cooldown(retry_after)
        logging.warning("NetEase fallback unavailable: 429, retry after %ss", retry_after)
        raise NeteaseUnavailableError("NetEase rate limited")
    if response.status_code != 200:
        _set_cooldown(DEFAULT_UNAVAILABLE_BACKOFF_S)
        logging.warning("NetEase fallback unavailable: HTTP %s: %.120s",
                        response.status_code, response.text)
        raise NeteaseUnavailableError(f"NetEase HTTP {response.status_code}")
    try:
        return response.json() or {}
    except ValueError as exc:
        _set_cooldown(DEFAULT_UNAVAILABLE_BACKOFF_S)
        logging.warning("NetEase fallback unavailable: malformed JSON: %.120s", response.text)
        raise NeteaseUnavailableError("NetEase malformed JSON") from exc


def search_netease(track_name: str, artist_name: str) -> list[dict]:
    data = _request_json(NETEASE_SEARCH_URL,
                         params={"s": f"{track_name} {artist_name}", "type": 1, "limit": 10})
    return (data.get("result") or {}).get("songs") or []


def rank_netease_songs(songs, target_track, target_artist, target_duration_s) -> list[dict]:
    """Return up to MAX_CANDIDATES ranked songs; reject weak textual matches outright."""
    nt, na = _normalize(target_track), _normalize(target_artist)
    scored = []
    for song in songs:
        st = _normalize(song.get("name", ""))
        artists = song.get("artists") or []
        sa = _normalize(", ".join(a.get("name", "") for a in artists))
        name_match = 0 if st == nt else (5 if nt and (nt in st or st in nt) else 10)
        artist_match = 0 if sa == na else (5 if na and (na in sa or sa in na) else 10)
        text_score = name_match + artist_match
        if text_score >= 20:  # both unmatched → wrong song; wrong lyrics worse than none
            continue
        dur_diff = abs(song.get("duration", 0) // 1000 - target_duration_s)
        if dur_diff <= DURATION_TOLERANCE_S:
            dur_penalty = 0.0
        elif text_score == 0:           # exact title+artist → tolerate drift cheaply
            dur_penalty = (dur_diff - DURATION_TOLERANCE_S) * 0.2
        else:                            # weaker text → drift counts more
            dur_penalty = float(dur_diff)
        scored.append((text_score + dur_penalty, song))
    scored.sort(key=lambda item: item[0])
    return [song for _, song in scored[:MAX_CANDIDATES]]


def fetch_netease_lyric(song_id) -> str | None:
    data = _request_json(NETEASE_LYRIC_URL,
                         params={"id": song_id, "lv": -1, "kv": -1, "tv": -1})
    return (data.get("lrc") or {}).get("lyric")


def _is_credit_line(text: str) -> bool:
    match = re.match(r"\s*([^\s:：]+)\s*[:：]", text)
    return bool(match) and match.group(1).lower() in _CREDIT_PREFIXES


def _clean_lyric(parsed: list[tuple[int, str]]) -> list[tuple[int, str]]:
    return [(ts, _to_traditional(text)) for ts, text in parsed if not _is_credit_line(text)]


def fetch_lyrics_from_netease(track_name, artist_name, duration_ms) -> list[tuple[int, str]] | None:
    """Best-effort NetEase synced lyrics, Traditionalized.

    None only for confirmed no-match / no-usable-lyric. Temporary failures raise
    NeteaseUnavailableError. Tries up to MAX_CANDIDATES ranked candidates and requires
    parsed timed lines (the top search hit can be an untimed cover)."""
    songs = search_netease(track_name, artist_name)
    candidates = rank_netease_songs(songs, track_name, artist_name, duration_ms // 1000)
    if not candidates:
        logging.info("NetEase fallback miss: no candidate for %s - %s", track_name, artist_name)
        return None
    for candidate in candidates:
        lyric_text = fetch_netease_lyric(candidate["id"])
        if not lyric_text:
            continue
        cleaned = _clean_lyric(parse_lrc(lyric_text))
        if cleaned:
            logging.info("NetEase fallback hit: %s (for %s)", candidate.get("name"), track_name)
            return cleaned
    logging.info("NetEase fallback miss: no timed lyric among candidates for %s", track_name)
    return None
