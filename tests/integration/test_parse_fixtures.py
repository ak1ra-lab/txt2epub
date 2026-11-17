from __future__ import annotations

import json
from pathlib import Path

import pytest

from txt2epub_cli.hierarchy import flatten
from txt2epub_cli.model import Disposition, HeadingKind
from txt2epub_cli.parser import parse_file, parse_text
from txt2epub_cli.report import report_dict


def parse_fixture(fixtures: Path, name: str, **kwargs):
    return parse_file(fixtures / name, **kwargs)


def titles(result) -> list[str]:
    return [node.heading.title for node in flatten(result.roots)]


@pytest.mark.parametrize(
    ("name", "volumes", "chapters", "sections", "specials"),
    [
        ("simple_arabic.txt", 0, 3, 0, 0),
        ("simple_chinese.txt", 0, 3, 0, 0),
        ("zero_padded.txt", 0, 3, 0, 0),
        ("no_separator.txt", 0, 3, 0, 0),
        ("volume_chapter.txt", 2, 4, 0, 0),
        ("volume_no_blank.txt", 2, 4, 0, 0),
        ("combined_prefix.txt", 2, 4, 0, 0),
        ("combined_volume_special.txt", 1, 2, 0, 1),
        ("multi_number.txt", 0, 3, 0, 0),
        ("special_sections.txt", 1, 1, 0, 6),
        ("duplicates_noise.txt", 0, 2, 0, 0),
        ("toc_page.txt", 0, 2, 0, 0),
        ("front_matter.txt", 0, 2, 0, 0),
        ("false_positives.txt", 0, 1, 0, 0),
        ("indented_headings.txt", 0, 3, 0, 1),
    ],
)
def test_fixture_counts(
    fixtures: Path, name: str, volumes: int, chapters: int, sections: int, specials: int
):
    result = parse_fixture(fixtures, name)
    assert result.stats.volumes == volumes
    assert result.stats.chapters == chapters
    assert result.stats.sections == sections
    assert result.stats.specials == specials
    assert result.coverage.ok, (name, result.coverage.missing, result.coverage.extra)
    assert not [
        line for line in result.ledger if line.disposition is Disposition.UNATTACHED
    ]


def test_combined_prefix_strips_volume_prefix(fixtures: Path):
    result = parse_fixture(fixtures, "combined_prefix.txt")
    chapter_titles = [
        node.heading.title
        for node in flatten(result.roots)
        if node.heading.kind is HeadingKind.CHAPTER
    ]
    assert chapter_titles == [
        "第1章 占位章名",
        "第2章 占位章名",
        "第1章 占位章名",
        "第2章 占位章名",
    ]
    assert all("卷" not in title for title in chapter_titles)


def test_combined_volume_special_splits(fixtures: Path):
    result = parse_fixture(fixtures, "combined_volume_special.txt")
    volume = result.roots[0]
    assert volume.heading.kind is HeadingKind.VOLUME
    assert volume.heading.title == "第一卷 占位卷名"
    assert volume.children[0].heading.title == "卷首序"
    assert volume.children[0].heading.kind is HeadingKind.SPECIAL


def test_multi_number_is_one_node(fixtures: Path):
    result = parse_fixture(fixtures, "multi_number.txt")
    chapter_titles = [t for t in titles(result) if t.startswith("第")]
    assert chapter_titles[0] == "第104、105章 占位标题"
    assert chapter_titles[-1] == "第1037章—第1038章 占位合章"
    assert result.stats.chapters == 3


def test_special_hierarchy(fixtures: Path):
    result = parse_fixture(fixtures, "special_sections.txt")
    roots = {node.heading.title: node for node in result.roots}
    assert "前传 占位前传" in roots
    assert roots["前传 占位前传"].children[0].heading.title == "第一章 占位标题"
    assert "番外 占位番外（一）" in roots
    assert "终章 占位标题" in roots
    assert "后记，占位说明。" in roots
    assert "完本感言" in roots


def test_duplicates_and_noise(fixtures: Path):
    result = parse_fixture(fixtures, "duplicates_noise.txt")
    codes = [issue.code for issue in result.issues]
    assert "duplicate_number" in codes
    assert "noise_removed" in codes
    assert result.stats.chapters == 2
    assert result.stats.duplicates == 1
    assert result.stats.noise >= 2
    body_text = "\n".join(
        line.text for node in flatten(result.roots) for line in node.body
    )
    assert "这是重复章节的占位正文。" in body_text
    assert result.coverage.ok


def test_duplicates_noise_keep_noise(fixtures: Path):
    result = parse_fixture(fixtures, "duplicates_noise.txt", keep_noise=True)
    assert result.stats.noise == 0
    assert result.coverage.ok


def test_toc_page_removed(fixtures: Path):
    result = parse_fixture(fixtures, "toc_page.txt")
    assert result.stats.toc_pages >= 5
    assert result.stats.chapters == 2
    assert result.coverage.ok
    codes = [issue.code for issue in result.issues]
    assert "toc_page_removed" in codes


