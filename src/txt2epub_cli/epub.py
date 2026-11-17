"""EPUB writer: EPUB 3 navigation plus an EPUB 2 NCX fallback.

The writer never mutates the :class:`~txt2epub_cli.model.ParseResult`.  Pages are
planned first so that the OPF, nav document, and NCX can all point at the exact
same member names.
"""

from __future__ import annotations

import importlib.resources
import string
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from txt2epub_cli.model import HeadingKind, Node, ParseResult, SourceLine

_MIMETYPE = b"application/epub+zip"
_XHTML_NS = "http://www.w3.org/1999/xhtml"
_XML_ENTITIES = {'"': "&quot;", "'": "&apos;"}
# Heading kind -> (filename family, manifest id prefix).  Volumes and specials
# share one counter and both use part-*.xhtml.
_FAMILIES: dict[HeadingKind, tuple[str, str]] = {
    HeadingKind.VOLUME: ("part", "p"),
    HeadingKind.SPECIAL: ("part", "p"),
    HeadingKind.CHAPTER: ("chapter", "c"),
    HeadingKind.SECTION: ("section", "s"),
}


@dataclass(slots=True)
class _Fragment:
    """One physical XHTML file belonging to a node."""

    zip_path: str
    href: str
    manifest_id: str
    title: str
    paragraphs: list[str]


@dataclass(slots=True)
class _NodePage:
    """All fragments generated for one node."""

    depth: int
    href: str
    fragments: list[_Fragment]


def _template(name: str) -> string.Template:
    text = (
        importlib.resources.files("txt2epub_cli")
        .joinpath("templates")
        .joinpath(name)
        .read_text(encoding="utf-8")
    )
    return string.Template(text)


def _xml_safe(value: str) -> str:
    """Drop characters that are not legal in XML 1.0."""

    return "".join(
        char
        for char in value
        if char in "\t\n\r"
        or 0x20 <= ord(char) <= 0xD7FF
        or 0xE000 <= ord(char) <= 0xFFFD
        or ord(char) >= 0x10000
    )


def _xml_escape(value: str) -> str:
    """Escape text for XML element content, including both quote characters."""

    return escape(_xml_safe(value), _XML_ENTITIES)


def _attr(value: str) -> str:
    """Return an XML attribute value with its surrounding quotes."""

    return quoteattr(value)


def _paragraph_texts(lines: list[SourceLine]) -> list[str]:
    """Return non-blank body lines, preserving their original indentation."""

    return [line.text for line in lines if line.text.strip()]


def _split_paragraphs(paragraphs: list[str], limit: int) -> list[list[str]]:
    """Greedily split paragraphs at boundaries, never inside a paragraph."""

    chunks: list[list[str]] = []
    current: list[str] = []
    size = 0
    for paragraph in paragraphs:
        paragraph_size = len(paragraph.encode("utf-8"))
        if current and size + paragraph_size > limit:
            chunks.append(current)
            current = []
            size = 0
        current.append(paragraph)
        size += paragraph_size
    chunks.append(current)
    return chunks


def _plan_pages(
    roots: list[Node], split_size: int
) -> tuple[list[_NodePage], dict[int, _NodePage]]:
    """Assign file names and manifest ids to every node in tree order."""

    counters = {"part": 0, "chapter": 0, "section": 0}
    pages: list[_NodePage] = []
    by_node: dict[int, _NodePage] = {}

    def visit(node: Node, depth: int) -> None:
        family, prefix = _FAMILIES.get(node.heading.kind, ("section", "s"))
        counters[family] += 1
        number = counters[family]
        stem = f"{family}-{number:04d}"
        display_title = node.heading.display_title
        chunks = _split_paragraphs(_paragraph_texts(node.body), split_size)
        fragments: list[_Fragment] = []
        for index, chunk in enumerate(chunks, start=1):
            if index == 1:
                file_stem = stem
                manifest_id = f"{prefix}{number:04d}"
                title = display_title
            else:
                file_stem = f"{stem}-{index}"
                manifest_id = f"{prefix}{number:04d}-{index}"
                title = f"{display_title}（续）"
            fragments.append(
                _Fragment(
                    zip_path=f"OEBPS/text/{file_stem}.xhtml",
                    href=f"text/{file_stem}.xhtml",
                    manifest_id=manifest_id,
                    title=title,
                    paragraphs=chunk,
                )
            )
        page = _NodePage(depth=depth, href=fragments[0].href, fragments=fragments)
        pages.append(page)
        by_node[id(node)] = page
        for child in node.children:
            visit(child, depth + 1)

    for root in roots:
        visit(root, 1)
    return pages, by_node


