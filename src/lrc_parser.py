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
