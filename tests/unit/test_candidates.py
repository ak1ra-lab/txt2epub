"""Tests for deterministic heading-candidate detection."""

from __future__ import annotations

from txt2epub_cli.candidates import Candidate, detect_candidate, detect_candidates
from txt2epub_cli.model import HeadingKind, SourceLine
from txt2epub_cli.rules import builtin_ruleset, parse_toml_rules

INDENT_CHARS = " \t\u3000"


def make_line(text: str, line_no: int = 1) -> SourceLine:
    stripped = text.strip()
    indent = text[: len(text) - len(text.lstrip(INDENT_CHARS))]
    return SourceLine(
        line_no=line_no,
        raw=text,
        text=text,
        stripped=stripped,
        indent=indent,
        normalized=stripped,
    )


def detect(text: str, rules=None, line_no: int = 1) -> Candidate | None:
    return detect_candidate(make_line(text, line_no), rules or builtin_ruleset())


def test_volume_di() -> None:
    candidate = detect("第一卷 平庸少年")
    assert candidate is not None
    assert candidate.kind is HeadingKind.VOLUME
    assert candidate.family == "volume_di"
    assert candidate.number == "一"
    assert candidate.title == "平庸少年"
    assert candidate.separator == " "
    assert candidate.detail["unit"] == "卷"
    assert candidate.deferred is False


def test_volume_juan() -> None:
    candidate = detect("卷一 少年游")
    assert candidate is not None
    assert candidate.kind is HeadingKind.VOLUME
    assert candidate.family == "volume_juan"
    assert candidate.number == "一"
    assert candidate.title == "少年游"
    assert candidate.detail["unit"] == "卷"


def test_chapter_arabic() -> None:
    candidate = detect("第1章 陨落的天才")
    assert candidate is not None
    assert candidate.kind is HeadingKind.CHAPTER
    assert candidate.family == "chapter_di"
    assert candidate.number == "1"
    assert candidate.title == "陨落的天才"
    assert candidate.separator == " "


def test_chapter_chinese() -> None:
    candidate = detect("第一章 离乡")
    assert candidate is not None
    assert candidate.family == "chapter_di"
    assert candidate.number == "一"
    assert candidate.title == "离乡"


def test_chapter_zero_padded() -> None:
    candidate = detect("第0001章 沈家")
    assert candidate is not None
    assert candidate.family == "chapter_zero_padded"
    assert candidate.number == "0001"
    assert candidate.title == "沈家"


def test_chapter_no_separator() -> None:
    candidate = detect("第一章活着")
    assert candidate is not None
    assert candidate.family == "chapter_no_sep"
    assert candidate.number == "一"
    assert candidate.title == "活着"
    assert candidate.separator == ""
    assert candidate.confidence == 0.85

    candidate = detect("第1746章三魂归位！")
    assert candidate is not None
    assert candidate.family == "chapter_no_sep"
    assert candidate.title == "三魂归位！"


def test_chapter_multi_number() -> None:
    candidate = detect("第104、105章 踏月而战！")
    assert candidate is not None
    assert candidate.kind is HeadingKind.CHAPTER
    assert candidate.family == "chapter_di"
    assert candidate.number == "104、105"
    assert candidate.title == "踏月而战！"


def test_chapter_span() -> None:
    candidate = detect("第1037章—第1038章 合章")
    assert candidate is not None
    assert candidate.kind is HeadingKind.CHAPTER
    assert candidate.family == "chapter_span"
    assert candidate.number == "1037"
    assert candidate.title == "合章"
    assert candidate.detail["number2"] == "1038"
    assert candidate.separator == " "


def test_section() -> None:
    candidate = detect("第一节 初见")
    assert candidate is not None
    assert candidate.kind is HeadingKind.SECTION
    assert candidate.family == "section_di"
    assert candidate.number == "一"
    assert candidate.title == "初见"


def test_combined_prefix_with_volume_title() -> None:
    candidate = detect("第一卷 占位卷名 第1章 占位章名")
    assert candidate is not None
    assert candidate.kind is HeadingKind.CHAPTER
    assert candidate.family == "combined_prefix"
    assert candidate.number == "1"
    assert candidate.title == "占位章名"
    assert candidate.detail["combined"] is True
    assert candidate.detail["volume_raw"] == "第一卷 占位卷名"
    assert candidate.detail["volume_number"] == "一"
    assert candidate.detail["volume_title"] == "占位卷名"


def test_combined_prefix_without_volume_title() -> None:
    candidate = detect("第一卷 第1章 占位章名")
    assert candidate is not None
    assert candidate.family == "combined_prefix"
    assert candidate.title == "占位章名"
    assert candidate.detail["volume_title"] == ""
    assert candidate.detail["volume_number"] == "一"


def test_combined_prefix_multi_number() -> None:
    candidate = detect("第一卷 占位卷名 第104、105章 标题")
    assert candidate is not None
    assert candidate.family == "combined_prefix"
    assert candidate.number == "104、105"
    assert candidate.title == "标题"


def test_combined_prefix_juan() -> None:
    candidate = detect("卷一 少年游 第2章 标题")
    assert candidate is not None
    assert candidate.family == "combined_prefix"
    assert candidate.number == "2"
    assert candidate.title == "标题"
    assert candidate.detail["volume_number"] == "一"
    assert candidate.detail["volume_title"] == "少年游"


