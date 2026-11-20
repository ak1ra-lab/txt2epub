# txt2epub

[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/ak1ra-lab/txt2epub/.github%2Fworkflows%2Fpublish-to-pypi.yaml)](https://github.com/ak1ra-lab/txt2epub/actions/workflows/publish-to-pypi.yaml)
[![PyPI - Version](https://img.shields.io/pypi/v/txt2epub-cli)](https://pypi.org/project/txt2epub-cli/)
[![Docs](https://img.shields.io/badge/docs-online-0a7ea4)](https://ak1ra-lab.github.io/txt2epub/)

An auditable Chinese TXT → EPUB 3 converter with multi-level navigation for
KOReader, Kindle, and other EPUB readers.

Every source line gets a disposition in a line ledger. Conversion refuses to
write an EPUB unless the source/output/dropped text multiset balances, unless
`--allow-loss` is passed explicitly.

> **AI usage disclosure:** Most of this codebase was written by AI coding
> agents. Human maintainers have verified behavior with automated tests and
> real-book conversions, but have not performed a rigorous line-by-line review.
> Review the source before relying on it in sensitive environments.

## Install

Requires Python 3.11+. Install with [uv](https://docs.astral.sh/uv/).

```bash
# install as an isolated CLI tool (recommended)
uv tool install txt2epub-cli

# or run once without installing
uvx --from txt2epub-cli txt2epub --help
```

The PyPI distribution is `txt2epub-cli`, and the CLI command is `txt2epub`.

## Quick start

```bash
# inspect without writing anything
txt2epub inspect book.txt

# write book.epub next to the source file
txt2epub convert book.txt

# batch into a directory
txt2epub convert *.txt -o out/
```

Existing output files are skipped by default. Pass `--force` to overwrite them.
A batch run ends with a summary of succeeded, failed, and skipped files.

## Documentation

- [Getting Started](https://ak1ra-lab.github.io/txt2epub/getting-started/)
- [CLI Reference](https://ak1ra-lab.github.io/txt2epub/cli/)
- [Rules and TOML Configuration](https://ak1ra-lab.github.io/txt2epub/configuration/)
- [How It Works](https://ak1ra-lab.github.io/txt2epub/how-it-works/)
- [Development](https://ak1ra-lab.github.io/txt2epub/development/)

Full documentation (English and Simplified Chinese):
<https://ak1ra-lab.github.io/txt2epub/>

## Development

```bash
uv sync --group dev
uv run pre-commit install

just lint
just typecheck
just test
```

See the [development documentation](https://ak1ra-lab.github.io/txt2epub/development/)
for test fixtures, local samples, docs, and release notes.

## License

GPL-3.0-only. See `LICENSE`.
