"""Line-level coverage accounting.

Every non-blank source line contributes one or more normalized text units.
Accepted headings contribute their final display title; body/front-matter lines
contribute their normalized text; noise / duplicates / TOC pages are accounted
for in a separate dropped bucket.  The multiset must balance exactly.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from txt2epub_cli.hierarchy import flatten
from txt2epub_cli.model import (
    Book,
    Coverage,
    Disposition,
    Heading,
    Node,
    SourceLine,
)
from txt2epub_cli.normalize import normalize_for_match

_DROPPED = {Disposition.NOISE, Disposition.DUPLICATE, Disposition.TOC_PAGE}


def assign_units(
    roots: list[Node],
    ledger: list[SourceLine],
    headings: list[Heading],
) -> None:
    present = {node.id for node in flatten(roots)}
    by_line: dict[int, list[Heading]] = defaultdict(list)
    for heading in headings:
        if heading.id in present:
            by_line[heading.line_no].append(heading)

    for line in ledger:
        if line.disposition is Disposition.BLANK:
            line.units = []
        elif line.disposition is Disposition.HEADING:
            present_headings = by_line.get(line.line_no, [])
            if present_headings:
                line.units = [normalize_for_match(h.title) for h in present_headings]
            else:
                # A heading line whose node was removed must be accounted for as
                # dropped text, never silently forgotten.
                line.disposition = Disposition.DUPLICATE
                line.reason = line.reason or "heading_removed"
                line.units = [line.normalized]
        elif line.disposition in _DROPPED:
            line.units = [line.normalized]
        else:
            line.units = [line.normalized]


def compute_coverage(
    book: Book,
    roots: list[Node],
    ledger: list[SourceLine],
    headings: list[Heading],
) -> Coverage:
    assign_units(roots, ledger, headings)

    source_units: list[str] = []
    for line in ledger:
        source_units.extend(unit for unit in line.units if unit)

    output_units: list[str] = []
    for line in book.front_matter:
        unit = normalize_for_match(line.text)
        if unit:
            output_units.append(unit)

    for node in flatten(roots):
        title = normalize_for_match(node.heading.title)
        if title:
            output_units.append(title)
        for line in node.body:
            unit = normalize_for_match(line.text)
            if unit:
                output_units.append(unit)

    dropped_units: list[str] = []
    for line in ledger:
        if line.disposition in _DROPPED:
            dropped_units.extend(unit for unit in line.units if unit)

    source_counter = Counter(source_units)
    accounted = Counter(output_units) + Counter(dropped_units)
    missing = list((source_counter - accounted).elements())[:20]
    extra = list((accounted - source_counter).elements())[:20]

    source_chars = sum(len(unit) for unit in source_units)
    output_chars = sum(len(unit) for unit in output_units)
    dropped_chars = sum(len(unit) for unit in dropped_units)
    loss_ratio = 0.0
    if source_chars:
        loss_ratio = (source_chars - output_chars - dropped_chars) / source_chars

    return Coverage(
        source_chars=source_chars,
        output_chars=output_chars,
        dropped_chars=dropped_chars,
        source_units=len(source_units),
        output_units=len(output_units),
        dropped_units=len(dropped_units),
        loss_ratio=loss_ratio,
        ok=source_counter == accounted,
        missing=missing,
        extra=extra,
    )
