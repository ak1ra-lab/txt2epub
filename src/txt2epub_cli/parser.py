"""Main parsing pipeline: encoding -> ledger -> candidates -> tree -> coverage."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

from txt2epub_cli.candidates import Candidate, detect_candidate
from txt2epub_cli.coverage import compute_coverage
from txt2epub_cli.dedupe import (
    check_number_sequence,
    dedupe_chapters,
    dedupe_numbers,
    number_style,
    parse_number,
)
from txt2epub_cli.encoding import decode_bytes, read_text_file
from txt2epub_cli.hierarchy import build_tree, flatten
from txt2epub_cli.ledger import LineLedger
from txt2epub_cli.model import (
    Book,
    DecodedText,
    Disposition,
    Heading,
    HeadingKind,
    Issue,
    Node,
    ParseResult,
    SourceLine,
    Stats,
)
from txt2epub_cli.noise import noise_reason
from txt2epub_cli.normalize import (
    make_source_lines,
    normalize_for_match,
    normalize_text,
    strip_heading_decoration,
)
from txt2epub_cli.rules import RuleSet, builtin_ruleset
from txt2epub_cli.toc import detect_toc_lines

_TOO_LONG = "too_long"


def number_key(raw: str | None) -> str:
    if raw is None:
        return ""
    value = parse_number(raw)
    return str(value) if value is not None else raw.strip()


def _too_long(candidate: Candidate) -> bool:
    return any(issue.code == _TOO_LONG for issue in candidate.issues)


def _looks_like_sentence(text: str) -> bool:
    return any(ch in text for ch in "。！？；，、：:“”‘’…")


class _Parser:
    def __init__(
        self,
        decoded: DecodedText,
        source: Path,
        *,
        rules: RuleSet,
        keep_noise: bool,
        keep_toc: bool,
        dedupe: str,
    ) -> None:
        self.decoded = decoded
        self.source = source
        self.rules = rules
        self.keep_noise = keep_noise
        self.keep_toc = keep_toc
        self.dedupe_mode = dedupe

        self.lines = make_source_lines(decoded.text)
        self.ledger = LineLedger(self.lines)
        self.candidates: dict[int, Candidate] = {}
        self.issues: list[Issue] = []
        self.headings: list[Heading] = []
        self.heading_seq = 0
        self.toc_lines: set[int] = set()

        self.current_volume_id: str | None = None
        self.current_volume_key: str | None = None
        self.current_container_id: str | None = None
        self.current_container_key: str | None = None
        self.registry: dict[tuple[str, str], list[Heading]] = defaultdict(list)
        self.column_zero_registry: dict[tuple[str, str], str] = {}
        self.has_column_zero_chapters = False
        self.first_heading_line: int | None = None

    # ------------------------------------------------------------------ helpers
    def _container_key(self) -> str:
        if self.current_volume_key:
            return f"V:{self.current_volume_key}"
        if self.current_container_key:
            return f"S:{self.current_container_key}"
        return ""

    def _add_heading(
        self,
        line: SourceLine,
        kind: HeadingKind,
        title: str,
        number: str | None,
        family: str,
        confidence: float,
        detail: dict | None = None,
    ) -> Heading:
        self.heading_seq += 1
        heading = Heading(
            id=f"h{self.heading_seq:05d}",
            kind=kind,
            level=1,
            raw=line.raw,
            title=title.strip(),
            number=number,
            line_no=line.line_no,
            confidence=confidence,
            family=family,
            detail=dict(detail or {}),
        )
        self.headings.append(heading)
        return heading

    def _register_chapter(self, heading: Heading) -> None:
        key = (self._container_key(), number_key(heading.number))
        self.registry[key].append(heading)

    def _near_chapter(self, line: SourceLine, limit: int = 10) -> bool:
        seen = 0
        for following in self.lines[line.line_no :]:
            if not following.stripped:
                continue
            seen += 1
            if seen > limit:
                return False
            candidate = self.candidates.get(following.line_no)
            if candidate is None:
                continue
            if _too_long(candidate):
                continue
            if candidate.kind == HeadingKind.CHAPTER:
                return True
            if candidate.kind in (HeadingKind.VOLUME, HeadingKind.SPECIAL):
                return False
        return False

    def _matched_text(self, line: SourceLine) -> str:
        return normalize_text(strip_heading_decoration(line.stripped)).strip()

    # ------------------------------------------------------------- classification
    def _prepare(self) -> None:
        stats = Stats(
            lines=len(self.lines),
            chars=sum(len(line.text) for line in self.lines),
            non_empty=sum(1 for line in self.lines if line.stripped),
        )
        self.stats = stats

        for line in self.lines:
            if not line.stripped:
                self.ledger.mark(line.line_no, Disposition.BLANK)
                continue
            candidate = detect_candidate(line, self.rules)
            if candidate is not None:
                self.candidates[line.line_no] = candidate

        def is_heading_like(line: SourceLine) -> bool:
            candidate = self.candidates.get(line.line_no)
            if candidate is None or _too_long(candidate):
                return False
            return not (candidate.deferred and not self.rules.allow_indented_headings)

        self.toc_lines = detect_toc_lines(self.lines, self.rules, is_heading_like)
        if self.toc_lines:
            if self.keep_toc:
                for line_no in self.toc_lines:
                    self.ledger.mark(line_no, Disposition.FRONT_MATTER, "toc_kept")
                self.issues.append(
                    Issue(
                        severity="info",
                        code="toc_kept",
                        line_no=min(self.toc_lines),
                        message=f"kept {len(self.toc_lines)} embedded TOC lines as front matter",
                    )
                )
            else:
                for line_no in self.toc_lines:
                    self.ledger.mark(line_no, Disposition.TOC_PAGE, "embedded_toc")
                self.issues.append(
                    Issue(
                        severity="info",
                        code="toc_page_removed",
                        line_no=min(self.toc_lines),
                        message=f"removed {len(self.toc_lines)} embedded TOC lines",
                    )
                )
        self._precompute_column_zero_registry()

    def _precompute_column_zero_registry(self) -> None:
        """Remember column-zero chapter numbers per container.

        Indented candidates are resolved in source order, but the clean
        column-zero heading for the same chapter may appear later (or use a
        different numeral style).  A pre-pass makes the duplicate decision
        independent of that order.
        """

        token = ""
        for line in self.lines:
            if line.disposition is not Disposition.UNKNOWN:
                continue
            candidate = self.candidates.get(line.line_no)
            if candidate is None or _too_long(candidate):
                continue
            text = self._matched_text(line)
            if candidate.detail.get("combined"):
                volume_raw = str(candidate.detail.get("volume_raw") or "")
                token = f"V:{normalize_for_match(volume_raw)}"
                if not candidate.deferred and candidate.number:
                    key = (token, number_key(candidate.number))
                    self.column_zero_registry.setdefault(key, normalize_for_match(text))
            elif candidate.kind == HeadingKind.VOLUME:
                volume_title, _ = self._split_volume_suffix(candidate, line, text)
                token = f"V:{normalize_for_match(volume_title)}"
            elif candidate.kind == HeadingKind.SPECIAL:
                if self._special_is_container(text):
                    token = f"S:{normalize_for_match(text)}"
            elif (
                candidate.kind == HeadingKind.CHAPTER
                and not candidate.deferred
                and candidate.number
            ):
                key = (token, number_key(candidate.number))
                self.column_zero_registry.setdefault(key, normalize_for_match(text))
                self.has_column_zero_chapters = True

    def _adjacent_heading(self, line: SourceLine) -> bool:
        """Return whether the nearest non-blank line on either side is a heading."""

        cursor = line.line_no - 2
        while cursor >= 0:
            previous = self.lines[cursor]
            if previous.stripped:
                if previous.disposition is Disposition.HEADING:
                    return True
                candidate = self.candidates.get(previous.line_no)
                return bool(
                    candidate is not None
                    and not _too_long(candidate)
                    and candidate.kind
                    in (HeadingKind.VOLUME, HeadingKind.CHAPTER, HeadingKind.SPECIAL)
                )
            cursor -= 1
        return False

    # ------------------------------------------------------------------ acceptance
    def _accept_combined(
        self, candidate: Candidate, line: SourceLine, text: str
    ) -> list[Heading]:
        volume_raw = str(candidate.detail.get("volume_raw") or "").strip()
        volume_key = normalize_for_match(volume_raw)
        created: list[Heading] = []
        if volume_raw and volume_key != self.current_volume_key:
            volume = self._add_heading(
                line,
                HeadingKind.VOLUME,
                volume_raw,
                str(candidate.detail.get("volume_number") or ""),
                "combined_prefix",
                candidate.confidence,
                {"combined": True},
            )
            self.current_volume_id = volume.id
            self.current_volume_key = volume_key
            self.current_container_id = None
            self.current_container_key = None
            created.append(volume)

        chapter_title = text
        if volume_raw and text.startswith(volume_raw):
            chapter_title = text[len(volume_raw) :].strip() or text
        chapter = self._add_heading(
            line,
            HeadingKind.CHAPTER,
            chapter_title,
            candidate.number,
            candidate.family,
            candidate.confidence,
            dict(candidate.detail),
        )
        self._register_chapter(chapter)
        created.append(chapter)
        return created

    def _split_volume_suffix(
        self, candidate: Candidate, line: SourceLine, text: str
    ) -> tuple[str, str | None]:
        title = candidate.title.strip()
        if not title:
            return text, None
        parts = title.rsplit(None, 1)
        if len(parts) != 2:
            return text, None
        suffix = parts[1]
        if not (1 <= len(suffix) <= 4):
            return text, None
        if suffix[-1] not in self.rules.volume_suffix_special_suffixes:
            return text, None
        # 序/章/篇 are strong section markers (e.g. 魔序, 卷首序) and may be
        # followed by body text.  传/记/录 are weaker and only split when a
        # chapter follows, to avoid eating ordinary volume names.
        if suffix[-1] not in {"序", "章", "篇"} and not self._near_chapter(line):
            return text, None
        position = text.rfind(suffix)
        volume_title = text[:position].strip() if position > 0 else text
        return volume_title or text, suffix

    def _accept_volume(
        self, candidate: Candidate, line: SourceLine, text: str
    ) -> list[Heading]:
        volume_title, suffix = self._split_volume_suffix(candidate, line, text)
        volume = self._add_heading(
            line,
            HeadingKind.VOLUME,
            volume_title,
            candidate.number,
            candidate.family,
            candidate.confidence,
            {"unit": candidate.detail.get("unit", "")},
        )
        self.current_volume_id = volume.id
        self.current_volume_key = normalize_for_match(volume_title)
        self.current_container_id = None
        self.current_container_key = None
        created = [volume]
        if suffix:
            special = self._add_heading(
                line,
                HeadingKind.SPECIAL,
                suffix,
                None,
                "volume_suffix_special",
                0.8,
                {"in_volume": True},
            )
            created.append(special)
        return created

    def _special_is_container(self, title: str) -> bool:
        return title.startswith(("前传", "番外", "外传")) or (
            "外传" in title and title.find("外传") <= 2
        )

    def _accept_special(
        self, candidate: Candidate, line: SourceLine, text: str
    ) -> list[Heading]:
        title = text or candidate.title
        is_container = self._special_is_container(title)
        heading = self._add_heading(
            line,
            HeadingKind.SPECIAL,
            title,
            None,
            candidate.family,
            candidate.confidence,
            {"container": is_container},
        )
        if is_container:
            self.current_container_id = heading.id
            self.current_container_key = normalize_for_match(title)
            self.current_volume_id = None
            self.current_volume_key = None
        return [heading]

    def _accept_chapter(
        self, candidate: Candidate, line: SourceLine, text: str
    ) -> list[Heading]:
        number = candidate.number
        number2 = candidate.detail.get("number2")
        if number and number2:
            # Preserve both endpoints so sequence checks know the span's end.
            number = f"{number}—{number2}"
        heading = self._add_heading(
            line,
            HeadingKind.CHAPTER,
            text or candidate.title,
            number,
            candidate.family,
            candidate.confidence,
            dict(candidate.detail),
        )
        self._register_chapter(heading)
        return [heading]

    def _accept_section(
        self, candidate: Candidate, line: SourceLine, text: str
    ) -> list[Heading]:
        return [
            self._add_heading(
                line,
                HeadingKind.SECTION,
                text or candidate.title,
                candidate.number,
                candidate.family,
                candidate.confidence,
                dict(candidate.detail),
            )
        ]

    def _accept(self, candidate: Candidate, line: SourceLine) -> list[Heading]:
        text = self._matched_text(line)
        if candidate.detail.get("combined"):
            return self._accept_combined(candidate, line, text)
        if candidate.kind == HeadingKind.VOLUME:
            return self._accept_volume(candidate, line, text)
        if candidate.kind == HeadingKind.SPECIAL:
            return self._accept_special(candidate, line, text)
        if candidate.kind == HeadingKind.CHAPTER:
            return self._accept_chapter(candidate, line, text)
        if candidate.kind == HeadingKind.SECTION:
            return self._accept_section(candidate, line, text)
        return []

    def _reject_indented(self, candidate: Candidate, line: SourceLine) -> bool:
        if not candidate.deferred:
            return False
        if not self.rules.allow_indented_headings:
            self.ledger.mark(line.line_no, Disposition.BODY, "indented_rejected")
            self.issues.append(
                Issue(
                    severity="info",
                    code="indented_rejected",
                    line_no=line.line_no,
                    message="indented heading candidate rejected by rules",
                )
            )
            return True
        text = self._matched_text(line)
        if candidate.kind == HeadingKind.VOLUME:
            short_enough = len(text) <= self.rules.max_indented_volume_length
            if not (short_enough and self._near_chapter(line)):
                self.ledger.mark(
                    line.line_no, Disposition.BODY, "indented_volume_rejected"
                )
                self.issues.append(
                    Issue(
                        severity="info",
                        code="indented_volume_rejected",
                        line_no=line.line_no,
                        message="short indented volume candidate not followed by a chapter",
                    )
                )
                return True
        if candidate.kind == HeadingKind.SPECIAL and (
            len(text) > 30
            or (_looks_like_sentence(text) and not text.endswith(("完本感言", "外传")))
        ):
            self.ledger.mark(
                line.line_no, Disposition.BODY, "indented_special_rejected"
            )
            return True
        if candidate.kind == HeadingKind.CHAPTER and candidate.number:
            key = (self._container_key(), number_key(candidate.number))
            existing = self.registry.get(key, [])
            column_zero_title = self.column_zero_registry.get(key)
            if existing or column_zero_title is not None:
                title = normalize_for_match(text)
                same = any(
                    normalize_for_match(heading.title) == title for heading in existing
                ) or (column_zero_title is not None and column_zero_title == title)
                reason = (
                    "duplicate_number_same_title"
                    if same
                    else "duplicate_number_indented"
                )
                self.ledger.mark(line.line_no, Disposition.DUPLICATE, reason)
                self.issues.append(
                    Issue(
                        severity="info",
                        code="duplicate_indented",
                        line_no=line.line_no,
                        message=(
                            f"indented chapter {candidate.number!r} already exists at "
                            "column zero in this container; heading line dropped"
                        ),
                    )
                )
                return True
            if self.has_column_zero_chapters and not self._adjacent_heading(line):
                # In mixed-format books, a lone indented "第X章..." sentence in
                # the middle of a paragraph is almost always narrative text.
                self.ledger.mark(line.line_no, Disposition.BODY, "indented_unconfirmed")
                self.issues.append(
                    Issue(
                        severity="info",
                        code="indented_unconfirmed",
                        line_no=line.line_no,
                        message=(
                            "indented chapter candidate has no adjacent heading; kept as body"
                        ),
                    )
                )
                return True
        return False

    def _record_noise(self, line: SourceLine, reason: str, message: str) -> None:
        self.ledger.mark(line.line_no, Disposition.NOISE, f"noise:{reason}")
        self.issues.append(
            Issue(
                severity="info",
                code="noise_removed",
                line_no=line.line_no,
                message=message,
                detail={"pattern": reason},
            )
        )

    def _run_acceptance(self) -> None:
        for line in self.lines:
            if line.disposition is not Disposition.UNKNOWN:
                continue
            candidate = self.candidates.get(line.line_no)
            if candidate is not None and _too_long(candidate):
                self.ledger.mark(line.line_no, Disposition.BODY, "too_long")
                self.issues.append(
                    Issue(
                        severity="warning",
                        code=_TOO_LONG,
                        line_no=line.line_no,
                        message="heading-like line exceeds max_heading_length; kept as body",
                    )
                )
                candidate = None

            if candidate is None:
                reason = noise_reason(line, self.rules)
                if reason is not None and not self.keep_noise:
                    self._record_noise(line, reason, "short site noise line removed")
                continue

            if candidate.deferred:
                reason = noise_reason(line, self.rules)
                if reason is not None:
                    if self.keep_noise:
                        self.ledger.mark(line.line_no, Disposition.BODY, "noise_kept")
                    else:
                        self._record_noise(
                            line, reason, "noisy indented heading candidate removed"
                        )
                    continue
                if self._reject_indented(candidate, line):
                    continue

            if candidate.kind == HeadingKind.VOLUME:
                text = self._matched_text(line)
                volume_title, _ = self._split_volume_suffix(candidate, line, text)
                volume_key = normalize_for_match(volume_title)
                if volume_key and volume_key == self.current_volume_key:
                    self.ledger.mark(
                        line.line_no, Disposition.DUPLICATE, "duplicate_volume"
                    )
                    self.issues.append(
                        Issue(
                            severity="info",
                            code="duplicate_volume",
                            line_no=line.line_no,
                            message="duplicate volume heading merged with the current volume",
                        )
                    )
                    continue

            created = self._accept(candidate, line)
            if not created:
                continue
            self.ledger.mark(
                line.line_no,
                Disposition.HEADING,
                created[-1].family,
                created[-1].id,
            )
            if self.first_heading_line is None:
                self.first_heading_line = line.line_no

    # --------------------------------------------------------------- body / tree
    def _attach_bodies(self, line_targets: dict[int, Node]) -> Book:
        book = Book(source=self.source, title=self.source.stem)
        target: Node | None = None
        for line in self.lines:
            node = line_targets.get(line.line_no)
            if node is not None:
                target = node

            if line.disposition is Disposition.FRONT_MATTER:
                book.front_matter.append(line)
                continue
            if line.disposition not in (Disposition.UNKNOWN, Disposition.BODY):
                continue

            before_first = (
                self.first_heading_line is None
                or line.line_no < self.first_heading_line
            )
            if before_first:
                line.disposition = Disposition.FRONT_MATTER
                line.reason = line.reason or "before_first_heading"
                book.front_matter.append(line)
            elif target is not None:
                line.disposition = Disposition.BODY
                line.reason = line.reason or "body"
                line.owner_id = target.id
                target.body.append(line)
            else:
                line.disposition = Disposition.UNATTACHED
                self.issues.append(
                    Issue(
                        severity="warning",
                        code="unattached_body",
                        line_no=line.line_no,
                        message=(
                            "body line could not be attached to a heading; kept in front matter"
                        ),
                    )
                )
                book.front_matter.append(line)

        return book

    # ------------------------------------------------------------------ metadata
    def _metadata(self, book: Book) -> None:
        stem = self.source.stem
        title: str | None = None
        author: str | None = None

        match = re.search(r"《(?P<title>[^》]+)》", stem)
        if match:
            title = match.group("title").strip()
        match = re.search(r"作者[:：]\s*(?P<author>[^（(]+)", stem)
        if match:
            author = match.group("author").strip()

        parts = stem.split("_")
        second = parts[1].strip() if len(parts) >= 2 else ""
        second_is_name = bool(re.fullmatch(r"[\u4e00-\u9fff]{2,4}", second))

        if title is None:
            title = parts[0].strip() if second_is_name else stem
        if author is None and second_is_name:
            author = second

        title = re.sub(r"（[^）]*）|\([^)]*\)", "", title or "").strip() or stem
        title = re.sub(r"\s+作者[:：].*$", "", title).strip() or stem
        title = re.sub(r"_ch\d+$", "", title).strip() or stem

        description_lines: list[str] = []
        collecting = False
        scan_limit = self.first_heading_line or 200
        for line in self.lines:
            if line.line_no > scan_limit:
                break
            if not line.stripped:
                if collecting and description_lines:
                    collecting = False
                continue
            text = line.stripped
            intro = re.match(r"^内容简介[:：]?\s*(?P<rest>.*)$", text)
            if re.match(r"^(书名|作品名)[:：]", text):
                title = re.sub(r"^(书名|作品名)[:：]\s*", "", text).strip() or title
            elif re.match(r"^作者[:：]", text):
                author = re.sub(r"^作者[:：]\s*", "", text).strip() or author
            elif re.match(r"^《[^》]+》$", text) and len(text) <= 60:
                title = text[1:-1].strip() or title
            elif intro:
                collecting = True
                rest = intro.group("rest").strip()
                if rest:
                    description_lines.append(rest)
            elif collecting and line.disposition is Disposition.HEADING:
                collecting = False
            elif collecting:
                description_lines.append(text)
                if len("\n".join(description_lines)) > 1200:
                    collecting = False
            else:
                match = re.match(r"^(?P<title>.+?)\s+作者[:：]\s*(?P<author>.+)$", text)
                if match:
                    title = match.group("title").strip() or title
                    author = match.group("author").strip() or author
                elif author is None:
                    match = re.search(r"作者[:：]\s*(?P<author>[^』\s]+)", text)
                    if match:
                        author = match.group("author").strip()

        book.title = title
        book.author = author
        book.description = "\n".join(description_lines)[:1500] or None

    # ------------------------------------------------------------------ finalize
    def _finalize(self, roots: list[Node], book: Book) -> ParseResult:
        line_heading_counts = Counter(heading.line_no for heading in self.headings)
        multi_heading_lines = {
            line_no for line_no, count in line_heading_counts.items() if count > 1
        }
        dedupe_numbers(
            roots,
            self.lines,
            self.issues,
            multi_heading_lines=multi_heading_lines,
        )
        sequence_counts = check_number_sequence(roots, self.issues)
        dedupe_chapters(
            roots,
            self.lines,
            self.issues,
            mode=self.dedupe_mode,
            skip_lines=multi_heading_lines,
        )

        present = flatten(roots)
        headings = [node.heading for node in present]
        kind_counts = Counter(heading.kind for heading in headings)
        issue_counts = Counter(issue.code for issue in self.issues)
        disposition_counts = self.ledger.counts()

        stats = self.stats
        stats.volumes = kind_counts[HeadingKind.VOLUME]
        stats.chapters = kind_counts[HeadingKind.CHAPTER]
        stats.sections = kind_counts[HeadingKind.SECTION]
        stats.specials = kind_counts[HeadingKind.SPECIAL]
        stats.noise = disposition_counts.get(Disposition.NOISE, 0)
        stats.indented_duplicates = issue_counts["duplicate_indented"]
        stats.duplicates = issue_counts["duplicate_number"] + stats.indented_duplicates
        stats.toc_pages = len(self.toc_lines)
        stats.front_matter_lines = len(book.front_matter)
        stats.front_matter_chars = sum(len(line.text) for line in book.front_matter)
        stats.first_heading = headings[0] if headings else None
        stats.last_heading = headings[-1] if headings else None
        stats.number_styles = dict(
            Counter(
                number_style(heading.number)
                for heading in headings
                if heading.kind is HeadingKind.CHAPTER
            )
        )
        stats.duplicate_numbers = issue_counts["duplicate_number"]
        stats.number_conflicts = issue_counts["number_conflict"]
        stats.number_gaps = sequence_counts["gaps"]
        stats.number_resets = sequence_counts["resets"]

        self.issues.sort(key=lambda issue: issue.line_no)
        coverage = compute_coverage(book, roots, self.lines, self.headings)
        if not coverage.ok:
            self.issues.append(
                Issue(
                    severity="error",
                    code="coverage_mismatch",
                    line_no=0,
                    message=(
                        "coverage multiset mismatch: "
                        f"{len(coverage.missing)} missing, {len(coverage.extra)} extra"
                    ),
                    detail={
                        "missing": coverage.missing[:20],
                        "extra": coverage.extra[:20],
                    },
                )
            )
        return ParseResult(
            book=book,
            roots=roots,
            ledger=self.lines,
            issues=self.issues,
            stats=stats,
            coverage=coverage,
            headings=self.headings,
            encoding=self.decoded,
            rules_name=self.rules.name,
            keep_noise=self.keep_noise,
            keep_toc=self.keep_toc,
        )

    def run(self) -> ParseResult:
        self._prepare()
        self._run_acceptance()
        roots, line_targets = build_tree(self.headings)
        book = self._attach_bodies(line_targets)
        self._metadata(book)
        return self._finalize(roots, book)


# --------------------------------------------------------------------- public API
def parse_bytes(
    data: bytes,
    *,
    source: Path = Path("book.txt"),
    rules: RuleSet | None = None,
    forced_encoding: str | None = None,
    keep_noise: bool = False,
    keep_toc: bool = False,
    dedupe: str = "off",
) -> ParseResult:
    decoded = decode_bytes(data, forced_encoding=forced_encoding)
    return _Parser(
        decoded,
        source,
        rules=rules or builtin_ruleset("auto"),
        keep_noise=keep_noise,
        keep_toc=keep_toc,
        dedupe=dedupe,
    ).run()


def parse_text(
    text: str,
    *,
    source: Path = Path("book.txt"),
    rules: RuleSet | None = None,
    encoding_name: str = "utf-8",
    keep_noise: bool = False,
    keep_toc: bool = False,
    dedupe: str = "off",
) -> ParseResult:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    decoded = DecodedText(
        text=normalized,
        encoding=encoding_name,
        confidence=1.0,
        errors=0,
        used_fallback=False,
    )
    return _Parser(
        decoded,
        source,
        rules=rules or builtin_ruleset("auto"),
        keep_noise=keep_noise,
        keep_toc=keep_toc,
        dedupe=dedupe,
    ).run()


def parse_file(
    path: Path,
    *,
    rules: RuleSet | None = None,
    forced_encoding: str | None = None,
    keep_noise: bool = False,
    keep_toc: bool = False,
    dedupe: str = "off",
) -> ParseResult:
    decoded = read_text_file(path, forced_encoding=forced_encoding)
    return _Parser(
        decoded,
        path,
        rules=rules or builtin_ruleset("auto"),
        keep_noise=keep_noise,
        keep_toc=keep_toc,
        dedupe=dedupe,
    ).run()
