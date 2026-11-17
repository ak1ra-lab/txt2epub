"""Deterministic heading-candidate detection.

A candidate is *not* a heading yet: it is a single-line observation that the
parser can accept, defer (indented lines) or reject.  Keeping detection and
acceptance apart makes inspect reports honest and testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .model import HeadingKind, Issue, SourceLine
from .normalize import normalize_for_match, strip_heading_decoration
from .rules import NUM, RuleSet

_VOLUME_SEPARATORS = " \t\u3000:：、,，.-—"
_SPECIAL_PREFIX_SEPARATORS = " \u3000:：,，"
_FOREIGN_SENTENCE_PUNCTUATION = "。！？；，、：“”‘’…"


@dataclass(slots=True)
class Candidate:
    raw: str
    normalized: str
    line_no: int
    kind: HeadingKind
    family: str
    number: str | None
    title: str
    separator: str
    indent: str
    confidence: float
    issues: list[Issue] = field(default_factory=list)
    deferred: bool = False
    detail: dict = field(default_factory=dict)


def _group(match: re.Match[str], name: str) -> str:
    value = match.groupdict().get(name)
    return value or ""


def _title_of(match: re.Match[str]) -> str:
    return _group(match, "title").strip()


def _unit_after(text: str, index: int) -> str:
    if 0 <= index < len(text):
        return text[index]
    return ""


def _between_unit_and_title(text: str, unit_index: int, title: str) -> str:
    remainder = text[unit_index + 1 :]
    if title and remainder.endswith(title):
        between = remainder[: len(remainder) - len(title)]
    else:
        between = remainder[:3]
    return between[:3]


def _apply_length_limit(candidate: Candidate, text: str, rules: RuleSet) -> Candidate:
    if len(text) > rules.max_heading_length:
        candidate.confidence = 0.2
        candidate.issues.append(
            Issue(
                severity="warning",
                code="too_long",
                line_no=candidate.line_no,
                message=(
                    f"heading candidate is too long ({len(text)} > {rules.max_heading_length})"
                ),
                detail={"length": len(text), "limit": rules.max_heading_length},
            )
        )
    return candidate


def _build(
    line: SourceLine,
    text: str,
    *,
    kind: HeadingKind,
    family: str,
    number: str | None,
    title: str,
    separator: str,
    confidence: float,
    detail: dict | None = None,
) -> Candidate:
    candidate = Candidate(
        raw=line.raw,
        normalized=normalize_for_match(text),
        line_no=line.line_no,
        kind=kind,
        family=family,
        number=number,
        title=title,
        separator=separator,
        indent=line.indent,
        confidence=confidence,
        deferred=bool(line.indent),
        detail=detail or {},
    )
    if line.indent:
        candidate.detail["indented"] = True
    return candidate


def _volume_components(volume_text: str, rules: RuleSet) -> tuple[str, str, str, str]:
    """Return (number, title, unit, separator) for a volume prefix."""
    for pattern in rules.volume_patterns:
        match = pattern.match(volume_text)
        if not match:
            continue
        number = _group(match, "num")
        number_end = match.end("num")
        unit_index = (
            match.start("num") - 1 if volume_text.startswith("卷") else number_end
        )
        unit = _unit_after(volume_text, unit_index)
        title = _title_of(match)
        separator = _between_unit_and_title(volume_text, number_end, title)
        return number, title, unit, separator

    match = re.match(rf"^(?:第)?(?P<num>[{NUM}]+)[卷部篇册](?P<rest>.*)$", volume_text)
    if match:
        number = match.group("num")
        unit = _unit_after(volume_text, match.end("num"))
        rest = match.group("rest").lstrip(_VOLUME_SEPARATORS)
        return number, rest, unit, ""
    return "", "", "", ""


def _chapter_components(
    chapter_text: str, rules: RuleSet
) -> tuple[str, str | None, str, str, str]:
    """Return (number, number2, title, unit, separator) for chapter text."""
    span_patterns = [
        pattern for pattern in rules.chapter_patterns if "num2" in pattern.groupindex
    ]
    for pattern in span_patterns:
        match = pattern.match(chapter_text)
        if not match:
            continue
        number = _group(match, "num")
        number2 = _group(match, "num2")
        title = _title_of(match)
        unit_index = match.end("num2")
        unit = _unit_after(chapter_text, unit_index)
        separator = _between_unit_and_title(chapter_text, unit_index, title)
        return number, number2, title, unit, separator

    for pattern in rules.chapter_patterns:
        if "num2" in pattern.groupindex:
            continue
        match = pattern.match(chapter_text)
        if not match:
            continue
        number = _group(match, "num")
        title = _title_of(match)
        unit_index = match.end("num")
        unit = _unit_after(chapter_text, unit_index)
        separator = _between_unit_and_title(chapter_text, unit_index, title)
        return number, None, title, unit, separator

    fallback = re.match(
        rf"^第(?P<num>[{NUM}]+)[章节回集幕](?:[\s\u3000:：]*(?P<title>.*))?$",
        chapter_text,
    )
    if fallback:
        number = _group(fallback, "num")
        title = _title_of(fallback)
        unit_index = fallback.end("num")
        unit = _unit_after(chapter_text, unit_index)
        separator = _between_unit_and_title(chapter_text, unit_index, title)
        return number, None, title, unit, separator

    return "", None, chapter_text, "", ""


def _record_decorated(candidate: Candidate, decorated: bool) -> Candidate:
    if decorated:
        candidate.detail["decorated"] = True
    return candidate


def _is_volume_false_positive(text: str, match: re.Match[str], rules: RuleSet) -> bool:
    number_end = match.end("num")
    unit = _unit_after(text, number_end)
    if unit not in {"部", "篇", "册"}:
        return False
    rest = text[number_end + 1 :]
    return bool(rest) and rest[0] in rules.invalid_volume_suffixes


def _is_chapter_false_positive(text: str, match: re.Match[str], rules: RuleSet) -> bool:
    number_end = match.end("num")
    unit = _unit_after(text, number_end)
    if unit != "回":
        return False
    after_number = text[number_end:]
    after_unit = text[number_end + 1 :]
    return any(
        after_number.startswith(suffix) or after_unit.startswith(suffix)
        for suffix in rules.invalid_chapter_suffixes
    )


def _detect_combined(line: SourceLine, text: str, rules: RuleSet) -> Candidate | None:
    for pattern in rules.combined_patterns:
        match = pattern.match(text)
        if not match:
            continue
        volume_raw = _group(match, "volume").strip()
        volume_number, volume_title, volume_unit, _ = _volume_components(
            volume_raw, rules
        )
        if not volume_number:
            volume_number = _group(match, "vnum")
        chapter_raw = _group(match, "chapter").strip()
        _, _, chapter_title, chapter_unit, separator = _chapter_components(
            chapter_raw, rules
        )
        number = _group(match, "cnum")
        return _build(
            line,
            text,
            kind=HeadingKind.CHAPTER,
            family="combined_prefix",
            number=number,
            title=chapter_title,
            separator=separator,
            confidence=0.98,
            detail={
                "combined": True,
                "volume_raw": volume_raw,
                "volume_number": volume_number,
                "volume_title": volume_title,
                "volume_unit": volume_unit,
                "chapter_unit": chapter_unit,
            },
        )
    return None


def _detect_chapter_span(
    line: SourceLine, text: str, rules: RuleSet
) -> Candidate | None:
    for pattern in rules.chapter_patterns:
        if "num2" not in pattern.groupindex:
            continue
        match = pattern.match(text)
        if not match:
            continue
        number = _group(match, "num")
        number2 = _group(match, "num2")
        title = _title_of(match)
        unit_index = match.end("num2")
        separator = _between_unit_and_title(text, unit_index, title)
        return _build(
            line,
            text,
            kind=HeadingKind.CHAPTER,
            family="chapter_span",
            number=number,
            title=title,
            separator=separator,
            confidence=0.95,
            detail={"number2": number2},
        )
    return None


def _detect_volume(line: SourceLine, text: str, rules: RuleSet) -> Candidate | None:
    for pattern in rules.volume_patterns:
        match = pattern.match(text)
        if not match:
            continue
        if _is_volume_false_positive(text, match, rules):
            return None
        number = _group(match, "num")
        number_end = match.end("num")
        family = "volume_juan" if text.startswith("卷") else "volume_di"
        unit_index = match.start("num") - 1 if family == "volume_juan" else number_end
        unit = _unit_after(text, unit_index)
        title = _title_of(match)
        separator = _between_unit_and_title(text, number_end, title)
        return _build(
            line,
            text,
            kind=HeadingKind.VOLUME,
            family=family,
            number=number,
            title=title,
            separator=separator,
            confidence=0.95 if family == "volume_di" else 0.9,
            detail={"unit": unit},
        )
    return None


def _detect_chapter(line: SourceLine, text: str, rules: RuleSet) -> Candidate | None:
    for pattern in rules.chapter_patterns:
        if "num2" in pattern.groupindex:
            continue
        match = pattern.match(text)
        if not match:
            continue
        number_end = match.end("num")
        unit = _unit_after(text, number_end)
        if unit == "节":
            # Section patterns own this unit; leave it for the next detector.
            continue
        if _is_chapter_false_positive(text, match, rules):
            return None
        number = _group(match, "num")
        title = _title_of(match)
        separator = _between_unit_and_title(text, number_end, title)
        if number.isdigit() and number.startswith("0") and len(number) > 1:
            family = "chapter_zero_padded"
        elif title and not separator:
            family = "chapter_no_sep"
        else:
            family = "chapter_di"
        confidence = 0.85 if family == "chapter_no_sep" else 0.95
        return _build(
            line,
            text,
            kind=HeadingKind.CHAPTER,
            family=family,
            number=number,
            title=title,
            separator=separator,
            confidence=confidence,
            detail={"unit": unit},
        )
    return None


def _detect_section(line: SourceLine, text: str, rules: RuleSet) -> Candidate | None:
    for pattern in rules.section_patterns:
        match = pattern.match(text)
        if not match:
            continue
        number = _group(match, "num")
        title = _title_of(match)
        unit_index = match.end("num")
        unit = _unit_after(text, unit_index)
        separator = _between_unit_and_title(text, unit_index, title)
        return _build(
            line,
            text,
            kind=HeadingKind.SECTION,
            family="section_di",
            number=number,
            title=title,
            separator=separator,
            confidence=0.9,
            detail={"unit": unit},
        )
    return None


def _special_candidate_from_match(
    line: SourceLine,
    text: str,
    match: re.Match[str],
    separator: str = "",
    *,
    custom: bool,
) -> Candidate:
    title = _group(match, "title").strip()
    if not title:
        title = _group(match, "special").strip()
    if not title:
        title = text
    detail = {"custom": True} if custom else {}
    return _build(
        line,
        text,
        kind=HeadingKind.SPECIAL,
        family="special",
        number=None,
        title=title,
        separator=separator,
        confidence=0.9 if custom else 0.95,
        detail=detail,
    )


def _detect_special(line: SourceLine, text: str, rules: RuleSet) -> Candidate | None:
    if text in rules.special_titles:
        return _build(
            line,
            text,
            kind=HeadingKind.SPECIAL,
            family="special",
            number=None,
            title=text,
            separator="",
            confidence=0.95,
            detail={"exact": True},
        )

    for special in sorted(rules.special_titles, key=len, reverse=True):
        if not text.startswith(special):
            continue
        next_char = text[len(special) : len(special) + 1]
        if not next_char or next_char not in _SPECIAL_PREFIX_SEPARATORS:
            continue
        remainder = text[len(special) + 1 :].strip()
        return _build(
            line,
            text,
            kind=HeadingKind.SPECIAL,
            family="special",
            number=None,
            title=remainder or special,
            separator="",
            confidence=0.9,
            detail={"prefix": special},
        )

    if text.endswith("完本感言") and len(text) <= 30:
        return _build(
            line,
            text,
            kind=HeadingKind.SPECIAL,
            family="special",
            number=None,
            title=text,
            separator="",
            confidence=0.9,
            detail={"suffix": "完本感言"},
        )

    if (
        "外传" in text
        and len(text) <= 30
        and not any(char in text for char in _FOREIGN_SENTENCE_PUNCTUATION)
        and (text.startswith("外传") or text.endswith("外传") or "外传·" in text)
    ):
        return _build(
            line,
            text,
            kind=HeadingKind.SPECIAL,
            family="special",
            number=None,
            title=text,
            separator="",
            confidence=0.85,
            detail={"contains": "外传"},
        )

    for pattern in rules.special_patterns:
        match = pattern.match(text)
        if match:
            return _special_candidate_from_match(line, text, match, custom=True)
    return None


def _detect_pure_number(
    line: SourceLine, text: str, rules: RuleSet
) -> Candidate | None:
    if not rules.pure_number_headings:
        return None
    for pattern in rules.pure_number_patterns:
        match = pattern.match(text)
        if not match:
            continue
        number = _group(match, "num")
        title = _title_of(match)
        unit_index = match.end("num")
        separator = _between_unit_and_title(text, unit_index, title)
        return _build(
            line,
            text,
            kind=HeadingKind.CHAPTER,
            family="pure_number",
            number=number,
            title=title,
            separator=separator,
            confidence=0.7,
        )
    return None


def detect_candidate(line: SourceLine, rules: RuleSet) -> Candidate | None:
    """Detect one heading candidate on a single source line."""
    if not line.stripped.strip():
        return None

    text = strip_heading_decoration(line.stripped).strip()
    if not text:
        return None
    decorated = text != line.stripped

    candidate = (
        _detect_combined(line, text, rules)
        or _detect_chapter_span(line, text, rules)
        or _detect_volume(line, text, rules)
        or _detect_chapter(line, text, rules)
        or _detect_section(line, text, rules)
        or _detect_special(line, text, rules)
        or _detect_pure_number(line, text, rules)
    )
    if candidate is None:
        return None

    _record_decorated(candidate, decorated)
    return _apply_length_limit(candidate, text, rules)


def detect_candidates(lines: list[SourceLine], rules: RuleSet) -> list[Candidate]:
    """Return all candidates, preserving source line order."""
    candidates: list[Candidate] = []
    for line in lines:
        candidate = detect_candidate(line, rules)
        if candidate is not None:
            candidates.append(candidate)
    return candidates
