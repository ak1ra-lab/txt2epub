"""Heading recognition rules and profiles.

Rules are deliberately small and line-oriented: every pattern is applied to a
single stripped line, never to a whole document.  This keeps backtracking
bounded and makes the inspect report explainable.
"""

from __future__ import annotations

import copy
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# Number characters accepted in headings.  Kept bracket-free so it can be
# embedded in any regex character class.  Covers ASCII/full-width digits,
# Chinese numerals, financial numerals, 廿/卅 and Roman numerals.
NUM = (
    "0-9０-９零〇一二三四五六七八九十百千万两壹贰叁肆伍陆柒捌玖拾佰仟廿卅IVXLCDMivxlcdm"
)

_BUILTIN_SPECIAL_TITLES = [
    "序章",
    "序言",
    "楔子",
    "引子",
    "前言",
    "后记",
    "尾声",
    "终章",
    "大结局",
    "番外",
    "外传",
    "附录",
    "前传",
    "完本感言",
    "上架感言",
    "作者的话",
]

_GENERIC_NOISE = [
    "百度搜索",
    "请务必保存好书签",
    "为您提供大神",
    "免费阅读",
    "秒更",
    "移动端：",
    "本章未完",
    "请收藏本站",
    "br>",
]

_ZXS_NOISE = ["知轩藏书", "更多精校小说", r"zxcs\.me"]

_VOLUME_PATTERNS = [
    rf"^第(?P<num>[{NUM}]+)[卷部篇册](?:[\s\u3000:：、,，.\-—]+(?P<title>.*))?$",
    rf"^卷(?P<num>[{NUM}]+)(?:[\s\u3000:：、,，.\-—]+(?P<title>.*))?$",
]

_CHAPTER_PATTERNS = [
    rf"^第(?P<num>[{NUM}]+(?:[、,，]\s*[{NUM}]+)*)[章节回集幕](?:[\s\u3000:：]*(?P<title>.*))?$",
    rf"^第(?P<num>[{NUM}]+)[章节回集幕]\s*[—\-~～至到]\s*第(?P<num2>[{NUM}]+)[章节回集幕](?:[\s\u3000:：]*(?P<title>.*))?$",
]

_STRICT_CHAPTER_PATTERNS = [
    rf"^第(?P<num>[{NUM}]+(?:[、,，]\s*[{NUM}]+)*)[章节回集幕][\s\u3000:：]+(?P<title>.+)$",
    rf"^第(?P<num>[{NUM}]+)[章节回集幕]\s*[—\-~～至到]\s*第(?P<num2>[{NUM}]+)[章节回集幕][\s\u3000:：]+(?P<title>.+)$",
]

_SECTION_PATTERNS = [
    rf"^第(?P<num>[{NUM}]+)节(?:[\s\u3000:：]*(?P<title>.*))?$",
]

_COMBINED_PATTERNS = [
    rf"^(?P<volume>第(?P<vnum>[{NUM}]+)[卷部篇册](?:[\s\u3000:：]+.*?)?)[\s\u3000:：]+(?P<chapter>第(?P<cnum>[{NUM}]+(?:[、,，]\s*[{NUM}]+)*)[章节回集幕].*)$",
    rf"^(?P<volume>卷(?P<vnum>[{NUM}]+)(?:[\s\u3000:：]+.*?)?)[\s\u3000:：]+(?P<chapter>第(?P<cnum>[{NUM}]+(?:[、,，]\s*[{NUM}]+)*)[章节回集幕].*)$",
]

_PURE_NUMBER_PATTERNS = [
    r"^(?P<num>\d{1,5})[.、．]\s*(?P<title>.*)$",
]


def _compile(patterns: list[str], context: str) -> list[re.Pattern[str]]:
    compiled: list[re.Pattern[str]] = []
    for pattern in patterns:
        try:
            compiled.append(re.compile(pattern))
        except re.error as exc:
            raise ValueError(f"invalid regex in {context}: {pattern!r}: {exc}") from exc
    return compiled


