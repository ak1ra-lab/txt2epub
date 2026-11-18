# PYTHON_ARGCOMPLETE_OK
"""Command-line interface for txt2epub."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

import argcomplete

from txt2epub_cli import __version__
from txt2epub_cli.model import ParseResult
from txt2epub_cli.parser import parse_file
from txt2epub_cli.report import report_dict, report_human
from txt2epub_cli.rules import builtin_ruleset, load_rules

PROFILES = ("auto", "zxs", "strict", "loose")
DEDUPE_MODES = ("off", "exact", "similar")


def _rules_from_args(args: argparse.Namespace):
    rules = builtin_ruleset(args.profile)
    if args.rules is not None:
        rules = load_rules(args.rules, base=rules)
    if args.max_heading_length is not None:
        rules = replace(rules, max_heading_length=args.max_heading_length)
    return rules


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("paths", nargs="+", type=Path, metavar="PATH")
    parser.add_argument("--rules", type=Path, help="TOML rule overrides")
    parser.add_argument(
        "--profile", choices=PROFILES, default="auto", help="built-in rule profile"
    )
    parser.add_argument("--encoding", help="force source encoding (e.g. gb18030)")
    parser.add_argument(
        "--max-heading-length",
        type=int,
        metavar="N",
        help="override the heading length limit",
    )
    parser.add_argument(
        "--keep-noise", action="store_true", help="keep site noise as body text"
    )
    parser.add_argument(
        "--keep-toc", action="store_true", help="keep embedded TOC as front matter"
    )
    parser.add_argument(
        "--dedupe",
        choices=DEDUPE_MODES,
        default="off",
        help="optional chapter dedupe mode (default: off)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="txt2epub",
        description="Analyze and convert Chinese TXT novels to EPUB 3 with a multi-level TOC.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    inspect = subcommands.add_parser("inspect", help="analyze one or more TXT files")
    _add_common(inspect)
    inspect.add_argument(
        "--json", action="store_true", help="emit machine-readable JSON"
    )
    inspect.add_argument(
        "--limit",
        type=int,
        default=10,
        metavar="N",
        help="number of suspicious issues to show in human output (0 hides them)",
    )
    inspect.add_argument(
        "--verbose", action="store_true", help="show all suspicious issues"
    )
    inspect.add_argument(
        "--ignore-issue",
        action="append",
        default=[],
        metavar="CODE",
        help="hide an issue code from the human suspicious list (repeat or comma-separate)",
    )
    inspect.add_argument(
        "--only-issue",
        action="append",
        default=[],
        metavar="CODE",
        help="show only these issue codes in the human suspicious list",
    )

    convert = subcommands.add_parser(
        "convert", help="convert one or more TXT files to EPUB"
    )
    _add_common(convert)
    convert.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help="output directory (default: next to each source file)",
    )
    convert.add_argument(
        "--dry-run", action="store_true", help="parse and report without writing EPUB"
    )
    convert.add_argument("--report", type=Path, help="write a JSON report to this file")
    convert.add_argument(
        "--allow-loss",
        action="store_true",
        help="write EPUB even when coverage verification fails",
    )
    convert.add_argument(
        "--force", action="store_true", help="overwrite existing output files"
    )
    convert.add_argument(
        "--yes",
        action="store_true",
        help="answer yes to overwrite prompts (non-interactive batch mode)",
    )
    convert.add_argument(
        "--split-size",
        type=int,
        default=256 * 1024,
        metavar="BYTES",
        help="split chapters larger than this many UTF-8 bytes (default: 262144)",
    )
    convert.add_argument(
        "--indent-em",
        type=float,
        default=2.0,
        metavar="EM",
        help="CSS first-line indent for body paragraphs (default: 2em; 0 disables)",
    )
    convert.add_argument(
        "--no-indent",
        action="store_true",
        help="shortcut for --indent-em 0 (no first-line indent)",
    )
    convert.add_argument(
        "--css",
        type=Path,
        help="replace the built-in stylesheet with this CSS file",
    )
    convert.add_argument(
        "--verbose", action="store_true", help="show tracebacks on failure"
    )
    return parser


def _issue_codes(values: list[str] | None) -> set[str]:
    codes: set[str] = set()
    for value in values or []:
        codes.update(part.strip() for part in value.split(",") if part.strip())
    return codes


def _load_rules_or_exit(args: argparse.Namespace):
    try:
        return _rules_from_args(args)
    except (OSError, ValueError) as exc:
        print(f"txt2epub: rules error: {exc}", file=sys.stderr)
        raise SystemExit(3) from exc


def _parse_one(args: argparse.Namespace, path: Path) -> ParseResult:
    rules = _rules_from_args(args)
    return parse_file(
        path,
        rules=rules,
        forced_encoding=args.encoding,
        keep_noise=args.keep_noise,
        keep_toc=args.keep_toc,
        dedupe=args.dedupe,
        allow_loss=getattr(args, "allow_loss", False),
    )


def _cmd_inspect(args: argparse.Namespace) -> int:
    _load_rules_or_exit(args)
    results: list[ParseResult] = []
    exit_code = 0
    for path in args.paths:
        try:
            result = _parse_one(args, path)
        except Exception as exc:  # noqa: BLE001 - CLI boundary
            print(f"txt2epub: {path}: {exc}", file=sys.stderr)
            exit_code = 1
            continue
        results.append(result)
        if not result.coverage.ok and exit_code == 0:
            exit_code = 2

    if args.json:
        if len(results) == 1:
            payload: dict = report_dict(results[0])
        else:
            payload = {
                "schema_version": 1,
                "files": [report_dict(result) for result in results],
            }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return exit_code

    limit = 1000 if args.verbose else args.limit
    ignore_codes = _issue_codes(args.ignore_issue)
    only_codes = _issue_codes(args.only_issue)
    for index, result in enumerate(results):
        if index:
            print()
        print(
            report_human(
                result,
                limit=limit,
                ignore_codes=ignore_codes,
                only_codes=only_codes,
            )
        )
    return exit_code


def _default_output(path: Path, args: argparse.Namespace) -> Path:
    directory = args.output_dir if args.output_dir is not None else path.parent
    return directory / f"{path.stem}.epub"


def _confirm_overwrite(output: Path, args: argparse.Namespace) -> bool:
    if args.force or args.yes:
        return True
    if not sys.stdin.isatty():
        return False
    answer = input(f"{output} exists; overwrite? [y/N] ").strip().lower()
    return answer in {"y", "yes"}


def _cmd_convert(args: argparse.Namespace) -> int:
    _load_rules_or_exit(args)
    if args.indent_em < 0:
        print("txt2epub: --indent-em must be non-negative", file=sys.stderr)
        return 3
    indent_em = 0.0 if args.no_indent else args.indent_em
    custom_css: str | None = None
    if args.css is not None:
        try:
            custom_css = args.css.read_text(encoding="utf-8-sig")
        except OSError as exc:
            print(f"txt2epub: cannot read CSS file {args.css}: {exc}", file=sys.stderr)
            return 3
    reports: list[dict] = []
    successes = 0
    failures = 0
    coverage_failures = 0

    for path in args.paths:
        try:
            result = _parse_one(args, path)
        except Exception as exc:  # noqa: BLE001 - CLI boundary
            failures += 1
            print(f"FAIL {path}: {exc}", file=sys.stderr)
            reports.append({"schema_version": 1, "file": str(path), "error": str(exc)})
            continue

        output = _default_output(path, args)
        if not result.coverage.ok and not args.allow_loss:
            coverage_failures += 1
            failures += 1
            print(
                f"FAIL {path}: coverage mismatch "
                f"({len(result.coverage.missing)} missing, {len(result.coverage.extra)} extra); "
                "use --allow-loss to write anyway",
                file=sys.stderr,
            )
            reports.append(report_dict(result))
            continue

        if args.dry_run:
            successes += 1
            print(
                f"DRY  {path}: {result.stats.volumes} volumes, "
                f"{result.stats.chapters} chapters, {result.stats.specials} specials, "
                f"coverage {'ok' if result.coverage.ok else 'mismatch'}"
            )
            reports.append(report_dict(result))
            continue

        if output.exists() and not _confirm_overwrite(output, args):
            failures += 1
            print(f"SKIP {output}: exists (use --force or --yes)", file=sys.stderr)
            reports.append(report_dict(result))
            continue

        try:
            from txt2epub_cli.epub import write_epub

            output.parent.mkdir(parents=True, exist_ok=True)
            write_epub(
                result,
                output,
                split_size=args.split_size,
                indent_em=indent_em,
                custom_css=custom_css,
            )
        except Exception as exc:  # noqa: BLE001 - CLI boundary
            failures += 1
            print(f"FAIL {path}: {exc}", file=sys.stderr)
            if args.verbose:
                import traceback

                traceback.print_exc()
            reports.append(report_dict(result))
            continue

        successes += 1
        print(
            f"OK   {path} -> {output} "
            f"({result.stats.volumes} volumes, {result.stats.chapters} chapters, "
            f"coverage {'ok' if result.coverage.ok else 'mismatch'})"
        )
        reports.append(report_dict(result, output))

    if args.report is not None and reports:
        try:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            payload = (
                reports[0]
                if len(reports) == 1
                else {"schema_version": 1, "files": reports}
            )
            args.report.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            failures += 1
            print(f"FAIL writing report {args.report}: {exc}", file=sys.stderr)

    print(f"Summary: {successes} succeeded, {failures} failed")
    if coverage_failures and not successes:
        return 2
    if coverage_failures and failures == coverage_failures:
        return 2
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    argcomplete.autocomplete(parser)
    args = parser.parse_args(argv)
    if args.command == "inspect":
        return _cmd_inspect(args)
    if args.command == "convert":
        return _cmd_convert(args)
    parser.error(f"unknown command {args.command!r}")
    return 3
