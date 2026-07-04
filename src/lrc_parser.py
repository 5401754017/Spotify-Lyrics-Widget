import re
from bisect import bisect_right


_TS_PATTERN = re.compile(r"\[(\d{2}):(\d{2})[.:](\d{2,3})\]")


def parse_lrc(lrc_text: str | None) -> list[tuple[int, str]]:
    """Parse LRC text into a sorted list of (timestamp_ms, lyric) pairs.

    Supports multiple leading timestamps on one line ([t1][t2]text)."""
    if not lrc_text:
        return []

    lines = []
    for raw_line in lrc_text.strip().split("\n"):
        raw_line = raw_line.strip()
        timestamps = list(_TS_PATTERN.finditer(raw_line))
        if not timestamps:
            continue
        text = raw_line[timestamps[-1].end():].strip()
        if not text:
            continue
        for match in timestamps:
            minutes, seconds, frac = match.groups()
            ms = int(minutes) * 60000 + int(seconds) * 1000
            ms += int(frac) * 10 if len(frac) == 2 else int(frac)
            lines.append((ms, text))

    lines.sort(key=lambda line: line[0])
    return lines


def find_current_line(lines: list[tuple[int, str]], progress_ms: int) -> int:
    """Return the index of the last lyric line at or before progress_ms."""
    if not lines:
        return -1

    timestamps = [line[0] for line in lines]
    return bisect_right(timestamps, progress_ms) - 1


def should_blank_incomplete_tail(
    progress_ms: int,
    lines: list[tuple[int, str]],
    duration_ms: int,
    grace_ms: int = 6000,
    min_uncovered_ratio: float = 0.3,
) -> bool:
    """True when playback has run well past an incomplete lyric source's last line.

    A short source (e.g. a 4-line loop returned for a full song) otherwise freezes
    on its last line for the rest of the track. Blank only once playback is past that
    line by grace_ms AND the lyrics leave a large tail of the song uncovered, so a
    genuine last-line-near-the-end source keeps displaying normally."""
    if not lines or duration_ms <= 0:
        return False
    last_ts = lines[-1][0]
    if progress_ms <= last_ts + grace_ms:
        return False
    return (duration_ms - last_ts) >= duration_ms * min_uncovered_ratio
