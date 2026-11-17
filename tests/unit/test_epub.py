"""Unit tests for the EPUB 3 + NCX writer."""

from __future__ import annotations

import posixpath
import re
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from txt2epub_cli.epub import build_epub, write_epub
from txt2epub_cli.model import (
    Book,
    Coverage,
    Disposition,
    Heading,
    HeadingKind,
    Node,
    ParseResult,
    SourceLine,
    Stats,
)

XHTML = "{http://www.w3.org/1999/xhtml}"
OPF = "{http://www.idpf.org/2007/opf}"
NCX = "{http://www.daisy.org/z3986/2005/ncx/}"
DC = "{http://purl.org/dc/elements/1.1/}"
EPUB = "{http://www.idpf.org/2007/ops}"

REQUIRED_MEMBERS = {
    "mimetype",
    "META-INF/container.xml",
    "OEBPS/content.opf",
    "OEBPS/nav.xhtml",
    "OEBPS/toc.ncx",
    "OEBPS/style.css",
    "OEBPS/text/front-matter.xhtml",
    "OEBPS/text/part-0001.xhtml",
    "OEBPS/text/chapter-0001.xhtml",
    "OEBPS/text/section-0001.xhtml",
}


def _source_line(
    line_no: int, text: str, disposition: Disposition = Disposition.BODY
) -> SourceLine:
    stripped = text.strip()
    return SourceLine(
        line_no=line_no,
        raw=text,
        text=text,
        stripped=stripped,
        indent=text[: len(text) - len(text.lstrip())],
        normalized=stripped,
        disposition=disposition,
    )


def _heading(
    identifier: str,
    kind: HeadingKind,
    title: str,
    *,
    level: int = 1,
    line_no: int = 1,
) -> Heading:
    return Heading(
        id=identifier,
        kind=kind,
        level=level,
        raw=title,
        title=title,
        number=None,
        line_no=line_no,
        confidence=1.0,
    )


def _node(
    heading: Heading,
    *,
    body: list[SourceLine] | None = None,
    children: list[Node] | None = None,
) -> Node:
    node = Node(heading=heading, body=list(body or []), children=list(children or []))
    for child in node.children:
        child.parent = node
    return node


def _result(
    roots: list[Node],
    *,
    front_matter: list[SourceLine] | None = None,
    title: str = "测试书",
    author: str | None = "某作者",
    description: str | None = "简介",
) -> ParseResult:
    book = Book(
        source=Path("book.txt"),
        title=title,
        author=author,
        language="zh",
        description=description,
        front_matter=list(front_matter or []),
    )
    return ParseResult(
        book=book,
        roots=list(roots),
        ledger=[],
        issues=[],
        stats=Stats(),
        coverage=Coverage(ok=True),
    )


def _book() -> ParseResult:
    chapter = _node(
        _heading("chapter-1", HeadingKind.CHAPTER, "第一章", level=2),
        body=[_source_line(3, "\u3000第一章正文")],
    )
    volume = _node(
        _heading("volume-1", HeadingKind.VOLUME, "第一卷"),
        body=[_source_line(2, "\u3000卷首正文")],
        children=[chapter],
    )
    section = _node(
        _heading("section-1", HeadingKind.SECTION, "第一节", level=2),
        body=[_source_line(5, "\u3000第一节正文")],
    )
    return _result([volume, section])


def _parse(archive: zipfile.ZipFile, name: str) -> ET.Element:
    return ET.fromstring(archive.read(name))


def _assert_hrefs_exist(archive: zipfile.ZipFile, members: set[str], name: str) -> None:
    root = _parse(archive, name)
    for element in root.iter():
        for attribute in ("href", "src"):
            value = element.get(attribute)
            if value is None:
                continue
            target = posixpath.normpath(
                posixpath.join(posixpath.dirname(name), value.split("#", 1)[0])
            )
            assert target in members, f"{name}: {attribute}={value!r} does not exist"


