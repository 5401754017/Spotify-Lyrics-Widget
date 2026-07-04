from src.lrc_parser import (
    find_current_line,
    parse_lrc,
    should_blank_incomplete_tail,
)


class TestParseLrc:
    def test_basic_parsing(self):
        lrc = "[00:12.34] Hello world\n[00:15.00] Second line\n[01:00.50] Third line"
        result = parse_lrc(lrc)
        assert result == [
            (12340, "Hello world"),
            (15000, "Second line"),
            (60500, "Third line"),
        ]

    def test_strips_whitespace(self):
        lrc = "[00:05.00]  Leading spaces  \n[00:10.00]Trailing  "
        result = parse_lrc(lrc)
        assert result == [
            (5000, "Leading spaces"),
            (10000, "Trailing"),
        ]

    def test_empty_string(self):
        assert parse_lrc("") == []

    def test_none_input(self):
        assert parse_lrc(None) == []

    def test_skips_invalid_lines(self):
        lrc = "[00:05.00] Valid\nno timestamp here\n[bad] Also bad\n[00:10.00] Also valid"
        result = parse_lrc(lrc)
        assert result == [
            (5000, "Valid"),
            (10000, "Also valid"),
        ]

    def test_skips_empty_lyric_lines(self):
        lrc = "[00:05.00] Valid\n[00:10.00] \n[00:15.00] Also valid"
        result = parse_lrc(lrc)
        assert result == [
            (5000, "Valid"),
            (15000, "Also valid"),
        ]

    def test_sorted_output(self):
        lrc = "[00:20.00] Second\n[00:05.00] First"
        result = parse_lrc(lrc)
        assert result == [
            (5000, "First"),
            (20000, "Second"),
        ]

    def test_two_digit_minutes(self):
        lrc = "[12:34.56] Late in song"
        result = parse_lrc(lrc)
        assert result == [(754560, "Late in song")]


class TestFindCurrentLine:
    def test_before_first_line(self):
        lines = [(5000, "First"), (10000, "Second")]
        assert find_current_line(lines, 3000) == -1

    def test_exact_match_first(self):
        lines = [(5000, "First"), (10000, "Second")]
        assert find_current_line(lines, 5000) == 0

    def test_between_lines(self):
        lines = [(5000, "First"), (10000, "Second"), (15000, "Third")]
        assert find_current_line(lines, 12000) == 1

    def test_after_last_line(self):
        lines = [(5000, "First"), (10000, "Second")]
        assert find_current_line(lines, 99000) == 1

    def test_empty_list(self):
        assert find_current_line([], 5000) == -1

    def test_exact_match_last(self):
        lines = [(5000, "First"), (10000, "Second")]
        assert find_current_line(lines, 10000) == 1


class TestShouldBlankIncompleteTail:
    def test_blanks_when_far_past_last_line_and_source_incomplete(self):
        lines = [(2000, "a"), (8000, "b")]  # last line at 8s of a 118s song
        assert should_blank_incomplete_tail(20000, lines, duration_ms=118000) is True

    def test_keeps_showing_within_grace_after_last_line(self):
        lines = [(2000, "a"), (8000, "b")]
        assert should_blank_incomplete_tail(10000, lines, duration_ms=118000) is False

    def test_does_not_blank_when_last_line_near_song_end(self):
        lines = [(2000, "a"), (114000, "b")]  # loop covers nearly the whole song
        assert should_blank_incomplete_tail(117000, lines, duration_ms=118000) is False

    def test_no_blank_without_known_duration(self):
        lines = [(2000, "a"), (8000, "b")]
        assert should_blank_incomplete_tail(50000, lines, duration_ms=0) is False

    def test_no_blank_when_no_lyrics(self):
        assert should_blank_incomplete_tail(50000, [], duration_ms=118000) is False


def test_single_timestamp_unchanged():
    from src.lrc_parser import parse_lrc
    assert parse_lrc("[00:05.00]hello") == [(5000, "hello")]


def test_multi_timestamp_line_expands_and_sorts():
    from src.lrc_parser import parse_lrc
    assert parse_lrc("[00:20.00][00:05.00]chorus") == [(5000, "chorus"), (20000, "chorus")]
