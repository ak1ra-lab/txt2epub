"""Duplicate-number detection, safe merging, and optional chapter dedupe."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from difflib import SequenceMatcher

from txt2epub_cli.model import Disposition, HeadingKind, Issue, Node, SourceLine

_CHINESE_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "壹": 1,
    "贰": 2,
    "叁": 3,
    "肆": 4,
    "伍": 5,
    "陆": 6,
    "柒": 7,
    "捌": 8,
    "玖": 9,
}
_CHINESE_UNITS = {
    "十": 10,
    "拾": 10,
    "廿": 20,
    "卅": 30,
    "百": 100,
    "佰": 100,
    "千": 1000,
    "仟": 1000,
    "万": 10000,
}
_ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def _roman_to_int(text: str) -> int | None:
    text = text.upper()
    if not text or any(ch not in _ROMAN for ch in text):
        return None
    total = 0
    prev = 0
    for ch in reversed(text):
        value = _ROMAN[ch]
        if value < prev:
            total -= value
        else:
            total += value
            prev = value
    return total


def _chinese_to_int(text: str) -> int | None:
    if not text:
        return None
    if all(ch in _CHINESE_DIGITS for ch in text):
        digits = [_CHINESE_DIGITS[ch] for ch in text]
        # "一三" is not a normal numeral; treat repeated digit sequences as
        # concatenated only for zero-padded-ish forms.
        if len(digits) == 1:
            return digits[0]
        return int("".join(str(d) for d in digits))

    total = 0
    section = 0
    number = 0
    for ch in text:
        if ch in _CHINESE_DIGITS:
            number = _CHINESE_DIGITS[ch]
        elif ch in _CHINESE_UNITS:
            unit = _CHINESE_UNITS[ch]
            if unit == 10000:
                section = (section + number) * unit
                total += section
                section = 0
            else:
                if number == 0:
                    number = 1
                section += number * unit
            number = 0
        else:
            return None
    return total + section + number


def parse_number(raw: str | None) -> int | None:
    """Parse the first number in a raw chapter number string."""

    if not raw:
        return None
    text = raw.strip().translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    # Multi-number / span forms: use the first component.
    text = re.split(r"[、,，\-—~～至到\s]", text, maxsplit=1)[0]
    if not text:
        return None
    if text.isdigit():
        return int(text)
    chinese = _chinese_to_int(text)
    if chinese is not None:
        return chinese
    return _roman_to_int(text)


def parse_last_number(raw: str | None) -> int | None:
    if not raw:
        return None
    parts = re.split(r"[、,，\-—~～至到\s]+", raw.strip())
    for part in reversed(parts):
        value = parse_number(part)
        if value is not None:
            return value
    return None


def number_style(raw: str | None) -> str:
    if not raw:
        return "none"
    text = raw.strip()
    if re.fullmatch(r"[0-9]+", text):
        return "arabic"
    if re.fullmatch(r"[０-９]+", text):
        return "fullwidth"
    if re.fullmatch(
        r"[零〇一二三四五六七八九十百千万两壹贰叁肆伍陆柒捌玖拾佰仟廿卅]+", text
    ):
        return "chinese"
    if re.fullmatch(r"[IVXLCDMivxlcdm]+", text):
        return "roman"
    return "mixed"


def _container_id(node: Node) -> str:
    current = node.parent
    while current is not None:
        if current.heading.kind in (HeadingKind.VOLUME, HeadingKind.SPECIAL):
            return current.id
        current = current.parent
    return ""


def _detach(node: Node) -> None:
    if node.parent is not None and node in node.parent.children:
        node.parent.children.remove(node)
        node.parent = None


def _remove_node(node: Node, roots: list[Node]) -> None:
    if node.parent is not None:
        _detach(node)
    elif node in roots:
        roots.remove(node)


def _body_hash(node: Node) -> str:
    digest = hashlib.sha256()
    for line in node.body:
        digest.update(line.normalized.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def dedupe_numbers(
    roots: list[Node],
    ledger: list[SourceLine],
    issues: list[Issue],
    multi_heading_lines: set[int] | frozenset[int] = frozenset(),
) -> dict[str, int]:
    """Detect same-number headings per container and merge safe duplicates."""

    by_line = {line.line_no: line for line in ledger}
    registry: dict[tuple[str, str], Node] = {}
    counts = {"duplicates": 0, "conflicts": 0}

    def walk(nodes: list[Node]) -> None:
        for node in list(nodes):
            if node.heading.kind == HeadingKind.CHAPTER and node.heading.number:
                key = (_container_id(node), node.heading.number.strip())
                first = registry.get(key)
                if first is None:
                    registry[key] = node
                elif node.heading.line_no in multi_heading_lines:
                    # A combined volume+chapter line also carries a volume node.
                    # Removing only the chapter would break line-level coverage,
                    # so keep it and report the conflict instead.
                    counts["conflicts"] += 1
                    issues.append(
                        Issue(
                            severity="warning",
                            code="number_conflict",
                            line_no=node.heading.line_no,
                            message=(
                                f"duplicate chapter number {node.heading.number!r} on a "
                                "combined heading; kept for coverage safety"
                            ),
                            detail={"title": node.heading.title},
                        )
                    )
                elif first.heading.title == node.heading.title:
                    counts["duplicates"] += 1
                    line = by_line.get(node.heading.line_no)
                    if line is not None:
                        line.disposition = Disposition.DUPLICATE
                        line.reason = "duplicate_number_same_title"
                    if not node.children:
                        for body_line in node.body:
                            body_line.owner_id = first.id
                            first.body.append(body_line)
                        node.body.clear()
                        _remove_node(node, roots)
                        issues.append(
                            Issue(
                                severity="warning",
                                code="duplicate_number",
                                line_no=node.heading.line_no,
                                message=(
                                    f"duplicate chapter number {node.heading.number!r}; "
                                    "body merged into the first occurrence"
                                ),
                                detail={"title": node.heading.title},
                            )
                        )
                    else:
                        issues.append(
                            Issue(
                                severity="warning",
                                code="duplicate_number_with_children",
                                line_no=node.heading.line_no,
                                message="duplicate chapter kept because it has child sections",
                            )
                        )
                else:
                    counts["conflicts"] += 1
                    issues.append(
                        Issue(
                            severity="warning",
                            code="number_conflict",
                            line_no=node.heading.line_no,
                            message=(
                                f"chapter number {node.heading.number!r} reused with a "
                                f"different title: {node.heading.title!r}"
                            ),
                            detail={"first_title": first.heading.title},
                        )
                    )
                    # Keep both; future chapters with this number still compare
                    # against the first occurrence.
            walk(node.children)

    walk(roots)
    return counts


def check_number_sequence(roots: list[Node], issues: list[Issue]) -> dict[str, int]:
    counts = {"gaps": 0, "resets": 0}
    containers: dict[str, list[Node]] = defaultdict(list)

    def walk(node: Node) -> None:
        if node.heading.kind == HeadingKind.CHAPTER:
            containers[_container_id(node)].append(node)
        for child in node.children:
            walk(child)

    for root in roots:
        walk(root)

    for chapters in containers.values():
        previous_last: int | None = None
        previous_title = ""
        for node in chapters:
            current = parse_number(node.heading.number)
            if current is None:
                continue
            last = parse_last_number(node.heading.number) or current
            if previous_last is not None:
                if current == 1:
                    counts["resets"] += 1
                    issues.append(
                        Issue(
                            severity="info",
                            code="number_reset",
                            line_no=node.heading.line_no,
                            message="chapter numbering reset to 1 inside one container",
                        )
                    )
                elif current > previous_last + 1:
                    counts["gaps"] += 1
                    issues.append(
                        Issue(
                            severity="warning",
                            code="number_gap",
                            line_no=node.heading.line_no,
                            message=(
                                f"chapter number jumps from {previous_last} to {current} "
                                f"after {previous_title!r}"
                            ),
                        )
                    )
            previous_last = last
            previous_title = node.heading.title
    return counts


def _similarity(a: Node, b: Node) -> float:
    left = "\n".join(line.normalized for line in a.body)
    right = "\n".join(line.normalized for line in b.body)
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right, autojunk=False).ratio()


def dedupe_chapters(
    roots: list[Node],
    ledger: list[SourceLine],
    issues: list[Issue],
    mode: str = "off",
    skip_lines: set[int] | frozenset[int] = frozenset(),
) -> int:
    """Optional content-level dedupe. Default off; exact is lossless by hash."""

    if mode == "off":
        return 0

    by_line = {line.line_no: line for line in ledger}
    seen: dict[tuple[str, str], Node] = {}
    removed = 0

    def mark_dropped(node: Node) -> None:
        line = by_line.get(node.heading.line_no)
        if line is not None:
            line.disposition = Disposition.DUPLICATE
            line.reason = f"dedupe_{mode}"
        for body_line in node.body:
            body_line.disposition = Disposition.DUPLICATE
            body_line.reason = f"dedupe_{mode}"

    def walk(nodes: list[Node]) -> None:
        nonlocal removed
        for node in list(nodes):
            if node.heading.line_no in skip_lines:
                walk(node.children)
                continue
            if (
                node.heading.kind == HeadingKind.CHAPTER
                and node.body
                and not node.children
            ):
                duplicate = False
                if mode == "similar":
                    for (title, _), first in seen.items():
                        if title != node.heading.title:
                            continue
                        if _similarity(first, node) >= 0.9:
                            duplicate = True
                            break
                else:
                    key = (node.heading.title, _body_hash(node))
                    duplicate = key in seen
                if duplicate:
                    mark_dropped(node)
                    _remove_node(node, roots)
                    removed += 1
                    issues.append(
                        Issue(
                            severity="info",
                            code=f"dedupe_{mode}",
                            line_no=node.heading.line_no,
                            message=f"{mode} duplicate chapter removed from output",
                        )
                    )
                else:
                    seen[(node.heading.title, _body_hash(node))] = node
            walk(node.children)

    walk(roots)
    return removed