def test_toc_page_kept(fixtures: Path):
    result = parse_fixture(fixtures, "toc_page.txt", keep_toc=True)
    assert result.stats.toc_pages >= 5
    assert result.stats.chapters == 2
    assert result.coverage.ok
    front = "\n".join(line.text for line in result.book.front_matter)
    assert "目录" in front


def test_front_matter_metadata(fixtures: Path):
    result = parse_fixture(fixtures, "front_matter.txt")
    assert result.book.title == "占位书名"
    assert result.book.author == "占位作者"
    assert "这是一段占位简介。" in (result.book.description or "")
    assert result.stats.front_matter_lines >= 3
    assert result.coverage.ok


def test_false_positives_are_body(fixtures: Path):
    result = parse_fixture(fixtures, "false_positives.txt")
    assert result.stats.volumes == 0
    assert result.stats.chapters == 1
    body = "\n".join(line.text for line in result.book.front_matter)
    assert "第一回合的接触" in body
    assert "第九部落" in body
    assert "第三部分内容" in body
    assert result.coverage.ok


def test_indented_headings(fixtures: Path):
    result = parse_fixture(fixtures, "indented_headings.txt")
    assert result.stats.specials == 1
    assert result.stats.chapters == 3
    assert result.coverage.ok


def test_no_separator_titles(fixtures: Path):
    result = parse_fixture(fixtures, "no_separator.txt")
    assert titles(result) == ["第一章占位标题", "第二章占位标题", "第三章占位标题"]


def test_empty_file():
    result = parse_text("")
    assert result.stats.lines == 0
    assert result.stats.chapters == 0
    assert result.coverage.ok


def test_no_headings_text_kept_as_front_matter():
    result = parse_text("这是一段没有标题的占位正文。\n还有一段。\n")
    assert result.stats.chapters == 0
    assert len(result.book.front_matter) == 2
    assert result.coverage.ok


def test_missing_chapter_title_is_kept():
    result = parse_text("第一章\n　　占位正文。\n")
    assert result.stats.chapters == 1
    assert result.roots[0].heading.title == "第一章"
    assert result.coverage.ok


def test_report_json_has_no_body_text(fixtures: Path):
    result = parse_fixture(fixtures, "simple_arabic.txt")
    payload = json.loads(json.dumps(report_dict(result), ensure_ascii=False))
    assert payload["schema_version"] == 1
    assert payload["stats"]["chapters"] == 3
    assert payload["coverage"]["ok"] is True
    assert "占位正文" not in json.dumps(payload, ensure_ascii=False)


def test_gb18030_file(tmp_path: Path):
    path = tmp_path / "gbk_book.txt"
    path.write_bytes("第一章 占位标题\n　　占位正文。\n".encode("gb18030"))
    result = parse_file(path)
    assert result.encoding is not None
    assert result.encoding.encoding in {"gb18030", "utf-8"}
    assert result.stats.chapters == 1
    assert result.coverage.ok


def test_utf16_file(tmp_path: Path):
    path = tmp_path / "utf16_book.txt"
    path.write_text("第一章 占位标题\n　　占位正文。\n", encoding="utf-16")
    result = parse_file(path)
    assert result.encoding is not None
    assert result.encoding.encoding == "utf-16"
    assert result.stats.chapters == 1


def test_forced_encoding(tmp_path: Path):
    path = tmp_path / "forced.txt"
    path.write_bytes("第一章 占位标题\n　　占位正文。\n".encode("gb18030"))
    result = parse_file(path, forced_encoding="gb18030")
    assert result.encoding is not None
    assert result.encoding.encoding == "gb18030"
    assert result.stats.chapters == 1


def test_all_fixtures_have_balanced_coverage(fixtures: Path):
    for path in sorted(fixtures.glob("*.txt")):
        result = parse_file(path)
        assert result.coverage.ok, (
            path.name,
            result.coverage.missing,
            result.coverage.extra,
        )
        assert result.coverage.source_units == (
            result.coverage.output_units + result.coverage.dropped_units
        )


def test_exact_dedupe_removes_identical_chapters_across_containers():
    text = (
        "第一卷 占位卷名\n"
        "第1章 占位标题\n"
        "　　这是相同的占位正文。\n"
        "第二卷 另占位卷名\n"
        "第1章 占位标题\n"
        "　　这是相同的占位正文。\n"
    )
    result = parse_text(text, dedupe="exact")
    assert result.stats.chapters == 1
    assert result.coverage.ok


def test_similar_dedupe_removes_near_identical_chapters():
    text = (
        "第一卷 占位卷名\n"
        "第1章 占位标题\n"
        "　　这是相同的占位正文。\n"
        "第二卷 另占位卷名\n"
        "第1章 占位标题\n"
        "　　这是相同的占位正文！\n"
    )
    result = parse_text(text, dedupe="similar")
    assert result.stats.chapters == 1
    assert result.coverage.ok


def test_off_dedupe_keeps_both_chapters():
    text = (
        "第一卷 占位卷名\n"
        "第1章 占位标题\n"
        "　　这是相同的占位正文。\n"
        "第二卷 另占位卷名\n"
        "第1章 占位标题\n"
        "　　这是相同的占位正文。\n"
    )
    result = parse_text(text, dedupe="off")
    assert result.stats.chapters == 2
    assert result.coverage.ok
