"""Shared data model for the TXT -> EPUB pipeline.

The central idea is a *line ledger*: every physical source line gets exactly one
disposition, so the converter can prove that no body text silently vanished.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Literal


class HeadingKind(StrEnum):
    VOLUME = "volume"
    CHAPTER = "chapter"
    SECTION = "section"
    SPECIAL = "special"


class Disposition(StrEnum):
    UNKNOWN = "unknown"
    BLANK = "blank"
    FRONT_MATTER = "front_matter"
    TOC_PAGE = "toc_page"
    HEADING = "heading"
    BODY = "body"
    NOISE = "noise"
    DUPLICATE = "duplicate"
    UNATTACHED = "unattached"


@dataclass(slots=True)
class SourceLine:
    """One physical line, normalized but preserving its original indent."""

    line_no: int
    raw: str
    text: str
    stripped: str
    indent: str
    normalized: str
    disposition: Disposition = Disposition.UNKNOWN
    reason: str = ""
    owner_id: str | None = None
    # Text units this line contributes to the coverage multiset. Filled in by
    # the parser once the final disposition is known.
    units: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Issue:
    severity: Literal["info", "warning", "error"]
    code: str
    line_no: int
    message: str
    detail: dict = field(default_factory=dict)


@dataclass(slots=True)
class Heading:
    id: str
    kind: HeadingKind
    level: int
    raw: str
    title: str
    number: str | None
    line_no: int
    confidence: float
    family: str = ""
    # Extra structured information, e.g. combined volume prefix.
    detail: dict = field(default_factory=dict)

    @property
    def display_title(self) -> str:
        return self.title.strip()


@dataclass
class Node:
    heading: Heading
    children: list[Node] = field(default_factory=list)
    body: list[SourceLine] = field(default_factory=list)
    parent: Node | None = field(default=None, repr=False)

    @property
    def id(self) -> str:
        return self.heading.id

    def walk(self) -> list[Node]:
        result = [self]
        for child in self.children:
            result.extend(child.walk())
        return result


@dataclass
class Book:
    source: Path
    title: str
    author: str | None = None
    language: str = "zh"
    description: str | None = None
    front_matter: list[SourceLine] = field(default_factory=list)
    cover: Path | None = None


@dataclass(slots=True)
class DecodedText:
    text: str
    encoding: str
    confidence: float
    errors: int
    used_fallback: bool
    had_bom: bool = False
    newline: str = "\n"


@dataclass
class Stats:
    lines: int = 0
    chars: int = 0
    non_empty: int = 0
    volumes: int = 0
    chapters: int = 0
    sections: int = 0
    specials: int = 0
    noise: int = 0
    duplicates: int = 0
    indented_duplicates: int = 0
    toc_pages: int = 0
    front_matter_lines: int = 0
    front_matter_chars: int = 0
    first_heading: Heading | None = None
    last_heading: Heading | None = None
    number_styles: dict[str, int] = field(default_factory=dict)
    duplicate_numbers: int = 0
    number_conflicts: int = 0
    number_gaps: int = 0
    number_resets: int = 0


@dataclass
class Coverage:
    source_chars: int = 0
    output_chars: int = 0
    dropped_chars: int = 0
    source_units: int = 0
    output_units: int = 0
    dropped_units: int = 0
    loss_ratio: float = 0.0
    ok: bool = True
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)


@dataclass
class ParseResult:
    book: Book
    roots: list[Node]
    ledger: list[SourceLine]
    issues: list[Issue]
    stats: Stats
    coverage: Coverage
    headings: list[Heading] = field(default_factory=list)
    encoding: DecodedText | None = None
    rules_name: str = "auto"
    keep_noise: bool = False
    keep_toc: bool = False

    def walk_nodes(self) -> list[Node]:
        result: list[Node] = []
        for root in self.roots:
            result.extend(root.walk())
        return result


class Txt2EpubError(Exception):
    """Base exception for user-facing conversion errors."""


class CoverageError(Txt2EpubError):
    def __init__(self, coverage: Coverage) -> None:
        self.coverage = coverage
        super().__init__(
            f"coverage mismatch: missing={len(coverage.missing)} extra={len(coverage.extra)}"
        )
