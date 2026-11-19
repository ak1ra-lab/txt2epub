"""Tests for text normalization and source-line construction."""

from __future__ import annotations

import pytest

from txt2epub_cli.normalize import (
    ZERO_WIDTH,
    indent_of,
    make_source_lines,
    normalize_for_match,
    normalize_text,
    split_lines,
    strip_heading_decoration,
)


def test_normalize_text_applies_nfc() -> None:
    assert normalize_text("e\u0301") == "\u00e9"


def test_normalize_text_does_not_apply_nfkc() -> None:
    assert normalize_text("\uff21") == "\uff21"


def test_normalize_text_removes_zero_width_characters() -> None:
    assert normalize_text(f"a{ZERO_WIDTH}b") == "ab"
    assert normalize_text("\ufeff第\u200b一章") == "第一章"


def test_normalize_text_preserves_ideographic_space() -> None:
    assert normalize_text("　第一章　") == "　第一章　"


def test_normalize_text_does_not_strip() -> None:
    assert normalize_text("  第一章  ") == "  第一章  "


def test_normalize_for_match_strips() -> None:
    assert normalize_for_match(" 　第一章　 ") == "第一章"


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("　　第一章", "　　"),
        ("  正文", "  "),
        ("\t正文", "\t"),
        (" \t　正文", " \t　"),
        ("正文", ""),
        ("", ""),
    ],
)
def test_indent_of(line: str, expected: str) -> None:
    assert indent_of(line) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("=== 第一章 标题 ===", "第一章 标题"),
        ("## 第一章 ##", "第一章"),
        ("~~~ 第一卷 ~~~", "第一卷"),
        ("***第一章***", "第一章"),
        ("=== 第一章 ===", "第一章"),
        ("第一章", "第一章"),
        ("第一章 - 上", "第一章 - 上"),
        ("- 第一章", "- 第一章"),
        ("=== ===", ""),
        ("", ""),
    ],
)
def test_strip_heading_decoration(value: str, expected: str) -> None:
    assert strip_heading_decoration(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("【第一章】", "第一章"),
        ("【第一章】标题", "第一章 标题"),
        ("【第一章】 标题", "第一章 标题"),
        ("【 第一章 】", "第一章"),
        ("「楔子」", "楔子"),
        ("[第一章]", "第一章"),
        ("[]", "[]"),
        ("【】", "【】"),
        ("[ ]", "[ ]"),
        ("=== 【第一章】 ===", "第一章"),
    ],
)
def test_strip_heading_decoration_brackets(value: str, expected: str) -> None:
    assert strip_heading_decoration(value) == expected


def test_strip_heading_decoration_keeps_long_bracket_content() -> None:
    value = "【" + "长" * 61 + "】"

    assert strip_heading_decoration(value) == value


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", []),
        ("\n", [""]),
        ("a", ["a"]),
        ("a\n", ["a"]),
        ("a\nb", ["a", "b"]),
        ("a\n\nb\n", ["a", "", "b"]),
        ("\n\n", ["", ""]),
    ],
)
def test_split_lines(text: str, expected: list[str]) -> None:
    assert split_lines(text) == expected


def test_make_source_lines_fields() -> None:
    lines = make_source_lines("　　第一章　标题\n\n　　正文　内容\n")

    assert [line.line_no for line in lines] == [1, 2, 3]

    first = lines[0]
    assert first.raw == "　　第一章　标题"
    assert first.text == "　　第一章　标题"
    assert first.stripped == "第一章　标题"
    assert first.indent == "　　"
    assert first.normalized == "第一章　标题"

    blank = lines[1]
    assert blank.raw == blank.text == blank.stripped == blank.normalized == ""
    assert blank.indent == ""

    third = lines[2]
    assert third.raw == "　　正文　内容"
    assert third.stripped == "正文　内容"
    assert third.indent == "　　"
    assert third.normalized == "正文　内容"


def test_make_source_lines_keeps_raw_and_removes_zero_width_in_normalized() -> None:
    lines = make_source_lines("　第\u200b一章\n")

    assert len(lines) == 1
    line = lines[0]
    assert line.raw == "　第\u200b一章"
    assert line.text == line.raw
    assert line.stripped == "第一章"
    assert line.normalized == "第一章"
    assert line.indent == "　"


def test_make_source_lines_applies_nfc() -> None:
    line = make_source_lines("e\u0301\n")[0]

    assert line.stripped == "\u00e9"
    assert line.normalized == "\u00e9"


def test_normalize_text_removes_xml_invalid_controls() -> None:
    assert normalize_text("a\x0bb\x00c\x1fd") == "abcd"
    assert normalize_text("正常\t文本") == "正常\t文本"
