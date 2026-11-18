# txt2epub

An auditable Chinese TXT → EPUB 3 converter with multi-level navigation for
KOReader, Kindle, and other EPUB readers.

The design goal is simple: **never silently lose body text**. Every source line
gets a disposition in a line ledger, and conversion refuses to write an EPUB
unless the source/output/dropped text multiset balances (unless you explicitly
pass `--allow-loss`).

## Features

- Detects UTF-8 / UTF-8 BOM / UTF-16 / GB18030 / Big5 input, CRLF or LF.
- Recognizes 卷 / 章 / 节 / special sections (`序章`, `前传`, `番外`, `终章`,
  `后记`, `完本感言`, ...).
- Handles common awkward formats:
  - `第一章活着` (no separator between number and title)
  - `第0001章` zero-padded numbers
  - `第一卷 卷名 第1章 章名` combined volume+chapter prefixes
  - `第104、105章` and `第1037章—第1038章` multi-number headings
  - indented headings (books where every heading starts with U+3000)
  - short indented volume names such as `　　第一卷，惊蛰。`
- Removes obvious site ads/watermarks, detects embedded TOC pages, reports
  duplicate chapter numbers and number gaps without renaming anything.
- Generates nested EPUB 3 `nav.xhtml` **and** EPUB 2 `toc.ncx`, so old and new
  readers both get a proper multi-level TOC.
- Batches multiple files; one failure does not stop the rest.

## Install

Requires Python 3.11+.

```bash
# with uv (recommended for development)
uv sync
uv run txt2epub --help

# or install into the current environment
pip install -e .
txt2epub --help
```

`python -m txt2epub_cli ...` works as well.

## Usage

### Inspect without writing files

```bash
txt2epub inspect book.txt
txt2epub inspect book.txt --json
txt2epub inspect examples/txt/*.txt --json > report.json
```

Human output includes encoding, line/char counts, front matter, heading counts,
first/last heading, issue summary, coverage, and a short suspicious list.
Add `--verbose` to show all warnings, or `--limit 0` to hide the list.

Some books have genuine source-level numbering gaps, or many expected
indented duplicate headings.  Focus the human list without changing the JSON
report:

```bash
# hide known source numbering gaps
txt2epub inspect book.txt --verbose --ignore-issue number_gap

# hide several codes (repeat the option or use commas)
txt2epub inspect book.txt --verbose \
  --ignore-issue number_gap,duplicate_number

# show only conflicts and gaps
txt2epub inspect book.txt --only-issue number_conflict,number_gap

# indented duplicate headings are severity=info; show them explicitly
txt2epub inspect book.txt --only-issue duplicate_indented
```

`--ignore-issue` / `--only-issue` affect only the human suspicious list;
`--json` always contains the complete issue list.

### Convert one or many files

```bash
# output next to the source file: book.epub
txt2epub convert book.txt

# batch into a directory
txt2epub convert *.txt -o out/

# parse and report only, no EPUB
txt2epub convert book.txt --dry-run

# write a JSON report for automation
txt2epub convert *.txt -o out/ --report out/report.json

# overwrite existing outputs non-interactively
txt2epub convert *.txt -o out/ --yes

# no first-line indent (indentation is CSS-driven, not literal spaces)
txt2epub convert book.txt --no-indent

# custom first-line indent in em
txt2epub convert book.txt --indent-em 1.5

# replace the built-in stylesheet entirely
txt2epub convert book.txt --css my-style.css
```

When an output file already exists, interactive runs ask before overwriting.
Use `--force` or `--yes` in scripts.

Body paragraphs are stripped of their source leading/trailing spaces and tabs
before being written to XHTML.  Indentation is controlled by the EPUB stylesheet
instead, so a source line beginning with two U+3000 spaces does not become a
double indent on Kindle.  The default stylesheet uses `text-indent: 2em`.
`--no-indent` writes `text-indent: 0`; `--css` replaces the stylesheet and takes
precedence over `--indent-em`.

### Exit codes

| code | meaning |
|---:|---|
| 0 | success |
| 1 | parse / write / input error |
| 2 | coverage or validation failure |
| 3 | rule/config error |

