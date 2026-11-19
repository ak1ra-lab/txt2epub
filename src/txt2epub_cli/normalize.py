"""Text normalization helpers shared by the parser and heading classifier."""

from __future__ import annotations

import re
import unicodedata

from .model import SourceLine

ZERO_WIDTH = "\u200b\u200c\u200d\ufeff"

_INDENT_CHARS = " \t\u3000"
# XML 1.0 forbids most C0 controls; drop them at the source rather than
# producing an unreadable XHTML file later.
_INVALID_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ufffe\uffff]")
# A decoration run needs at least two characters so that a single dash in a
# title (e.g. "第一章 - 上") survives untouched.
_DECORATION_RE = re.compile(r"^[ \t]*[-=*#~_]{2,}[ \t]*|[ \t]*[-=*#~_]{2,}[ \t]*$")
_BRACKET_PAIRS = {"【": "】", "[": "]", "「": "」"}
_MAX_BRACKET_INNER = 60


def normalize_text(s: str) -> str:
    """Apply NFC and drop zero-width / XML-invalid control characters.

    U+3000 and ordinary spacing are preserved.
    """
    normalized = unicodedata.normalize("NFC", s)
    cleaned = "".join(char for char in normalized if char not in ZERO_WIDTH)
    return _INVALID_CONTROL_RE.sub("", cleaned)


def normalize_for_match(s: str) -> str:
    """Normalize *s* and strip outer whitespace for comparisons."""
    return normalize_text(s).strip()


def indent_of(s: str) -> str:
    """Return the leading run of ideographic spaces, ASCII spaces, and tabs."""
    return s[: len(s) - len(s.lstrip(_INDENT_CHARS))]


def strip_heading_decoration(s: str) -> str:
    """Remove decoration runs and a leading wrapped bracket segment."""
    result = s
    while True:
        updated = _strip_decoration_runs(result)
        updated = _strip_leading_bracket(updated)
        if updated == result:
            return result
        result = updated


def split_lines(text: str) -> list[str]:
    """Split text on ``\\n`` without inventing a line for a trailing newline."""
    if text == "":
        return []
    lines = text.split("\n")
    if text.endswith("\n"):
        lines.pop()
    return lines


def make_source_lines(text: str) -> list[SourceLine]:
    """Turn normalized text into one :class:`SourceLine` per physical line."""
    lines: list[SourceLine] = []
    for line_no, raw in enumerate(split_lines(text), start=1):
        stripped = normalize_text(raw).strip()
        lines.append(
            SourceLine(
                line_no=line_no,
                raw=raw,
                text=raw,
                stripped=stripped,
                indent=indent_of(raw),
                normalized=normalize_text(stripped),
            )
        )
    return lines


def _strip_decoration_runs(s: str) -> str:
    result = s
    while True:
        updated = _DECORATION_RE.sub("", result).strip()
        if updated == result:
            return result
        result = updated


def _strip_leading_bracket(s: str) -> str:
    if not s:
        return s
    opener = s[0]
    closer = _BRACKET_PAIRS.get(opener)
    if closer is None:
        return s
    end = s.find(closer, 1)
    if end < 0:
        return s
    inner = s[1:end].strip()
    if not inner or len(inner) > _MAX_BRACKET_INNER:
        return s
    if opener in inner or closer in inner:
        return s
    rest = s[end + 1 :].strip()
    return f"{inner} {rest}" if rest else inner
