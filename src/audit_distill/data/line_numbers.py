"""Line positions follow LF/CRLF/CR source lines, with no phantom final line."""


def source_lines(code: str) -> list[str]:
    text = code.replace("\r\n", "\n").replace("\r", "\n")
    if not text:
        return []
    lines = text.split("\n")
    return lines[:-1] if text.endswith("\n") else lines


def render_line_numbers(code: str) -> str:
    return "\n".join(
        f"{number:04d} |" + (f" {line}" if line else "")
        for number, line in enumerate(source_lines(code), start=1)
    )
