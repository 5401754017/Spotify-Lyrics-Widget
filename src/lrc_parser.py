import re
from bisect import bisect_right


_LRC_PATTERN = re.compile(r"\[(\d{2}):(\d{2})\.(\d{2,3})\]\s*(.*)")


def parse_lrc(lrc_text: str | None) -> list[tuple[int, str]]:
    """Parse LRC text into a sorted list of timestamp and lyric pairs."""
    if not lrc_text:
        return []

    lines = []
    for raw_line in lrc_text.strip().split("\n"):
        match = _LRC_PATTERN.match(raw_line.strip())
        if not match:
            continue

        minutes, seconds, centis, text = match.groups()
        text = text.strip()
        if not text:
            continue

        if len(centis) == 2:
            timestamp_ms = int(minutes) * 60000 + int(seconds) * 1000 + int(centis) * 10
        else:
            timestamp_ms = int(minutes) * 60000 + int(seconds) * 1000 + int(centis)
        lines.append((timestamp_ms, text))

    lines.sort(key=lambda line: line[0])
    return lines


def find_current_line(lines: list[tuple[int, str]], progress_ms: int) -> int:
    """Return the index of the last lyric line at or before progress_ms."""
    if not lines:
        return -1

    timestamps = [line[0] for line in lines]
    return bisect_right(timestamps, progress_ms) - 1