def test_special_exact() -> None:
    for text in ("序章", "序言", "楔子", "完本感言", "作者的话"):
        candidate = detect(text)
        assert candidate is not None, text
        assert candidate.kind is HeadingKind.SPECIAL
        assert candidate.family == "special"
        assert candidate.number is None
        assert candidate.title == text


def test_special_prefix() -> None:
    candidate = detect("番外 冰灵族（一）")
    assert candidate is not None
    assert candidate.kind is HeadingKind.SPECIAL
    assert candidate.title == "冰灵族（一）"

    candidate = detect("后记，说明。")
    assert candidate is not None
    assert candidate.title == "说明。"

    candidate = detect("终章 占位标题")
    assert candidate is not None
    assert candidate.title == "占位标题"


def test_special_suffix_and_contains() -> None:
    candidate = detect("仙界篇完本感言")
    assert candidate is not None
    assert candidate.kind is HeadingKind.SPECIAL
    assert candidate.title == "仙界篇完本感言"

    candidate = detect("凡人外传·仙界篇 一")
    assert candidate is not None
    assert candidate.kind is HeadingKind.SPECIAL
    assert candidate.title == "凡人外传·仙界篇 一"

    candidate = detect("凡人外传")
    assert candidate is not None
    assert candidate.kind is HeadingKind.SPECIAL
    assert candidate.title == "凡人外传"


def test_special_rejects_ordinary_sentences() -> None:
    assert detect("就在这时，阁楼外传进韩宗的声音。") is None
    assert detect("序列十三") is None


def test_special_custom_pattern() -> None:
    rules = parse_toml_rules("[patterns]\nspecial = '^(?P<special>卷首序)$'\n")
    candidate = detect("卷首序", rules)
    assert candidate is not None
    assert candidate.kind is HeadingKind.SPECIAL
    assert candidate.family == "special"
    assert candidate.title == "卷首序"
    assert candidate.detail["custom"] is True


def test_decorated_equals_heading() -> None:
    candidate = detect("=== 第一章 标题 ===")
    assert candidate is not None
    assert candidate.kind is HeadingKind.CHAPTER
    assert candidate.number == "一"
    assert candidate.title == "标题"
    assert candidate.detail["decorated"] is True


def test_decorated_bracket_heading() -> None:
    candidate = detect("【第一章】标题")
    assert candidate is not None
    assert candidate.kind is HeadingKind.CHAPTER
    assert candidate.number == "一"
    assert "标题" in candidate.title
    assert candidate.detail["decorated"] is True


def test_false_positive_exclusions() -> None:
    assert detect("第一回合的接触让他措手不及。") is None
    assert detect("第九部落的传送阵亮了起来。") is None
    assert detect("第三部分内容") is None


def test_too_long_candidate_is_reported() -> None:
    text = "第一章 " + "长" * 60
    candidate = detect(text)
    assert candidate is not None
    assert candidate.confidence == 0.2
    issue = next(issue for issue in candidate.issues if issue.code == "too_long")
    assert issue.severity == "warning"
    assert issue.line_no == 1
    assert "50" in issue.message


def test_body_line_is_not_a_candidate() -> None:
    assert detect("他推开门，看见远处的山。") is None
    assert detect("   ") is None


def test_indented_candidate_is_deferred() -> None:
    candidate = detect("\u3000第一章 标题")
    assert candidate is not None
    assert candidate.deferred is True
    assert candidate.detail["indented"] is True
    assert candidate.indent == "\u3000"

    candidate = detect("  第一章 标题")
    assert candidate is not None
    assert candidate.deferred is True
    assert candidate.indent == "  "


def test_indented_candidate_returned_even_when_disallowed() -> None:
    candidate = detect("\u3000第一章 标题", builtin_ruleset("strict"))
    assert candidate is not None
    assert candidate.deferred is True
    assert candidate.detail["indented"] is True


def test_pure_number_only_when_enabled() -> None:
    assert detect("1. 标题") is None

    candidate = detect("1. 标题", builtin_ruleset("loose"))
    assert candidate is not None
    assert candidate.family == "pure_number"
    assert candidate.number == "1"
    assert candidate.title == "标题"

    candidate = detect("001、引言", builtin_ruleset("loose"))
    assert candidate is not None
    assert candidate.family == "pure_number"
    assert candidate.number == "001"
    assert candidate.title == "引言"


def test_strict_profile_behavior() -> None:
    rules = builtin_ruleset("strict")
    assert detect("第一章活着", rules) is None
    candidate = detect("第一章 活着", rules)
    assert candidate is not None
    assert candidate.family == "chapter_di"
    assert candidate.title == "活着"


def test_detect_candidates_preserves_order_and_skips_body() -> None:
    lines = [
        make_line("前言文字", 1),
        make_line("第一章 开始", 2),
        make_line("", 3),
        make_line("正文段落", 4),
        make_line("第一节 细节", 5),
    ]
    candidates = detect_candidates(lines, builtin_ruleset())
    assert [candidate.line_no for candidate in candidates] == [2, 5]
    assert [candidate.family for candidate in candidates] == [
        "chapter_di",
        "section_di",
    ]


def test_candidate_normalized_uses_match_text() -> None:
    candidate = detect("=== 第一章 标题 ===")
    assert candidate is not None
    assert "第一章" in candidate.normalized
    assert "===" not in candidate.normalized
