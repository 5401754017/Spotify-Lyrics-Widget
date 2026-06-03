from PyQt6.QtGui import QFont, QFontMetrics


def _font():
    return QFont("Arial", 16, QFont.Weight.Bold)


def test_short_lyric_text_is_unchanged(qtbot):
    from src.lyric_clamp import clamp_lyric_text

    text = "You look away from me"

    assert clamp_lyric_text(text, _font(), 360) == text


def test_long_lyric_text_clamps_to_two_visual_lines(qtbot):
    from src.lyric_clamp import clamp_lyric_text

    text = (
        "You look away from me, and I see there's something you're trying "
        "to hide, and I reach for your hand but it's cold"
    )
    width = 260
    clamped = clamp_lyric_text(text, _font(), width)
    metrics = QFontMetrics(_font())
    lines = clamped.splitlines()

    assert len(lines) == 2
    assert lines[1].endswith("...")
    assert all(metrics.horizontalAdvance(line) <= width for line in lines)


def test_long_unspaced_lyric_text_clamps_without_wrapping_again(qtbot):
    from src.lyric_clamp import clamp_lyric_text

    text = "你看著我我知道你有些事情想藏起來但這一整串沒有空白仍然不能跑出第三行"
    width = 220
    clamped = clamp_lyric_text(text, _font(), width)
    metrics = QFontMetrics(_font())
    lines = clamped.splitlines()

    assert len(lines) == 2
    assert lines[1].endswith("...")
    assert all(metrics.horizontalAdvance(line) <= width for line in lines)
