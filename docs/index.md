# txt2epub

Auditable Chinese TXT to EPUB 3 converter with multi-level navigation for
KOReader, Kindle, and other EPUB readers.

The design goal is **never silently lose body text**. Every source line gets a
disposition in a line ledger, and conversion refuses to write an EPUB unless the
source/output/dropped text multiset balances (unless `--allow-loss` is passed).

!!! warning "AI usage disclosure"

    Most of this codebase was written by AI coding agents. Human maintainers
    have verified behavior through automated tests and real-book conversions,
    but have not performed a rigorous line-by-line review. Review the source
    before relying on it in sensitive environments.

## Highlights

- Detects UTF-8, UTF-8 BOM, UTF-16, GB18030, and Big5 input with CRLF or LF
  line endings.
- Recognizes 卷 / 章 / 节 headings and special sections such as `序章`, `前传`,
  `番外`, `终章`, `后记`, and `完本感言`.
- Handles awkward but common headings: `第一章活着`, `第0001章`,
  `第一卷 卷名 第1章 章名`, multi-number headings, and indented headings.
- Removes common site ads and watermarks, detects embedded TOC pages, and
  reports duplicate chapter numbers and numbering gaps without renaming
  anything.
- Generates nested EPUB 3 `nav.xhtml` and EPUB 2 `toc.ncx`, so old and new
  readers both get a proper multi-level table of contents.
- Converts one file or a batch; one failure does not stop the rest. Existing
  outputs are skipped unless `--force` is used.
- Optional exact or similar chapter dedupe, plus CSS-driven first-line indent
  and custom stylesheets.

## Install

The distribution is available on PyPI as `txt2epub-cli`:

```bash
uv tool install txt2epub-cli
```

The CLI command is `txt2epub`. For a one-off run without installing, use
`uvx --from txt2epub-cli txt2epub`.

## Quick start

```bash
# inspect without writing anything
txt2epub inspect book.txt

# write book.epub next to the source file
txt2epub convert book.txt

# batch into a directory
txt2epub convert *.txt -o out/
```

## Documentation

- [Getting Started](getting-started.md) - install, inspect, and convert.
- [CLI Reference](cli.md) - every option, batch summaries, and exit codes.
- [Rules and TOML Configuration](configuration.md) - profiles and examples for
  different chapter structures.
- [How It Works](how-it-works.md) - coverage, duplicate handling, output layout,
  and limitations.
- [Development](development.md) - tests, docs, and release workflow.
