# CLI Reference

```text
txt2epub [COMMON OPTIONS] inspect PATH...
txt2epub [COMMON OPTIONS] convert PATH... [CONVERT OPTIONS]
```

## Common options

| Option | Description |
| --- | --- |
| `PATH...` | One or more source files. Shell globs are expanded by your shell. |
| `--profile {auto,strict,loose}` | Built-in rule profile (default: `auto`). |
| `--rules PATH` | TOML rule overrides loaded on top of the profile. |
| `--encoding NAME` | Force the source encoding (for example `gb18030`). |
| `--max-heading-length N` | Override the heading length limit after the profile and TOML file are applied. |
| `--keep-noise` | Keep site ads and watermarks as body text. |
| `--keep-toc` | Keep an embedded TOC page as front matter. |
| `--dedupe {off,exact,similar}` | Optional chapter dedupe mode (default: `off`). |

## inspect

`inspect` parses the source and prints a report without writing files.

| Option | Description |
| --- | --- |
| `--json` | Emit machine-readable JSON instead of the human report. |
| `--limit N` | Number of suspicious issues in human output (default: 10; `0` hides the list). |
| `--verbose` | Show all suspicious issues. |
| `--ignore-issue CODE` | Hide an issue code from the human list. Repeat the option or use commas. |
| `--only-issue CODE` | Show only these issue codes in the human list. Repeat or comma-separate. |

`--ignore-issue` and `--only-issue` affect only the human suspicious list. The
`--json` report always contains the complete issue list.

Common issue codes include `number_gap`, `duplicate_number`,
`number_conflict`, and `duplicate_indented`.

```bash
# hide known source numbering gaps
txt2epub inspect book.txt --verbose --ignore-issue number_gap

# hide several codes
txt2epub inspect book.txt --verbose \
  --ignore-issue number_gap,duplicate_number

# show only conflicts and gaps
txt2epub inspect book.txt --only-issue number_conflict,number_gap

# indented duplicate headings have severity=info
txt2epub inspect book.txt --only-issue duplicate_indented
```

With one file, `--json` emits a single report object. With multiple files, it
emits `{"schema_version": 1, "files": [...]}`.

## convert

`convert` parses each source file, verifies coverage, and writes an EPUB.

| Option | Description |
| --- | --- |
| `-o, --output-dir DIR` | Output directory (default: next to each source file). |
| `--dry-run` | Parse and report only; write no EPUB. Counted as succeeded in the summary. |
| `--report PATH` | Write a JSON report. |
| `--force` | Overwrite existing output files. Without it, existing outputs are skipped. |
| `--allow-loss` | Write an EPUB even when coverage verification fails. |
| `--split-size BYTES` | Split chapters larger than this many UTF-8 bytes (default: `262144`; must be positive). |
| `--indent-em EM` | CSS first-line indent for body paragraphs (default: `2.0`; `0` disables). |
| `--no-indent` | Shortcut for `--indent-em 0`. |
| `--css PATH` | Replace the built-in stylesheet. Takes precedence over `--indent-em`. |
| `--verbose` | Show tracebacks on failure. |

```bash
# output next to each source file
txt2epub convert book.txt

# batch into a directory
txt2epub convert *.txt -o out/

# parse and report only
txt2epub convert book.txt --dry-run

# write a JSON report
txt2epub convert *.txt -o out/ --report out/report.json

# overwrite existing outputs
txt2epub convert *.txt -o out/ --force

# no first-line indent
txt2epub convert book.txt --no-indent

# custom first-line indent in em
txt2epub convert book.txt --indent-em 1.5

# replace the built-in stylesheet entirely
txt2epub convert book.txt --css my-style.css
```

### Existing outputs and batch summary

`convert` never prompts. If the target file exists and `--force` is not set,
the source file is skipped before parsing. This makes a repeated batch run
cheap and safe:

```text
SKIP book.txt: out/book.epub exists (use --force to overwrite)
Summary: 2 succeeded, 1 failed, 3 skipped
```

- A skipped file is not a failure. If every file is skipped, the exit code is
  `0`.
- `--dry-run` ignores existing outputs because it writes nothing.
- A batch continues after a failure. The summary always reports succeeded,
  failed, and skipped counts.

### JSON report

Each `convert` report entry has a `status` field:

| Status | Meaning |
| --- | --- |
| `converted` | EPUB written successfully. |
| `dry-run` | Parsed and reported; no EPUB written. |
| `skipped` | Target existed and `--force` was not set. |
| `failed` | Parse, coverage, or write failure. |

Converted, dry-run, and post-parse failed entries include the full inspect
report fields. Entries that fail before parsing include `file`, `status`, and
`error`. A single-file report is one object; a batch report is
`{"schema_version": 1, "files": [...]}`.

## Exit codes

| Code | Meaning |
| ---: | --- |
| 0 | Success (including skipped files). |
| 1 | At least one parse / write / input error, or a mixed batch with non-coverage failures. |
| 2 | Every failed file failed coverage or validation. |
| 3 | Rule or configuration error. |

For a batch, processing continues after a failure; the final exit code reflects
the failed files, not the skipped ones.
