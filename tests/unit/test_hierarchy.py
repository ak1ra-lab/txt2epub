from __future__ import annotations

from txt2epub_cli.hierarchy import build_tree, flatten
from txt2epub_cli.model import Heading, HeadingKind


def heading(
    hid: str,
    kind: HeadingKind,
    title: str,
    line_no: int,
    *,
    number: str | None = None,
    detail: dict | None = None,
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
        detail=detail or {},
    )


def test_volume_chapter_nesting_and_levels():
    roots, targets = build_tree(
        [
            heading("v1", HeadingKind.VOLUME, "第一卷", 1, number="一"),
            heading("c1", HeadingKind.CHAPTER, "第一章", 2, number="1"),
            heading("c2", HeadingKind.CHAPTER, "第二章", 3, number="2"),
            heading("v2", HeadingKind.VOLUME, "第二卷", 4, number="二"),
            heading("c3", HeadingKind.CHAPTER, "第一章", 5, number="1"),
        ]
    )
    assert [node.heading.id for node in roots] == ["v1", "v2"]
    assert [child.heading.id for child in roots[0].children] == ["c1", "c2"]
    assert roots[0].children[0].heading.level == 2
    assert targets[2].heading.id == "c1"
    assert [node.heading.id for node in flatten(roots)] == [
        "v1",
        "c1",
        "c2",
        "v2",
        "c3",
    ]


def test_container_special_parents_chapters_until_volume():
    roots, _ = build_tree(
        [
            heading(
                "pre",
                HeadingKind.SPECIAL,
                "前传",
                1,
                detail={"container": True},
            ),
            heading("c1", HeadingKind.CHAPTER, "第一章", 2, number="1"),
            heading("v1", HeadingKind.VOLUME, "第一卷", 3, number="一"),
            heading("c2", HeadingKind.CHAPTER, "第一章", 4, number="1"),
        ]
    )
    assert [node.heading.id for node in roots] == ["pre", "v1"]
    assert roots[0].children[0].heading.id == "c1"
    assert roots[1].children[0].heading.id == "c2"


def test_ordinary_special_stays_at_root_after_volume():
    roots, _ = build_tree(
        [
            heading("v1", HeadingKind.VOLUME, "第一卷", 1, number="一"),
            heading("s", HeadingKind.SPECIAL, "序章", 2),
            heading("c1", HeadingKind.CHAPTER, "第一章", 3, number="1"),
        ]
    )
    assert [node.heading.id for node in roots] == ["v1", "s"]
    assert roots[0].children[0].heading.id == "c1"


def test_volume_suffix_special_attaches_inside_volume():
    roots, _ = build_tree(
        [
            heading("v1", HeadingKind.VOLUME, "第一卷", 1, number="一"),
            heading(
                "s",
                HeadingKind.SPECIAL,
                "卷首序",
                2,
                detail={"in_volume": True},
            ),
            heading("c1", HeadingKind.CHAPTER, "第一章", 3, number="1"),
        ]
    )
    assert [node.heading.id for node in roots] == ["v1"]
    assert [child.heading.id for child in roots[0].children] == ["s", "c1"]


def test_section_attaches_to_current_chapter():
    roots, targets = build_tree(
        [
            heading("c1", HeadingKind.CHAPTER, "第一章", 1, number="1"),
            heading("s1", HeadingKind.SECTION, "第一节", 2, number="1"),
            heading("s2", HeadingKind.SECTION, "第二节", 3, number="2"),
        ]
    )
    assert [child.heading.id for child in roots[0].children] == ["s1", "s2"]
    assert roots[0].children[0].heading.level == 2
    assert targets[2].heading.id == "s1"


def test_combined_heading_line_target_is_chapter():
    roots, targets = build_tree(
        [
            heading(
                "v1",
                HeadingKind.VOLUME,
                "第一卷",
                1,
                number="一",
                detail={"combined": True},
            ),
            heading("c1", HeadingKind.CHAPTER, "第1章", 1, number="1"),
        ]
    )
    assert targets[1].heading.id == "c1"
    assert roots[0].children[0].heading.id == "c1"
