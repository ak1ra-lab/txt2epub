"""Detect embedded table-of-contents pages.

The detector is deliberately conservative: an explicit 目录/Contents marker needs
at least five short entry-like lines, and an implicit block needs at least five
consecutive heading-like lines with no narrative paragraph between them.
"""

from __future__ import annotations

from collections.abc import Callable

from txt2epub_cli.model import SourceLine
from txt2epub_cli.rules import RuleSet

HeadingLike = Callable[[SourceLine], bool]

_MAX_SCAN = 600
_MAX_ENTRY_LENGTH = 80
_MAX_BLANK_GAP = 3


def _is_toc_title(text: str, rules: RuleSet) -> bool:
    stripped = text.strip(" \t\u3000:：-—=_")
    return stripped in rules.toc_titles


def _looks_like_entry(line: SourceLine, is_heading_like: HeadingLike) -> bool:
    text = line.stripped
    if not text or len(text) > _MAX_ENTRY_LENGTH:
        return False
    if is_heading_like(line):
        return True
    # Entries with page numbers / dot leaders are useful even when the title
    # itself is not a recognized heading.
    return bool(
        any(marker in text for marker in ("……", "...", "···"))
        and any(ch.isdigit() for ch in text)
    )


def detect_toc_lines(
    lines: list[SourceLine],
    rules: RuleSet,
    is_heading_like: HeadingLike,
) -> set[int]:
    marked: set[int] = set()
    total = len(lines)

    for index, line in enumerate(lines):
        if not _is_toc_title(line.stripped, rules):
            continue
        entries: list[int] = []
        blank_gap = 0
        cursor = index + 1
        while cursor < total and cursor - index <= _MAX_SCAN:
            current = lines[cursor]
            if not current.stripped:
                if entries:
                    # A blank line after entries ends the TOC block; otherwise a
                    # real chapter following the TOC page would be swallowed.
                    break
                blank_gap += 1
                if blank_gap > _MAX_BLANK_GAP:
                    break
                cursor += 1
                continue
            blank_gap = 0
            if len(current.stripped) > _MAX_ENTRY_LENGTH * 2:
                break
            if _looks_like_entry(current, is_heading_like):
                entries.append(current.line_no)
            elif entries:
                break
            cursor += 1
        if len(entries) >= 5:
            marked.add(line.line_no)
            marked.update(entries)

    # Implicit TOC: a run of heading-like lines with no long body paragraph.
    run: list[int] = []
    for line in lines:
        if not line.stripped:
            if len(run) >= 5:
                marked.update(run)
            run = []
            continue
        if (
            _looks_like_entry(line, is_heading_like)
            and len(line.stripped) <= _MAX_ENTRY_LENGTH
        ):
            run.append(line.line_no)
            continue
        if len(run) >= 5:
            marked.update(run)
        run = []
    if len(run) >= 5:
        marked.update(run)

    return marked
