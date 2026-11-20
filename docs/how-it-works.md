# How It Works

## Line ledger and coverage

Every physical source line receives one disposition: front matter, heading,
body, noise, duplicate, embedded TOC page, or blank. The parser then checks that
the source, output, and intentionally dropped text multisets balance.

`inspect` and `convert` both report:

```text
Coverage:   100.00% (source 1,234,567 / output 1,234,567 / dropped 0)
```

- `source` counts normalized text units from every non-blank source line.
- `output` counts heading titles, front matter, and body paragraphs.
- `dropped` counts noise, duplicate headings, and embedded TOC lines that were
  intentionally removed, so the totals still balance.
- If the multiset does not balance, `convert` exits with code `2` and does not
  write a file. Use `--allow-loss` only when you understand why.

`--keep-noise` keeps site ads as body text. `--keep-toc` keeps an embedded TOC
page as front matter instead of deleting it.

## Noise and embedded TOC pages

Common site ads, watermarks, and short noise lines are removed and recorded in
the ledger. Embedded TOC pages are detected and removed by default. Nothing is
silently discarded: both cases show up as dropped text and as issues in the
report.

## Duplicate numbers and optional dedupe

By default, duplicate chapter numbers are **reported, not renumbered**. If two
headings have the same number and the same title, the later heading is merged
into the first occurrence and its body is preserved. The same number with a
different title is reported as `number_conflict`, and both chapters are kept.

Indented duplicate headings that merely echo an existing column-zero chapter
(for example, a repeated title with a site suffix) are recorded as
`duplicate_indented` with severity `info`; they do not flood the warning list.

Optional content dedupe:

```bash
txt2epub convert book.txt --dedupe exact    # identical title+body hash
txt2epub convert book.txt --dedupe similar  # near-identical body (>= 0.9)
```

Both modes are off by default.

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

Volume and special parent nodes always get a real XHTML page, so every nav/NCX
entry has a valid link. Chapters larger than `--split-size` (default 256 KiB)
are split at paragraph boundaries; only the first fragment appears in the TOC.

## Known limitations

- One source line remains one paragraph; the converter does not reflow or
  re-paragraph text.
- No cover image generation. A future option can accept an external cover.
- No AI rewriting or automatic chapter-title generation.
- Big5 detection is best-effort; GB18030 is tried first because most simplified
  Chinese samples are GB18030.
- No MOBI/AZW3 output, no GUI, and no KOReader plugin.
- DRM-free input only.
