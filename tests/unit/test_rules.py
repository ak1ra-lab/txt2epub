"""Tests for built-in heading rules and TOML overrides."""

from __future__ import annotations

import re

import pytest

from txt2epub_cli.rules import (
    NUM,
    RuleSet,
    builtin_ruleset,
    load_rules,
    make_ruleset,
    parse_toml_rules,
)


def _matches(patterns: list[re.Pattern[str]], text: str) -> bool:
    return any(pattern.match(text) for pattern in patterns)


def _noise(rules: RuleSet, text: str) -> bool:
    return any(pattern.search(text) for pattern in rules.noise_patterns)


def test_num_covers_expected_characters() -> None:
    number_class = re.compile(rf"[{NUM}]")
    for char in "0123456789０１２３４５６７８９零〇一二三四五六七八九十百千万两":
        assert number_class.fullmatch(char)
    for char in "壹贰叁肆伍陆柒捌玖拾佰仟廿卅IVXLCDMivxlcdm":
        assert number_class.fullmatch(char)
    assert "[" not in NUM
    assert "]" not in NUM


def test_auto_profile_defaults() -> None:
    rules = builtin_ruleset()
    assert rules.name == "auto"
    assert rules.max_heading_length == 50
    assert rules.require_column_zero is True
    assert rules.allow_indented_headings is True
    assert rules.pure_number_headings is False
    assert rules.volume_patterns
    assert rules.chapter_patterns
    assert rules.section_patterns
    assert rules.combined_patterns
    assert rules.noise_patterns


def test_auto_volume_patterns() -> None:
    rules = builtin_ruleset()
    match = rules.volume_patterns[0].match("第一卷 平庸少年")
    assert match is not None
    assert match.group("num") == "一"
    assert match.group("title") == "平庸少年"

    match = rules.volume_patterns[1].match("卷一 少年游")
    assert match is not None
    assert match.group("num") == "一"
    assert match.group("title") == "少年游"


def test_auto_chapter_patterns() -> None:
    rules = builtin_ruleset()
    match = rules.chapter_patterns[0].match("第104、105章 踏月而战！")
    assert match is not None
    assert match.group("num") == "104、105"
    assert match.group("title") == "踏月而战！"

    match = rules.chapter_patterns[0].match("第0001章 沈家")
    assert match is not None
    assert match.group("num") == "0001"


def test_auto_chapter_span_pattern() -> None:
    rules = builtin_ruleset()
    pattern = next(p for p in rules.chapter_patterns if "num2" in p.groupindex)
    match = pattern.match("第1037章—第1038章 合章")
    assert match is not None
    assert match.group("num") == "1037"
    assert match.group("num2") == "1038"
    assert match.group("title") == "合章"


def test_auto_combined_pattern() -> None:
    rules = builtin_ruleset()
    match = rules.combined_patterns[0].match("第一卷 占位卷名 第1章 占位章名")
    assert match is not None
    assert match.group("vnum") == "一"
    assert match.group("cnum") == "1"
    assert match.group("volume") == "第一卷 占位卷名"
    assert match.group("chapter") == "第1章 占位章名"


def test_zxs_noise_patterns() -> None:
    auto = builtin_ruleset()
    zxs = builtin_ruleset("zxs")
    assert not _noise(auto, "知轩藏书")
    assert _noise(zxs, "知轩藏书")
    assert _noise(zxs, "更多精校小说")
    assert _noise(zxs, "http://www.zxcs.me")
    assert _noise(auto, "百度搜索")
    assert _noise(auto, "<br>")
    assert not _noise(auto, "这是一段普通正文，没有广告")


def test_strict_profile_requires_separator() -> None:
    rules = builtin_ruleset("strict")
    assert rules.max_heading_length == 40
    assert rules.require_column_zero is True
    assert rules.allow_indented_headings is False
    assert not _matches(rules.chapter_patterns, "第一章活着")
    assert _matches(rules.chapter_patterns, "第1章 标题")
    assert _matches(rules.chapter_patterns, "第一章：标题")
    match = rules.chapter_patterns[0].match("第1章 标题")
    assert match is not None
    assert match.group("title") == "标题"


def test_loose_profile_enables_pure_numbers() -> None:
    rules = builtin_ruleset("loose")
    assert rules.max_heading_length == 80
    assert rules.allow_indented_headings is True
    assert rules.pure_number_headings is True
    assert _matches(rules.pure_number_patterns, "1. 标题")
    assert _matches(rules.pure_number_patterns, "001、序")


def test_unknown_profile_raises() -> None:
    with pytest.raises(ValueError, match="unknown rules profile"):
        builtin_ruleset("nope")


def test_make_ruleset_overrides_and_file(tmp_path) -> None:
    rules_file = tmp_path / "rules.toml"
    rules_file.write_text(
        "[heading]\nmax_length = 33\nallow_indented_headings = false\n",
        encoding="utf-8",
    )
    rules = make_ruleset(
        profile="strict",
        rules_file=rules_file,
        max_heading_length=12,
        allow_indented_headings=True,
    )
    assert rules.max_heading_length == 12
    assert rules.allow_indented_headings is True
    assert rules.require_column_zero is True


