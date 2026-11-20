# Getting Started

## Prerequisites

- Python 3.11 or newer.
- [uv](https://docs.astral.sh/uv/).

The PyPI distribution is `txt2epub-cli` and the CLI command is `txt2epub`.

## Install from PyPI

```bash
# isolated CLI install (recommended)
uv tool install txt2epub-cli

# run once without installing
uvx --from txt2epub-cli txt2epub --help
```

## Run from a source checkout

```bash
git clone https://github.com/ak1ra-lab/txt2epub.git
cd txt2epub

uv sync
uv run txt2epub --help
```

For development, install the development dependency group and run the quality
gates from the same checkout:

```bash
uv sync --group dev
uv run pre-commit install
```

## Inspect a book

`inspect` parses the source and prints a report without writing an EPUB:

```bash
txt2epub inspect book.txt
txt2epub inspect book.txt --json
txt2epub inspect examples/**/*.txt --json > report.json
```

Human output includes encoding, line and character counts, front matter,
heading counts, the first and last heading, issue summary, coverage, and a short
suspicious list. Use `--verbose` to show every warning, or `--limit 0` to hide
the list.

## Convert

```bash
# write book.epub next to the source file
txt2epub convert book.txt

# batch into a directory
txt2epub convert *.txt -o out/

# parse and report only
txt2epub convert book.txt --dry-run

# write a JSON report for automation
txt2epub convert *.txt -o out/ --report out/report.json

# overwrite existing outputs
txt2epub convert *.txt -o out/ --force
```

If the target file already exists, `convert` skips it without prompting. Pass
`--force` to overwrite it. The final summary counts succeeded, failed, and
skipped files:

```text
Summary: 3 succeeded, 1 failed, 2 skipped
```

Body paragraphs are stripped of leading and trailing spaces and tabs before
being written to XHTML. Indentation is controlled by the EPUB stylesheet, so
the default uses `text-indent: 2em`. Use `--no-indent`, `--indent-em`, or
`--css` to change it.

## Shell completion

```bash
eval "$(register-python-argcomplete txt2epub)"
```

## Next steps

- [CLI Reference](cli.md) - all options, report fields, and exit codes.
- [Rules and TOML Configuration](configuration.md) - tune heading detection for
  your source files.
- [How It Works](how-it-works.md) - coverage, duplicates, output layout, and
  limitations.