def _render_page(fragment: _Fragment, depth: int, language: str) -> str:
    heading_tag = f"h{min(max(depth, 1), 3)}"
    title = _xml_escape(fragment.title)
    language_attr = _attr(language)
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        "<!DOCTYPE html>",
        f'<html xmlns="{_XHTML_NS}" xml:lang={language_attr} lang={language_attr}>',
        "<head>",
        '  <meta charset="utf-8"/>',
        f"  <title>{title}</title>",
        '  <link rel="stylesheet" type="text/css" href="../style.css"/>',
        "</head>",
        "<body>",
        f"  <{heading_tag}>{title}</{heading_tag}>",
    ]
    lines.extend(
        f"  <p>{_xml_escape(paragraph)}</p>" for paragraph in fragment.paragraphs
    )
    lines.extend(["</body>", "</html>", ""])
    return "\n".join(lines)


def _render_nav_node(node: Node, pages: dict[int, _NodePage], indent: int) -> str:
    page = pages[id(node)]
    title = _xml_escape(node.heading.display_title)
    href = _attr(page.href)
    pad = "  " * indent
    if not node.children:
        return f"{pad}<li><a href={href}>{title}</a></li>"

    lines = [
        f"{pad}<li>",
        f"{pad}  <a href={href}>{title}</a>",
        f"{pad}  <ol>",
    ]
    lines.extend(_render_nav_node(child, pages, indent + 2) for child in node.children)
    lines.extend([f"{pad}  </ol>", f"{pad}</li>"])
    return "\n".join(lines)


def _render_toc(
    result: ParseResult, pages: dict[int, _NodePage], include_front: bool
) -> str:
    items: list[str] = []
    if include_front:
        items.append('      <li><a href="text/front-matter.xhtml">前言</a></li>')
    items.extend(_render_nav_node(root, pages, 3) for root in result.roots)
    return "\n".join(items)


def _render_ncx_nav_points(
    result: ParseResult, pages: dict[int, _NodePage], include_front: bool
) -> str:
    play_order = 0
    lines: list[str] = []

    if include_front:
        play_order += 1
        lines.extend(
            [
                f'    <navPoint id="navPoint-{play_order}" playOrder="{play_order}">',
                "      <navLabel>",
                "        <text>前言</text>",
                "      </navLabel>",
                '      <content src="text/front-matter.xhtml"/>',
                "    </navPoint>",
            ]
        )

    def add(node: Node, indent: int) -> None:
        nonlocal play_order
        play_order += 1
        page = pages[id(node)]
        pad = "  " * indent
        title = _xml_escape(node.heading.display_title)
        href = _attr(page.href)
        lines.extend(
            [
                f'{pad}<navPoint id="navPoint-{play_order}" playOrder="{play_order}">',
                f"{pad}  <navLabel>",
                f"{pad}    <text>{title}</text>",
                f"{pad}  </navLabel>",
                f"{pad}  <content src={href}/>",
            ]
        )
        for child in node.children:
            add(child, indent + 1)
        lines.append(f"{pad}</navPoint>")

    for root in result.roots:
        add(root, 2)
    return "\n".join(lines)


def _nav_depth(roots: list[Node], include_front: bool) -> int:
    def node_depth(node: Node) -> int:
        return 1 + max((node_depth(child) for child in node.children), default=0)

    tree_depth = max((node_depth(root) for root in roots), default=0)
    return max(1, tree_depth, 1 if include_front else 0)