def test_load_rules_reads_toml(tmp_path) -> None:
    rules_file = tmp_path / "custom.toml"
    rules_file.write_text(
        "[heading]\nmax_length = 25\n\n[noise]\npatterns = ['自定义广告']\n",
        encoding="utf-8",
    )
    rules = load_rules(rules_file)
    assert rules.max_heading_length == 25
    assert _noise(rules, "这里有自定义广告")


def test_parse_toml_heading_values() -> None:
    rules = parse_toml_rules(
        """
[heading]
max_length = 30
require_column_zero = false
allow_indented_headings = false
allowed_indent = "  "
pure_number_headings = true
volume_suffix_special_suffixes = ["序", "跋"]
"""
    )
    assert rules.max_heading_length == 30
    assert rules.require_column_zero is False
    assert rules.allow_indented_headings is False
    assert rules.allowed_indent == "  "
    assert rules.pure_number_headings is True
    assert rules.volume_suffix_special_suffixes == ["序", "跋"]


def test_parse_toml_patterns_append() -> None:
    base = builtin_ruleset()
    rules = parse_toml_rules(
        """
[patterns]
volume = '^卷首(?P<num>[0-9]+)(?P<title>.*)$'
chapter = [
  '^第(?P<num>[0-9]+)话[\\s\\u3000:：]*(?P<title>.*)$',
  '^第(?P<num>[0-9]+)集[\\s\\u3000:：]*(?P<title>.*)$',
]
section = '^第(?P<num>[0-9]+)段[\\s\\u3000:：]*(?P<title>.*)$'
combined = '^(?P<volume>第(?P<vnum>[0-9]+)卷.*?)[\\s　:：]+(?P<chapter>第(?P<cnum>[0-9]+)章.*)$'
""",
        base=base,
    )
    assert len(rules.volume_patterns) == len(base.volume_patterns) + 1
    assert len(rules.chapter_patterns) == len(base.chapter_patterns) + 2
    assert len(rules.section_patterns) == len(base.section_patterns) + 1
    assert len(rules.combined_patterns) == len(base.combined_patterns) + 1
    assert _matches(rules.volume_patterns, "卷首1开篇")
    assert _matches(rules.chapter_patterns, "第3话 标题")


def test_parse_toml_patterns_replace() -> None:
    rules = parse_toml_rules(
        """
[patterns]
replace_patterns = true
volume = '^卷首(?P<num>[0-9]+)(?P<title>.*)$'
"""
    )
    assert len(rules.volume_patterns) == 1
    assert _matches(rules.volume_patterns, "卷首1开篇")


def test_parse_toml_special_patterns() -> None:
    rules = parse_toml_rules(
        """
[patterns]
special = '^(?P<special>卷首序)$'
"""
    )
    assert len(rules.special_patterns) == 1
    match = rules.special_patterns[0].match("卷首序")
    assert match is not None
    assert match.group("special") == "卷首序"


def test_parse_toml_exclude_append_and_replace() -> None:
    base = builtin_ruleset()
    appended = parse_toml_rules(
        '[exclude]\nvolume_suffixes = ["部"]\nchapter_suffixes = ["回廊"]\n',
        base=base,
    )
    assert "部" in appended.invalid_volume_suffixes
    assert "门" in appended.invalid_volume_suffixes
    assert "回廊" in appended.invalid_chapter_suffixes

    replaced = parse_toml_rules(
        """
[exclude]
replace_exclude = true
volume_suffixes = ["部"]
chapter_suffixes = ["回廊"]
""",
        base=base,
    )
    assert replaced.invalid_volume_suffixes == ["部"]
    assert replaced.invalid_chapter_suffixes == ["回廊"]


def test_parse_toml_noise_append_and_replace() -> None:
    base = builtin_ruleset()
    appended = parse_toml_rules("[noise]\npatterns = ['广告甲']\n", base=base)
    assert _noise(appended, "广告甲")
    assert _noise(appended, "百度搜索")

    replaced = parse_toml_rules(
        "[noise]\nreplace = true\npatterns = ['广告甲']\n", base=base
    )
    assert _noise(replaced, "广告甲")
    assert not _noise(replaced, "百度搜索")


def test_parse_toml_unknown_key_raises() -> None:
    with pytest.raises(ValueError, match="max_len"):
        parse_toml_rules("[heading]\nmax_len = 10\n")
    with pytest.raises(ValueError, match="mystery"):
        parse_toml_rules("mystery = true\n")
    with pytest.raises(ValueError, match="nope"):
        parse_toml_rules("[patterns]\nnope = 'x'\n")


def test_parse_toml_bad_regex_raises_with_context() -> None:
    with pytest.raises(ValueError, match=r"\[patterns\] volume"):
        parse_toml_rules("[patterns]\nvolume = '('\n")
    with pytest.raises(ValueError, match=r"\[noise\] patterns"):
        parse_toml_rules("[noise]\npatterns = ['[']\n")


def test_parse_toml_invalid_toml_raises() -> None:
    with pytest.raises(ValueError, match="invalid rules TOML"):
        parse_toml_rules("[heading\nmax_length = 1\n")


def test_builtin_rulesets_are_independent() -> None:
    first = builtin_ruleset("zxs")
    second = builtin_ruleset("zxs")
    first.noise_patterns.append(re.compile("only-in-first"))
    assert not _noise(second, "only-in-first")
