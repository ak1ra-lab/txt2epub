# Development

## Setup

```bash
uv sync --group dev
uv run pre-commit install
```

The repository uses `just` as a thin wrapper around `uv run`. Agents and scripts
can call either form directly.

```bash
just lint        # ruff check --fix + ruff format
just typecheck   # ty check src/
just test        # pytest -v tests/
just coverage    # pytest with coverage
just build       # uv build
just docs-build  # mkdocs build
just docs-serve  # local docs preview
```

Run the full pre-commit suite before committing:

```bash
uv run pre-commit run --all-files
```

## Tests and fixtures

Committed tests use synthetic placeholder fixtures only. Never commit real book
text. `tests/golden/samples.json` is a fixture snapshot of counts and first/last
headings; update it only when fixture behavior changes intentionally.

Local samples under `examples/txt/` and `examples/epub/` are gitignored. To run
the opt-in smoke tests:

```bash
TXT2EPUB_LOCAL_SAMPLES=1 uv run pytest -m local
```

## Documentation

The site is built with mkdocs and the i18n plugin using suffix-based files:

- `docs/page.md` for English.
- `docs/page.zh.md` for Simplified Chinese.

Update both language files when user-facing behavior changes. The build output
is deployed to GitHub Pages by the docs workflow.

## Versioning and releases

The version is derived from Git tags by `hatch-vcs`; `fallback_version` is
`0.1.0`. Do not edit a version string manually and do not add an
`__version__` constant. `src/txt2epub_cli/__init__.py` reads installed package
metadata.

Pushing a `v*` tag triggers the PyPI workflow. Do that only when a release is
intended. `CHANGELOG.md` follows Keep a Changelog and Semantic Versioning.

## Template

The project was scaffolded from
[`copier-pyproject`](https://github.com/ak1ra-lab/copier-pyproject).
`.copier-answers.yml` records the template revision and the distribution,
command, and import names. Verify a `copier update` with `--pretend` before
applying it.
