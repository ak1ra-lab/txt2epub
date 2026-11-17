from __future__ import annotations

from pathlib import Path

from txt2epub_cli.coverage import compute_coverage
from txt2epub_cli.hierarchy import build_tree
from txt2epub_cli.model import (
    Book,
    Disposition,
    Heading,
    HeadingKind,
    SourceLine,
)


def source_line(line_no: int, text: str, disposition: Disposition) -> SourceLine:
    return SourceLine(
        line_no=line_no,
        raw=text,
        text=text,
        stripped=text.strip(),
        indent="",
        normalized=text.strip(),
        disposition=disposition,
    )


def heading(
    hid: str, title: str, line_no: int, kind: HeadingKind = HeadingKind.CHAPTER
) -> Heading:
    return Heading(
        id=hid,
        kind=kind,
        level=1,
        raw=title,
        title=title,
        number="1",
        line_no=line_no,
        confidence=1.0,
    )


def test_coverage_balances_heading_body_and_dropped():
    h = heading("c1", "第一章", 1)
    roots, _ = build_tree([h])
    body = source_line(2, "占位正文。", Disposition.BODY)
    roots[0].body.append(body)
    noise = source_line(3, "百度搜索广告", Disposition.NOISE)
    ledger = [
        source_line(1, "第一章", Disposition.HEADING),
        body,
        noise,
    ]
    book = Book(source=Path("book.txt"), title="占位")

    coverage = compute_coverage(book, roots, ledger, [h])

    assert coverage.ok
    assert coverage.source_units == coverage.output_units + coverage.dropped_units
    assert coverage.dropped_chars == len("百度搜索广告")


def test_coverage_detects_missing_output_line():
    h = heading("c1", "第一章", 1)
    roots, _ = build_tree([h])
    body = source_line(2, "占位正文。", Disposition.BODY)
    # Deliberately forget to attach the body to the tree.
    ledger = [
        source_line(1, "第一章", Disposition.HEADING),
        body,
    ]
    book = Book(source=Path("book.txt"), title="占位")

    coverage = compute_coverage(book, roots, ledger, [h])

    assert not coverage.ok
    assert coverage.missing == ["占位正文。"]


def test_front_matter_is_counted():
    book = Book(source=Path("book.txt"), title="占位")
    front = source_line(1, "书名：占位书名", Disposition.FRONT_MATTER)
    book.front_matter.append(front)
    coverage = compute_coverage(book, [], [front], [])
    assert coverage.ok
    assert coverage.output_chars == len("书名：占位书名")