def test_zip_layout_and_mimetype(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "book.epub"

    written = write_epub(_book(), output)

    assert written == output
    assert output.is_file()
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        infos = archive.infolist()
        assert infos[0].filename == "mimetype"
        assert infos[0].compress_type == zipfile.ZIP_STORED
        assert infos[0].file_size == len(b"application/epub+zip")
        assert archive.read("mimetype") == b"application/epub+zip"
        assert all(info.compress_type == zipfile.ZIP_DEFLATED for info in infos[1:])
        assert set(archive.namelist()) >= REQUIRED_MEMBERS


def test_every_xml_document_parses(tmp_path: Path) -> None:
    output = tmp_path / "book.epub"
    write_epub(_book(), output)

    with zipfile.ZipFile(output) as archive:
        members = set(archive.namelist())
        assert members >= REQUIRED_MEMBERS

        container = _parse(archive, "META-INF/container.xml")
        rootfile = next(
            container.iter("{urn:oasis:names:tc:opendocument:xmlns:container}rootfile")
        )
        assert rootfile.get("full-path") == "OEBPS/content.opf"

        xml_members = [
            name
            for name in members
            if name.endswith((".xml", ".opf", ".ncx", ".xhtml"))
        ]
        assert xml_members
        for name in xml_members:
            _parse(archive, name)


def test_links_and_spine_resolve(tmp_path: Path) -> None:
    output = tmp_path / "book.epub"
    write_epub(_book(), output)

    with zipfile.ZipFile(output) as archive:
        members = set(archive.namelist())
        for name in ("OEBPS/nav.xhtml", "OEBPS/toc.ncx", "OEBPS/content.opf"):
            _assert_hrefs_exist(archive, members, name)
        for name in members:
            if name.startswith("OEBPS/text/") and name.endswith(".xhtml"):
                _assert_hrefs_exist(archive, members, name)

        package = _parse(archive, "OEBPS/content.opf")
        items = {
            item.get("id"): item for item in package.findall(f"{OPF}manifest/{OPF}item")
        }
        assert items["nav"].get("properties") == "nav"
        assert items["ncx"].get("media-type") == "application/x-dtbncx+xml"
        assert items["css"].get("media-type") == "text/css"
        assert items["front"].get("href") == "text/front-matter.xhtml"

        spine = package.find(f"{OPF}spine")
        assert spine is not None
        assert spine.get("toc") == "ncx"
        refs = [itemref.get("idref") for itemref in spine.findall(f"{OPF}itemref")]
        assert refs == ["front", "p0001", "c0001", "s0001"]
        assert all(ref in items for ref in refs)


def test_opf_metadata(tmp_path: Path) -> None:
    result = _book()
    output = tmp_path / "book.epub"
    write_epub(result, output)

    with zipfile.ZipFile(output) as archive:
        package = _parse(archive, "OEBPS/content.opf")
        assert package.get("unique-identifier") == "bookid"

        metadata = package.find(f"{OPF}metadata")
        assert metadata is not None
        identifier = metadata.findtext(f"{DC}identifier")
        assert identifier is not None
        assert identifier.startswith("urn:uuid:")
        uuid.UUID(identifier.removeprefix("urn:uuid:"))
        assert metadata.findtext(f"{DC}title") == result.book.title
        assert metadata.findtext(f"{DC}creator") == result.book.author
        assert metadata.findtext(f"{DC}language") == "zh"
        assert metadata.findtext(f"{DC}description") == result.book.description

        modified = next(
            (
                element.text
                for element in metadata.findall(f"{OPF}meta")
                if element.get("property") == "dcterms:modified"
            ),
            None,
        )
        assert modified is not None
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", modified)

        ncx = _parse(archive, "OEBPS/toc.ncx")
        ncx_uid = next(
            (
                element.get("content")
                for element in ncx.iter(f"{NCX}meta")
                if element.get("name") == "dtb:uid"
            ),
            None,
        )
        assert ncx_uid == identifier


def test_optional_metadata_omitted(tmp_path: Path) -> None:
    chapter = _node(
        _heading("chapter-1", HeadingKind.CHAPTER, "第一章"),
        body=[_source_line(1, "正文")],
    )
    result = _result([chapter], author=None, description=None)
    output = tmp_path / "book.epub"
    write_epub(result, output)

    with zipfile.ZipFile(output) as archive:
        package = _parse(archive, "OEBPS/content.opf")
        metadata = package.find(f"{OPF}metadata")
        assert metadata is not None
        assert metadata.find(f"{DC}creator") is None
        assert metadata.find(f"{DC}description") is None


def test_nav_nesting_and_parent_pages(tmp_path: Path) -> None:
    output = tmp_path / "book.epub"
    write_epub(_book(), output)

    with zipfile.ZipFile(output) as archive:
        nav = _parse(archive, "OEBPS/nav.xhtml")
        nav_element = nav.find(f".//{XHTML}nav")
        assert nav_element is not None
        assert nav_element.get(f"{EPUB}type") == "toc"

        top_list = nav_element.find(f"{XHTML}ol")
        assert top_list is not None
        top_items = top_list.findall(f"{XHTML}li")
        assert len(top_items) == 2

        volume_item = top_items[0]
        volume_link = volume_item.find(f"{XHTML}a")
        assert volume_link is not None
        assert volume_link.get("href") == "text/part-0001.xhtml"
        assert volume_link.text == "第一卷"

        child_list = volume_item.find(f"{XHTML}ol")
        assert child_list is not None
        chapter_link = child_list.find(f"{XHTML}li/{XHTML}a")
        assert chapter_link is not None
        assert chapter_link.get("href") == "text/chapter-0001.xhtml"
        assert chapter_link.text == "第一章"

        section_link = top_items[1].find(f"{XHTML}a")
        assert section_link is not None
        assert section_link.get("href") == "text/section-0001.xhtml"

        parent_page = _parse(archive, "OEBPS/text/part-0001.xhtml")
        assert parent_page.findtext(f".//{XHTML}h1") == "第一卷"
        paragraphs = parent_page.findall(f".//{XHTML}p")
        assert [paragraph.text for paragraph in paragraphs] == ["\u3000卷首正文"]

        chapter_page = _parse(archive, "OEBPS/text/chapter-0001.xhtml")
        assert chapter_page.findtext(f".//{XHTML}h2") == "第一章"

        ncx = _parse(archive, "OEBPS/toc.ncx")
        nav_map = ncx.find(f"{NCX}navMap")
        assert nav_map is not None
        top_points = nav_map.findall(f"{NCX}navPoint")
        assert len(top_points) == 2

        volume_point = top_points[0]
        volume_src = volume_point.find(f"{NCX}content")
        assert volume_src is not None
        assert volume_src.get("src") == "text/part-0001.xhtml"

        chapter_point = volume_point.find(f"{NCX}navPoint")
        assert chapter_point is not None
        chapter_src = chapter_point.find(f"{NCX}content")
        assert chapter_src is not None
        assert chapter_src.get("src") == "text/chapter-0001.xhtml"

        orders = [point.get("playOrder") for point in nav_map.iter(f"{NCX}navPoint")]
        assert orders == ["1", "2", "3"]


def test_xml_escaping(tmp_path: Path) -> None:
    title = "书名 & <测试> \"双引号\" '单引号'"
    body = "\u3000正文 & < > \" '"
    chapter = _node(
        _heading("chapter-1", HeadingKind.CHAPTER, title),
        body=[_source_line(1, body), _source_line(2, "   ")],
    )
    result = _result([chapter], title=title)
    output = tmp_path / "book.epub"

    written = build_epub(result, output)

    assert written == output
    with zipfile.ZipFile(output) as archive:
        package_raw = archive.read("OEBPS/content.opf").decode("utf-8")
        nav_raw = archive.read("OEBPS/nav.xhtml").decode("utf-8")
        page_raw = archive.read("OEBPS/text/chapter-0001.xhtml").decode("utf-8")
        for raw in (package_raw, nav_raw, page_raw):
            for entity in ("&amp;", "&lt;", "&gt;", "&quot;", "&apos;"):
                assert entity in raw

        nav = _parse(archive, "OEBPS/nav.xhtml")
        link = nav.find(f".//{XHTML}a")
        assert link is not None
        assert link.text == title

        page = _parse(archive, "OEBPS/text/chapter-0001.xhtml")
        assert page.findtext(f".//{XHTML}title") == title
        assert page.findtext(f".//{XHTML}h1") == title
        paragraphs = page.findall(f".//{XHTML}p")
        assert [paragraph.text for paragraph in paragraphs] == [body]


def test_large_node_splits_at_paragraph_boundaries(tmp_path: Path) -> None:
    paragraphs = [f"{index}" + "x" * 99 for index in range(1, 4)]
    chapter = _node(
        _heading("chapter-1", HeadingKind.CHAPTER, "长章"),
        body=[
            _source_line(index, paragraph)
            for index, paragraph in enumerate(paragraphs, start=1)
        ],
    )
    result = _result([chapter])
    output = tmp_path / "book.epub"
    write_epub(result, output, split_size=150)

    with zipfile.ZipFile(output) as archive:
        members = set(archive.namelist())
        files = [
            "OEBPS/text/chapter-0001.xhtml",
            "OEBPS/text/chapter-0001-2.xhtml",
            "OEBPS/text/chapter-0001-3.xhtml",
        ]
        assert set(files) <= members
        assert "OEBPS/text/chapter-0001-4.xhtml" not in members

        nav = _parse(archive, "OEBPS/nav.xhtml")
        nav_hrefs = [link.get("href") for link in nav.iter(f"{XHTML}a")]
        assert nav_hrefs == ["text/chapter-0001.xhtml"]

        ncx = _parse(archive, "OEBPS/toc.ncx")
        ncx_srcs = [content.get("src") for content in ncx.iter(f"{NCX}content")]
        assert ncx_srcs == ["text/chapter-0001.xhtml"]

        package = _parse(archive, "OEBPS/content.opf")
        items = {
            item.get("id"): item for item in package.findall(f"{OPF}manifest/{OPF}item")
        }
        assert {"c0001", "c0001-2", "c0001-3"} <= set(items)
        spine = package.find(f"{OPF}spine")
        assert spine is not None
        refs = [itemref.get("idref") for itemref in spine.findall(f"{OPF}itemref")]
        assert refs == ["front", "c0001", "c0001-2", "c0001-3"]

        for index, name in enumerate(files):
            page = _parse(archive, name)
            page_paragraphs = page.findall(f".//{XHTML}p")
            assert [paragraph.text for paragraph in page_paragraphs] == [
                paragraphs[index]
            ]
            title_text = page.findtext(f".//{XHTML}title")
            if index == 0:
                assert title_text == "长章"
            else:
                assert title_text == "长章（续）"
                assert page.findtext(f".//{XHTML}h1") == "长章（续）"


def test_oversized_paragraph_is_kept_whole(tmp_path: Path) -> None:
    body = "x" * 300
    chapter = _node(
        _heading("chapter-1", HeadingKind.CHAPTER, "超长段"),
        body=[_source_line(1, body)],
    )
    output = tmp_path / "book.epub"
    write_epub(_result([chapter]), output, split_size=100)

    with zipfile.ZipFile(output) as archive:
        members = set(archive.namelist())
        chapter_files = {
            name for name in members if name.startswith("OEBPS/text/chapter-0001")
        }
        assert chapter_files == {"OEBPS/text/chapter-0001.xhtml"}

        page = _parse(archive, "OEBPS/text/chapter-0001.xhtml")
        paragraphs = page.findall(f".//{XHTML}p")
        assert [paragraph.text for paragraph in paragraphs] == [body]


@pytest.mark.parametrize(
    ("front_text", "expect_entry"),
    [("版权信息", True), ("", False)],
    ids=["present", "absent"],
)
def test_front_matter_toc_entry(
    tmp_path: Path, front_text: str, expect_entry: bool
) -> None:
    front_matter = [_source_line(1, front_text)] if front_text else []
    chapter = _node(
        _heading("chapter-1", HeadingKind.CHAPTER, "第一章"),
        body=[_source_line(2, "正文")],
    )
    result = _result([chapter], front_matter=front_matter)
    output = tmp_path / "book.epub"
    write_epub(result, output)

    with zipfile.ZipFile(output) as archive:
        members = set(archive.namelist())
        assert "OEBPS/text/front-matter.xhtml" in members

        front_page = _parse(archive, "OEBPS/text/front-matter.xhtml")
        assert front_page.findtext(f".//{XHTML}h1") == "前言"
        paragraphs = [
            paragraph.text for paragraph in front_page.findall(f".//{XHTML}p")
        ]
        assert paragraphs == ([front_text] if front_text else [])

        nav = _parse(archive, "OEBPS/nav.xhtml")
        nav_texts = [link.text for link in nav.iter(f"{XHTML}a")]
        assert ("前言" in nav_texts) is expect_entry
        nav_hrefs = [link.get("href") for link in nav.iter(f"{XHTML}a")]
        assert ("text/front-matter.xhtml" in nav_hrefs) is expect_entry

        ncx = _parse(archive, "OEBPS/toc.ncx")
        ncx_labels = [
            label.findtext(f"{NCX}text") for label in ncx.iter(f"{NCX}navLabel")
        ]
        assert ("前言" in ncx_labels) is expect_entry

        first_content = next(ncx.iter(f"{NCX}content"))
        if expect_entry:
            assert first_content.get("src") == "text/front-matter.xhtml"
        else:
            assert first_content.get("src") == "text/chapter-0001.xhtml"

        package = _parse(archive, "OEBPS/content.opf")
        spine = package.find(f"{OPF}spine")
        assert spine is not None
        refs = [itemref.get("idref") for itemref in spine.findall(f"{OPF}itemref")]
        assert refs[0] == "front"


def test_volume_and_special_share_part_counter(tmp_path: Path) -> None:
    chapter = _node(
        _heading("chapter-1", HeadingKind.CHAPTER, "第一章", level=2),
        body=[_source_line(2, "正文")],
    )
    extra = _node(
        _heading("chapter-2", HeadingKind.CHAPTER, "第二章", level=2),
        body=[_source_line(3, "正文")],
    )
    volume = _node(
        _heading("volume-1", HeadingKind.VOLUME, "第一卷"),
        children=[chapter],
    )
    special = _node(
        _heading("special-1", HeadingKind.SPECIAL, "番外"),
        children=[extra],
    )
    output = tmp_path / "book.epub"
    write_epub(_result([volume, special]), output)

    with zipfile.ZipFile(output) as archive:
        members = set(archive.namelist())
        assert "OEBPS/text/part-0001.xhtml" in members
        assert "OEBPS/text/part-0002.xhtml" in members
        assert "OEBPS/text/chapter-0001.xhtml" in members
        assert "OEBPS/text/chapter-0002.xhtml" in members


def test_invalid_xml_control_characters_are_removed(tmp_path: Path) -> None:
    node = _node(
        _heading("chapter-1", HeadingKind.CHAPTER, "第一章", level=1),
        body=[_source_line(2, "　　\x0b正文内容")],
    )
    output = tmp_path / "book.epub"
    write_epub(_result([node]), output)

    with zipfile.ZipFile(output) as archive:
        payload = archive.read("OEBPS/text/chapter-0001.xhtml").decode("utf-8")
        assert "\x0b" not in payload
        ET.fromstring(payload)
        assert "正文内容" in payload
