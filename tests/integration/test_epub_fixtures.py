from __future__ import annotations

import posixpath
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from txt2epub_cli.epub import write_epub
from txt2epub_cli.parser import parse_file

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "txt"
XHTML = "{http://www.w3.org/1999/xhtml}"
NCX = "{http://www.daisy.org/z3986/2005/ncx/}"


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.txt")), ids=lambda p: p.name)
def test_fixture_epub_structure(path: Path, tmp_path: Path):
    result = parse_file(path)
    output = tmp_path / f"{path.stem}.epub"
    write_epub(result, output)

    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        assert archive.namelist()[0] == "mimetype"
        assert archive.read("mimetype") == b"application/epub+zip"
        assert archive.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        assert archive.testzip() is None

        trees = {}
        for name in (
            n for n in names if n.endswith((".xml", ".opf", ".xhtml", ".ncx"))
        ):
            trees[name] = ET.fromstring(archive.read(name))

        nav = trees["OEBPS/nav.xhtml"]
        ncx = trees["OEBPS/toc.ncx"]
        nav_links = nav.findall(f".//{XHTML}nav//{XHTML}a")
        ncx_points = ncx.findall(f".//{NCX}navPoint")
        expected = len(result.walk_nodes()) + (1 if result.book.front_matter else 0)
        assert len(nav_links) == expected
        assert len(ncx_points) == expected

        for name in ("OEBPS/nav.xhtml", "OEBPS/toc.ncx", "OEBPS/content.opf"):
            for element in trees[name].iter():
                for attribute in ("href", "src"):
                    target = element.get(attribute)
                    if not target or target.startswith(
                        ("http:", "https:", "urn:", "data:")
                    ):
                        continue
                    resolved = posixpath.normpath(
                        posixpath.join(posixpath.dirname(name), target)
                    )
                    assert resolved in names, (name, target, resolved)

        spine = trees["OEBPS/content.opf"].findall(
            "{http://www.idpf.org/2007/opf}spine/{http://www.idpf.org/2007/opf}itemref"
        )
        assert spine[0].get("idref") == "front"


def test_fixture_epub_split(tmp_path: Path):
    from txt2epub_cli.parser import parse_text

    paragraph = "　　" + "占位正文。" * 20
    text = "第1章 占位标题\n" + "\n".join(paragraph for _ in range(5)) + "\n"
    result = parse_text(text)
    output = tmp_path / "split.epub"
    write_epub(result, output, split_size=512)

    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        fragments = [
            name for name in names if name.startswith("OEBPS/text/chapter-0001-")
        ]
        assert fragments
        nav = ET.fromstring(archive.read("OEBPS/nav.xhtml"))
        assert len(nav.findall(f".//{XHTML}nav//{XHTML}a")) == 1
