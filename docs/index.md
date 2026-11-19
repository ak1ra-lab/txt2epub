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
- Generates nested EPUB 3 `nav.xhtml` and EPUB 2 `toc.ncx`, so old and new
  readers both get a proper multi-level table of contents.
- Reports encoding, heading counts, duplicate numbers, numbering gaps,
  coverage, and suspicious lines without rewriting the source.
- Converts one file or a batch; one failure does not stop the rest.

## Install

The distribution is available on PyPI as `txt2epub-cli`:

```bash
uv tool install txt2epub-cli
```

The CLI command is `txt2epub`; the import package is `txt2epub_cli`. The
separate import name avoids clashing with the unrelated PyPI package
`txt2epub`.

## Next steps

- [Getting Started](getting-started.md)
- [Project README](https://github.com/ak1ra-lab/txt2epub)
