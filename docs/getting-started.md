# Getting Started

## Prerequisites

- Python 3.11 or newer.
- [uv](https://docs.astral.sh/uv/) for the recommended workflow, or `pip` for a
  plain editable install.

The distribution is named `txt2epub-cli`; the CLI command is `txt2epub` and the
import package is `txt2epub_cli`. Install it in a virtualenv, or run
`uv tool install .` from the repository root. The separate import name avoids
clashing with the unrelated PyPI package `txt2epub`.

## Install from source

```bash
git clone git@github.com:ak1ra-lab/txt2epub.git
cd txt2epub

uv sync --group dev
uv run txt2epub --help
```

To install the working tree into the current environment instead:

```bash
pip install -e .
txt2epub --help
```

`python -m txt2epub_cli ...` works as well.

## Inspect a book

`inspect` parses the source and prints a report without writing an EPUB:

```bash
uv run txt2epub inspect book.txt
uv run txt2epub inspect book.txt --json
uv run txt2epub inspect examples/**/*.txt --json > report.json
```

Human output includes encoding, line and character counts, front matter,
heading counts, the first and last heading, issue summary, coverage, and a short
suspicious list. Use `--verbose` to show every warning, or `--limit 0` to hide
the list.

## Convert

```bash
# write book.epub next to the source file
uv run txt2epub convert book.txt

# batch into a directory
uv run txt2epub convert *.txt -o out/

# parse and report only
uv run txt2epub convert book.txt --dry-run

# write a JSON report for automation
uv run txt2epub convert *.txt -o out/ --report out/report.json

# overwrite existing outputs non-interactively
uv run txt2epub convert *.txt -o out/ --yes
```

Body paragraphs are stripped of leading and trailing spaces and tabs before
being written to XHTML. Indentation is controlled by the EPUB stylesheet, so
the default uses `text-indent: 2em`. Use `--no-indent`, `--indent-em`, or
`--css` to change it.

## Shell completion

```bash
eval "$(register-python-argcomplete txt2epub)"
```

## Development

```bash
uv sync --group dev
uv run pre-commit install

just lint
just typecheck
just test
just coverage
just build
just docs-build
```

Committed tests use synthetic placeholder fixtures only. Local samples under
`examples/txt/` or `examples/epub/` are gitignored:

```bash
TXT2EPUB_LOCAL_SAMPLES=1 uv run pytest -m local
```

## Exit codes

| code | meaning |
| ---: | --- |
| 0 | success |
| 1 | parse / write / input error |
| 2 | coverage or validation failure |
| 3 | rule/config error |

For a batch, processing continues after a failure; the final exit code reflects
whether any file failed.