@dataclass(slots=True)
class RuleSet:
    name: str = "auto"
    max_heading_length: int = 50
    require_column_zero: bool = True
    allow_indented_headings: bool = True
    allowed_indent: str = "\u3000"
    volume_patterns: list[re.Pattern[str]] = field(default_factory=list)
    chapter_patterns: list[re.Pattern[str]] = field(default_factory=list)
    section_patterns: list[re.Pattern[str]] = field(default_factory=list)
    combined_patterns: list[re.Pattern[str]] = field(default_factory=list)
    special_titles: list[str] = field(
        default_factory=lambda: list(_BUILTIN_SPECIAL_TITLES)
    )
    special_patterns: list[re.Pattern[str]] = field(default_factory=list)
    invalid_volume_suffixes: list[str] = field(
        default_factory=lambda: ["门", "队", "属", "分", "件", "落"]
    )
    invalid_chapter_suffixes: list[str] = field(
        default_factory=lambda: ["回合", "回事", "回到", "回去", "回来", "回答", "回应"]
    )
    noise_patterns: list[re.Pattern[str]] = field(default_factory=list)
    toc_titles: list[str] = field(
        default_factory=lambda: ["目录", "目錄", "Contents", "Table of Contents"]
    )
    pure_number_headings: bool = False
    pure_number_patterns: list[re.Pattern[str]] = field(default_factory=list)
    volume_suffix_special_suffixes: list[str] = field(
        default_factory=lambda: ["序", "章", "篇", "传", "记", "录"]
    )
    max_indented_volume_length: int = 20
    noise_max_length: int = 80


def _new_ruleset(name: str) -> RuleSet:
    rules = RuleSet(name=name)
    rules.volume_patterns = _compile(_VOLUME_PATTERNS, "built-in volume patterns")
    rules.chapter_patterns = _compile(_CHAPTER_PATTERNS, "built-in chapter patterns")
    rules.section_patterns = _compile(_SECTION_PATTERNS, "built-in section patterns")
    rules.combined_patterns = _compile(_COMBINED_PATTERNS, "built-in combined patterns")
    rules.pure_number_patterns = _compile(
        _PURE_NUMBER_PATTERNS, "built-in pure-number patterns"
    )
    rules.noise_patterns = [re.compile(pattern) for pattern in _GENERIC_NOISE]
    return rules


def builtin_ruleset(name: str = "auto") -> RuleSet:
    """Return a fresh rule set for a built-in profile."""
    profile = name.strip().lower()
    if profile == "auto":
        return _new_ruleset("auto")

    if profile == "zxs":
        rules = _new_ruleset("zxs")
        rules.noise_patterns.extend(re.compile(pattern) for pattern in _ZXS_NOISE)
        return rules

    if profile == "strict":
        rules = _new_ruleset("strict")
        rules.require_column_zero = True
        rules.allow_indented_headings = False
        rules.max_heading_length = 40
        rules.chapter_patterns = _compile(
            _STRICT_CHAPTER_PATTERNS, "strict chapter patterns"
        )
        return rules

    if profile == "loose":
        rules = _new_ruleset("loose")
        rules.allow_indented_headings = True
        rules.max_heading_length = 80
        rules.pure_number_headings = True
        return rules

    raise ValueError(
        f"unknown rules profile: {name!r}; expected one of: auto, zxs, strict, loose"
    )


def _clone_ruleset(rules: RuleSet) -> RuleSet:
    return copy.deepcopy(rules)


def _table(data: dict, section: str) -> dict:
    value = data.get(section, {})
    if not isinstance(value, dict):
        raise ValueError(f"rules key [{section}] must be a table")
    return value


def _check_keys(table: dict, allowed: set[str], section: str) -> None:
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise ValueError(f"unknown rules key: [{section}] {unknown[0]}")


def _as_bool(value: object, key: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"rules key {key} must be a boolean")
    return value


def _as_int(value: object, key: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"rules key {key} must be an integer")
    return value


def _as_str(value: object, key: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"rules key {key} must be a string")
    return value


def _as_str_list(value: object, key: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"rules key {key} must be a list of strings")
    return list(value)


def _pattern_list(value: object, key: str) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    raise ValueError(f"[patterns] {key} must be a string or a list of strings")


