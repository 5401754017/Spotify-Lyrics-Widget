from PyQt6.QtGui import QFont, QFontMetrics, QTextLayout, QTextOption


MAX_LYRIC_VISUAL_LINES = 2
ASCII_ELLIPSIS = "..."


def clamp_lyric_text(
    text: str,
    font: QFont,
    width: int,
    max_lines: int = MAX_LYRIC_VISUAL_LINES,
) -> str:
    if not text or width <= 0:
        return text

    explicit_lines = text.splitlines()
    if len(explicit_lines) > max_lines:
        text = "\n".join(explicit_lines[:max_lines])

    visual_lines = _wrapped_visual_lines(text, font, width)
    if len(visual_lines) <= max_lines:
        return text

    if max_lines == 1:
        return _elide_ascii(text.replace("\n", " "), QFontMetrics(font), width)

    first_line = visual_lines[0]
    remaining_text = " ".join(line for line in visual_lines[1:] if line)
    second_line = _elide_ascii(remaining_text, QFontMetrics(font), width)
    return f"{first_line}\n{second_line}" if second_line else first_line


def _wrapped_visual_lines(text: str, font: QFont, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        if not paragraph:
            lines.append("")
            continue
        layout = QTextLayout(paragraph, font)
        option = QTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        layout.setTextOption(option)
        layout.beginLayout()
        try:
            while True:
                line = layout.createLine()
                if not line.isValid():
                    break
                line.setLineWidth(width)
                start = line.textStart()
                length = line.textLength()
                lines.append(paragraph[start : start + length].strip())
        finally:
            layout.endLayout()
    return lines


def _elide_ascii(text: str, metrics: QFontMetrics, width: int) -> str:
    text = text.strip()
    if metrics.horizontalAdvance(text) <= width:
        return text

    ellipsis_width = metrics.horizontalAdvance(ASCII_ELLIPSIS)
    if ellipsis_width >= width:
        return ASCII_ELLIPSIS

    result = ""
    for char in text:
        if metrics.horizontalAdvance(result + char) > width - ellipsis_width:
            break
        result += char
    return f"{result.rstrip()}{ASCII_ELLIPSIS}"
