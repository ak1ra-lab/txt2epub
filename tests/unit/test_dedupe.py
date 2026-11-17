from __future__ import annotations

from txt2epub_cli.dedupe import (
    check_number_sequence,
    dedupe_numbers,
    number_style,
    parse_last_number,
    parse_number,
)
from txt2epub_cli.hierarchy import build_tree
from txt2epub_cli.model import Disposition, Heading, HeadingKind, Issue, SourceLine


def heading(
    hid: str, kind: HeadingKind, title: str, line_no: int, number: str | None
) -> Heading:
    return Heading(
        id=hid,
        kind=kind,
        level=1,
        raw=title,
        title=title,
        number=number,
        line_no=line_no,
        confidence=1.0,
    )


def line(line_no: int, text: str) -> SourceLine:
    return SourceLine(
        line_no=line_no,
        raw=text,
        text=text,
        stripped=text.strip(),
        indent="",
        normalized=text.strip(),
        disposition=Disposition.HEADING,
    )


def test_parse_number_variants():
    assert parse_number("1") == 1
    assert parse_number("0001") == 1
    assert parse_number("１２") == 12
    assert parse_number("一") == 1
    assert parse_number("十二") == 12
    assert parse_number("二十三") == 23
    assert parse_number("一百零五") == 105
    assert parse_number("一千零一") == 1001
    assert parse_number("廿三") == 23
    assert parse_number("IV") == 4
    assert parse_number("104、105") == 104
    assert parse_last_number("104、105") == 105
    assert parse_number("不是数字") is None


def test_number_styles():
    assert number_style("1") == "arabic"
    assert number_style("１２") == "fullwidth"
    assert number_style("十二") == "chinese"
    assert number_style("IV") == "roman"
    assert number_style("1、2") == "mixed"
    assert number_style(None) == "none"


def test_duplicate_same_title_merges_body():
    first_body = line(2, "first body")
    second_body = line(5, "second body")
    h1 = heading("c1", HeadingKind.CHAPTER, "第一章", 1, "1")
    h2 = heading("c2", HeadingKind.CHAPTER, "第一章", 4, "1")
    roots, targets = build_tree([h1, h2])
    roots[0].body.append(first_body)
    roots[1].body.append(second_body)
    ledger = [line(1, "第一章"), first_body, line(4, "第一章"), second_body]
    issues: list[Issue] = []

    counts = dedupe_numbers(roots, ledger, issues)

    assert counts["duplicates"] == 1
    assert len(roots) == 1
    assert [item.text for item in roots[0].body] == ["first body", "second body"]
    assert ledger[2].disposition is Disposition.DUPLICATE
    assert any(issue.code == "duplicate_number" for issue in issues)


def test_same_number_different_title_is_kept_as_conflict():
    h1 = heading("c1", HeadingKind.CHAPTER, "第一章 占位甲", 1, "1")
    h2 = heading("c2", HeadingKind.CHAPTER, "第一章 占位乙", 2, "1")
    roots, _ = build_tree([h1, h2])
    ledger = [line(1, h1.title), line(2, h2.title)]
    issues: list[Issue] = []

    counts = dedupe_numbers(roots, ledger, issues)

    assert counts["conflicts"] == 1
    assert len(roots) == 2
    assert any(issue.code == "number_conflict" for issue in issues)


def test_same_number_in_different_volumes_is_not_duplicate():
    roots, _ = build_tree(
        [
            heading("v1", HeadingKind.VOLUME, "第一卷", 1, "一"),
            heading("c1", HeadingKind.CHAPTER, "第一章", 2, "1"),
            heading("v2", HeadingKind.VOLUME, "第二卷", 3, "二"),
            heading("c2", HeadingKind.CHAPTER, "第一章", 4, "1"),
        ]
    )
    ledger = [line(i, f"line {i}") for i in range(1, 5)]
    issues: list[Issue] = []
    counts = dedupe_numbers(roots, ledger, issues)
    assert counts == {"duplicates": 0, "conflicts": 0}


def test_number_gap_and_reset_reported():
    roots, _ = build_tree(
        [
            heading("c1", HeadingKind.CHAPTER, "第一章", 1, "1"),
            heading("c2", HeadingKind.CHAPTER, "第五章", 2, "5"),
            heading("c3", HeadingKind.CHAPTER, "第一章", 3, "1"),
        ]
    )
    issues: list[Issue] = []
    counts = check_number_sequence(roots, issues)
    assert counts["gaps"] == 1
    assert counts["resets"] == 1
    codes = {issue.code for issue in issues}
    assert {"number_gap", "number_reset"} <= codes


def test_sequence_handles_multi_number_ranges():
    roots, _ = build_tree(
        [
            heading("c1", HeadingKind.CHAPTER, "第104、105章", 1, "104、105"),
            heading("c2", HeadingKind.CHAPTER, "第106章", 2, "106"),
        ]
    )
    issues: list[Issue] = []
    counts = check_number_sequence(roots, issues)
    assert counts["gaps"] == 0