def parse_toml_rules(text: str, base: RuleSet | None = None) -> RuleSet:
    """Parse a TOML rules document on top of *base* (default: auto)."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid rules TOML: {exc}") from exc

    rules = _clone_ruleset(base if base is not None else builtin_ruleset("auto"))

    known_sections = {"heading", "patterns", "exclude", "noise"}
    unknown_sections = sorted(set(data) - known_sections)
    if unknown_sections:
        raise ValueError(f"unknown rules key: {unknown_sections[0]}")

    heading = _table(data, "heading")
    _check_keys(
        heading,
        {
            "max_length",
            "require_column_zero",
            "allow_indented_headings",
            "allowed_indent",
            "pure_number_headings",
            "volume_suffix_special_suffixes",
        },
        "heading",
    )
    if "max_length" in heading:
        rules.max_heading_length = _as_int(
            heading["max_length"], "[heading] max_length"
        )
    if "require_column_zero" in heading:
        rules.require_column_zero = _as_bool(
            heading["require_column_zero"], "[heading] require_column_zero"
        )
    if "allow_indented_headings" in heading:
        rules.allow_indented_headings = _as_bool(
            heading["allow_indented_headings"], "[heading] allow_indented_headings"
        )
    if "allowed_indent" in heading:
        rules.allowed_indent = _as_str(
            heading["allowed_indent"], "[heading] allowed_indent"
        )
    if "pure_number_headings" in heading:
        rules.pure_number_headings = _as_bool(
            heading["pure_number_headings"], "[heading] pure_number_headings"
        )
    if "volume_suffix_special_suffixes" in heading:
        rules.volume_suffix_special_suffixes = _as_str_list(
            heading["volume_suffix_special_suffixes"],
            "[heading] volume_suffix_special_suffixes",
        )

    patterns = _table(data, "patterns")
    _check_keys(
        patterns,
        {"volume", "chapter", "section", "combined", "special", "replace_patterns"},
        "patterns",
    )
    replace_patterns = _as_bool(
        patterns.get("replace_patterns", False), "[patterns] replace_patterns"
    )
    for key, attribute in (
        ("volume", "volume_patterns"),
        ("chapter", "chapter_patterns"),
        ("section", "section_patterns"),
        ("combined", "combined_patterns"),
        ("special", "special_patterns"),
    ):
        if key not in patterns:
            continue
        compiled = _compile(_pattern_list(patterns[key], key), f"[patterns] {key}")
        existing: list[re.Pattern[str]] = getattr(rules, attribute)
        if replace_patterns:
            setattr(rules, attribute, compiled)
        else:
            existing.extend(compiled)

    exclude = _table(data, "exclude")
    _check_keys(
        exclude, {"volume_suffixes", "chapter_suffixes", "replace_exclude"}, "exclude"
    )
    replace_exclude = _as_bool(
        exclude.get("replace_exclude", False), "[exclude] replace_exclude"
    )
    for key, attribute in (
        ("volume_suffixes", "invalid_volume_suffixes"),
        ("chapter_suffixes", "invalid_chapter_suffixes"),
    ):
        if key not in exclude:
            continue
        values = _as_str_list(exclude[key], f"[exclude] {key}")
        if replace_exclude:
            setattr(rules, attribute, values)
        else:
            getattr(rules, attribute).extend(values)

    noise = _table(data, "noise")
    _check_keys(noise, {"patterns", "replace"}, "noise")
    if "patterns" in noise:
        compiled_noise = _compile(
            _pattern_list(noise["patterns"], "patterns"), "[noise] patterns"
        )
        if _as_bool(noise.get("replace", False), "[noise] replace"):
            rules.noise_patterns = compiled_noise
        else:
            rules.noise_patterns.extend(compiled_noise)

    return rules


def load_rules(path: Path, base: RuleSet | None = None) -> RuleSet:
    """Load a TOML rule override from *path*."""
    rules_path = Path(path)
    try:
        text = rules_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read rules file {rules_path}: {exc}") from exc
    return parse_toml_rules(text, base=base)


def make_ruleset(
    *,
    profile: str = "auto",
    rules_file: str | Path | None = None,
    max_heading_length: int | None = None,
    allow_indented_headings: bool | None = None,
) -> RuleSet:
    """Build a rule set from a profile, optional TOML file and CLI overrides."""
    rules = builtin_ruleset(profile)
    if rules_file is not None:
        rules = load_rules(Path(rules_file), base=rules)
    if max_heading_length is not None:
        rules.max_heading_length = max_heading_length
    if allow_indented_headings is not None:
        rules.allow_indented_headings = allow_indented_headings
    return rules