For a batch, processing continues after a failure; the final exit code reflects
whether any file failed.

## Rules and profiles

Built-in profiles:

| profile | behavior |
|---|---|
| `auto` (default) | common web-novel formats, allows indented headings |
| `zxs` | `auto` plus 知轩藏书-style site noise cleanup |
| `strict` | column-zero headings only, separator required, 40-char limit |
| `loose` | indented headings, longer titles, pure-number headings |

Select with `--profile`, and/or override with a TOML file:

```bash
txt2epub inspect book.txt --profile strict --rules my-rules.toml
```

Example `my-rules.toml`:

```toml
[heading]
max_length = 50
allow_indented_headings = true
volume_suffix_special_suffixes = ["序", "章", "篇", "传", "记", "录"]

[patterns]
# Additional patterns are appended to the built-ins.
chapter = '^第(?P<num>[0-9零〇一二三四五六七八九十百千万两]+)[章节回集幕](?:[\s　:：]*(?P<title>.*))?$'
# Set replace_patterns = true to replace the built-in lists instead of appending.
replace_patterns = false

[exclude]
volume_suffixes = ["门", "队", "属", "分", "件", "落"]

[noise]
patterns = ["免费阅读", "百度搜索", "请务必保存好书签", "为您提供大神", "秒更", "br>"]
```

Rules are plain single-line regular expressions. Invalid regexes and unknown
TOML keys produce a configuration error instead of a traceback.

## Coverage

`inspect` and `convert` both report:

```text
Coverage:   100.00% (source 1,234,567 / output 1,234,567 / dropped 0)
```

- `source` counts normalized text units from every non-blank source line.
- `output` counts heading titles, front matter, and body paragraphs.
- `dropped` counts noise / duplicate headings / embedded TOC lines that were
  intentionally removed, so the totals still balance.
- If the multiset does not balance, `convert` exits with code 2 and does not
  write a file. Use `--allow-loss` only when you understand why.

`--keep-noise` keeps site ads as body text. `--keep-toc` keeps an embedded TOC
page as front matter instead of deleting it.

## Duplicate numbers and optional dedupe

By default, duplicate chapter numbers are **reported, not renumbered**. If two
headings have the same number and same title, the later heading is merged into
the first occurrence and its body is preserved. Same number + different title is
reported as `number_conflict` and both chapters are kept.

Indented duplicate headings that merely echo an existing column-zero chapter
(e.g. a repeated title with a site suffix) are recorded as
`duplicate_indented` with severity `info`; they do not flood the warning list.

Optional content dedupe:

```bash
txt2epub convert book.txt --dedupe exact    # identical title+body hash
txt2epub convert book.txt --dedupe similar  # near-identical body (>= 0.9)
```

Both are off by default.

## Output layout

```text
mimetype
META-INF/container.xml
OEBPS/content.opf
OEBPS/nav.xhtml
OEBPS/toc.ncx
OEBPS/style.css
OEBPS/text/front-matter.xhtml
OEBPS/text/part-0001.xhtml
OEBPS/text/chapter-0001.xhtml
...
```

Volume/special parent nodes always get a real XHTML page, so every nav/NCX
entry has a valid link. Chapters larger than `--split-size` (default 256 KiB)
are split at paragraph boundaries; only the first fragment appears in the TOC.

## Development

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest

# optional local sample smoke (samples are gitignored)
TXT2EPUB_LOCAL_SAMPLES=1 uv run pytest -m local
```

Committed tests use synthetic placeholder fixtures only. Local samples under
`examples/txt/` (or `examples/txt/`) are never committed.

## Known limitations

- MVP keeps one source line per paragraph; it does not reflow or re-paragraph.
- No cover image generation; a future option can accept an external cover.
- No AI rewriting or automatic chapter-title generation.
- Big5 detection is best-effort; GB18030 is tried first because most simplified
  Chinese samples are GB18030.
- No MOBI/AZW3 output, no GUI, no KOReader plugin.
- DRM-free input only.

## License

GPL-3.0-only. See `LICENSE`.