def _render_manifest(pages: list[_NodePage]) -> str:
    lines = [
        '    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '    <item id="css" href="style.css" media-type="text/css"/>',
        '    <item id="front" href="text/front-matter.xhtml" media-type="application/xhtml+xml"/>',
    ]
    for page in pages:
        for fragment in page.fragments:
            lines.append(
                f'    <item id="{fragment.manifest_id}" href={_attr(fragment.href)} '
                'media-type="application/xhtml+xml"/>'
            )
    return "\n".join(lines)


def _render_spine(pages: list[_NodePage]) -> str:
    lines = ['    <itemref idref="front"/>']
    for page in pages:
        lines.extend(
            f'    <itemref idref="{fragment.manifest_id}"/>'
            for fragment in page.fragments
        )
    return "\n".join(lines)


def write_epub(
    result: ParseResult, output: Path, *, split_size: int = 256 * 1024
) -> Path:
    """Write *result* as an EPUB 3 file at *output* and return the output path."""

    if split_size <= 0:
        raise ValueError("split_size must be positive")

    output = Path(output)
    book = result.book
    language = book.language or "zh"
    identifier = f"urn:uuid:{uuid.uuid4()}"
    modified = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    include_front = bool(book.front_matter)

    pages, by_node = _plan_pages(result.roots, split_size)
    front_fragment = _Fragment(
        zip_path="OEBPS/text/front-matter.xhtml",
        href="text/front-matter.xhtml",
        manifest_id="front",
        title="前言",
        paragraphs=_paragraph_texts(book.front_matter),
    )

    container = _template("container.xml").substitute()
    creator_item = (
        f"\n    <dc:creator>{_xml_escape(book.author)}</dc:creator>"
        if book.author is not None
        else ""
    )
    description_item = (
        f"\n    <dc:description>{_xml_escape(book.description)}</dc:description>"
        if book.description is not None
        else ""
    )
    opf = _template("content.opf").substitute(
        language=_xml_escape(language),
        identifier=_xml_escape(identifier),
        title=_xml_escape(book.title),
        creator_item=creator_item,
        description_item=description_item,
        modified=modified,
        manifest=_render_manifest(pages),
        spine=_render_spine(pages),
    )
    nav = _template("nav.xhtml").substitute(
        language=_xml_escape(language),
        title=_xml_escape(book.title),
        toc=_render_toc(result, by_node, include_front),
    )
    ncx = _template("toc.ncx").substitute(
        language=_xml_escape(language),
        identifier=_xml_escape(identifier),
        title=_xml_escape(book.title),
        depth=str(_nav_depth(result.roots, include_front)),
        nav_points=_render_ncx_nav_points(result, by_node, include_front),
    )
    style = _template("style.css").substitute()

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        mimetype_info = zipfile.ZipInfo("mimetype")
        mimetype_info.compress_type = zipfile.ZIP_STORED
        mimetype_info.date_time = (1980, 1, 1, 0, 0, 0)
        archive.writestr(mimetype_info, _MIMETYPE)

        entries = [
            ("META-INF/container.xml", container),
            ("OEBPS/content.opf", opf),
            ("OEBPS/nav.xhtml", nav),
            ("OEBPS/toc.ncx", ncx),
            ("OEBPS/style.css", style),
        ]
        for name, text in entries:
            archive.writestr(
                name, text.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED
            )

        archive.writestr(
            front_fragment.zip_path,
            _render_page(front_fragment, 1, language).encode("utf-8"),
            compress_type=zipfile.ZIP_DEFLATED,
        )
        for page in pages:
            for fragment in page.fragments:
                archive.writestr(
                    fragment.zip_path,
                    _render_page(fragment, page.depth, language).encode("utf-8"),
                    compress_type=zipfile.ZIP_DEFLATED,
                )
    return output


def build_epub(
    result: ParseResult, output: Path, *, split_size: int = 256 * 1024
) -> Path:
    """Alias for :func:`write_epub`."""

    return write_epub(result, output, split_size=split_size)
