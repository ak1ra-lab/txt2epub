"""Human-readable and JSON reports for inspect / convert."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from txt2epub_cli.model import Issue, ParseResult


def _heading_dict(heading) -> dict | None:
    if heading is None:
        return None
    return {
        "line": heading.line_no,
        "title": heading.title,
        "kind": str(heading.kind),
        "level": heading.level,
    }


def _issue_dict(issue: Issue) -> dict:
    data = {
        "severity": issue.severity,
        "code": issue.code,
        "line": issue.line_no,
        "message": issue.message,
    }
    if issue.detail:
        data["detail"] = issue.detail
    return data


def report_dict(result: ParseResult, output: Path | None = None) -> dict:
    stats = result.stats
    coverage = result.coverage
    encoding = result.encoding
    data = {
        "schema_version": 1,
        "file": str(result.book.source),
        "title": result.book.title,
        "author": result.book.author,
        "rules": result.rules_name,
        "encoding": {
            "name": encoding.encoding if encoding else "unknown",
            "confidence": encoding.confidence if encoding else 0.0,
            "errors": encoding.errors if encoding else 0,
            "used_fallback": encoding.used_fallback if encoding else False,
        },
        "stats": {
            "lines": stats.lines,
            "chars": stats.chars,
            "non_empty": stats.non_empty,
            "volumes": stats.volumes,
            "chapters": stats.chapters,
            "sections": stats.sections,
            "specials": stats.specials,
            "noise": stats.noise,
            "duplicates": stats.duplicates,
            "indented_duplicates": stats.indented_duplicates,
            "toc_pages": stats.toc_pages,
            "front_matter_lines": stats.front_matter_lines,
            "number_styles": stats.number_styles,
            "number_gaps": stats.number_gaps,
            "number_conflicts": stats.number_conflicts,
            "number_resets": stats.number_resets,
        },
        "first_heading": _heading_dict(stats.first_heading),
        "last_heading": _heading_dict(stats.last_heading),
        "issues": [_issue_dict(issue) for issue in result.issues],
        "coverage": {
            "source_chars": coverage.source_chars,
            "output_chars": coverage.output_chars,
            "dropped_chars": coverage.dropped_chars,
            "loss_ratio": coverage.loss_ratio,
            "ok": coverage.ok,
            "source_units": coverage.source_units,
            "output_units": coverage.output_units,
            "dropped_units": coverage.dropped_units,
            "missing_sample": coverage.missing,
            "extra_sample": coverage.extra,
        },
    }
    if output is not None:
        data["output"] = str(output)
    return data


def report_json(result: ParseResult, output: Path | None = None) -> str:
    return json.dumps(report_dict(result, output), ensure_ascii=False, indent=2)


def report_human(
    result: ParseResult,
    *,
    limit: int = 10,
    output: Path | None = None,
    ignore_codes: set[str] | None = None,
    only_codes: set[str] | None = None,
) -> str:
    stats = result.stats
    coverage = result.coverage
    encoding = result.encoding
    lines = [
        f"File:       {result.book.source}",
        (
            f"Title:      {result.book.title}"
            + (f" / {result.book.author}" if result.book.author else "")
        ),
        (
            f"Encoding:   {encoding.encoding} "
            f"({'fallback' if encoding.used_fallback else 'strict'}, "
            f"{encoding.errors} errors)"
            if encoding
            else "Encoding:   unknown"
        ),
        f"Lines:      {stats.lines:,} (non-empty {stats.non_empty:,})",
        f"Chars:      {stats.chars:,}",
        (
            f"Front:      {stats.front_matter_lines:,} lines / {stats.front_matter_chars:,} chars"
        ),
        (
            f"Headings:   {stats.volumes:,} volumes, {stats.chapters:,} chapters, "
            f"{stats.sections:,} sections, {stats.specials:,} specials"
        ),
    ]
    if stats.first_heading:
        first = stats.first_heading
        lines.append(f"First:      [{first.line_no}] {first.title}")
    if stats.last_heading:
        last = stats.last_heading
        lines.append(f"Last:       [{last.line_no}] {last.title}")
    lines.append(
        f"Issues:     {stats.duplicate_numbers:,} duplicate chapters, "
        f"{stats.indented_duplicates:,} indented duplicates, "
        f"{stats.number_conflicts:,} conflicts, {stats.number_gaps:,} gaps, "
        f"{stats.noise:,} noise lines, {stats.toc_pages:,} toc lines"
    )
    percent = 100.0 * (1.0 - coverage.loss_ratio) if coverage.source_chars else 100.0
    lines.append(
        f"Coverage:   {percent:.2f}% (source {coverage.source_chars:,} / "
        f"output {coverage.output_chars:,} / dropped {coverage.dropped_chars:,})"
        + ("" if coverage.ok else "  [MISMATCH]")
    )
    if output is not None:
        lines.append(f"Output:     {output}")

    if only_codes:
        warnings = [issue for issue in result.issues if issue.code in only_codes]
    else:
        warnings = [
            issue for issue in result.issues if issue.severity in ("warning", "error")
        ]
    if ignore_codes:
        warnings = [issue for issue in warnings if issue.code not in ignore_codes]

    if warnings and limit > 0:
        by_code = Counter(issue.code for issue in warnings)
        summary = ", ".join(f"{code}={count}" for code, count in by_code.most_common())
        lines.append("")
        lines.append(f"Suspicious: {summary}")
        for issue in warnings[:limit]:
            lines.append(
                f"  [{issue.line_no}] {issue.severity}: {issue.code}: {issue.message}"
            )
        if len(warnings) > limit:
            lines.append(f"  ... {len(warnings) - limit} more (see --json)")
    return "\n".join(lines)
