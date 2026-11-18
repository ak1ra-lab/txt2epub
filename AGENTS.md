# AGENTS.md

txt2epub is a Python 3.11+ CLI that converts Chinese TXT novels to EPUB 3 with
an auditable line ledger and a multi-level table of contents. Application code
lives under `src/txt2epub_cli`; see `README.md` for behavior and CLI examples.

## Tooling - use these, not the defaults

`just <recipe>` is a convenience wrapper for humans; each recipe is a thin
`uv run ...` (see `justfile`). Agents can call `uv run ...` directly when that is
more flexible - the two are equivalent, not mutually exclusive.

- Env/deps: **uv** (`just sync` = `uv sync --group dev`; extra args forward
  through, e.g. `just sync --frozen`). Never `pip`/`poetry`/`pipenv`.
- Lint+format: **ruff** (`just lint` = `uv run ruff check --fix` then
  `uv run ruff format` over `src/` and `tests/`). Never
  `black`/`isort`/`flake8`.
- Typecheck: **ty** (astral-sh/ty), `src/` only
  (`just typecheck` = `uv run ty check src/`). Never `mypy`.
- Tests: **pytest** (`just test` = `uv run pytest -v tests/`). Extra args go
  *before* `tests/`, so `just test -k <pattern>`; or run
  `uv run pytest -v tests/unit/test_parser.py` directly.
- Docs: `just docs-build` = `NO_MKDOCS_2_WARNING=1 uv run mkdocs build`
  (and `just docs-serve` to preview).
- Build: `just build` = `uv build`.
- Pre-commit: `uv run pre-commit run --all-files` runs every configured hook
  (check-yaml/check-toml, end-of-file-fixer, trailing-whitespace, ruff, uv-lock,
  ty). Run it explicitly before committing - the hooks are not a passive safety
  net.
- CI: GitLab CI uses uv's Debian trixie image and `UV_PYTHON` to install
  interpreters on demand; tests run on Python 3.11-3.14. GitHub workflows are
  kept for a future mirror.

Python changes MUST pass ruff, ty, and pytest before commit, then
`uv run pre-commit run --all-files` as the final gate for the remaining hooks.

## Project conventions

- Every non-blank source line must receive a ledger disposition. Do not add a
  code path that drops text without recording it, and keep `convert` refusing
  coverage mismatches unless `--allow-loss` is set.
- `tests/fixtures/txt/` contains synthetic placeholders only. Never commit real
  book text, and never copy local samples into fixtures or golden data.
- `tests/golden/samples.json` is a fixture snapshot of counts and first/last
  headings. Update it only when fixture behavior changes intentionally.
- `examples/` is gitignored local sample data. `tests/local/` is opt-in via
  `TXT2EPUB_LOCAL_SAMPLES=1`.
- `src/txt2epub_cli/templates/` holds package data read at runtime through
  `importlib.resources`. Keep it inside the package so wheels include it.
- EPUB output must stay valid: `mimetype` is the first stored ZIP member, and
  `nav.xhtml`, `toc.ncx`, and `content.opf` must link to existing members.
- `pyproject.toml` is the single source of truth for dependencies and metadata.

## Versioning and publishing

Version is dynamic via `hatch-vcs` (Git tags); `fallback_version` is `0.1.0`.
Do not manually bump a version string, and do not add `__version__` constants:
`src/txt2epub_cli/__init__.py` reads installed package metadata.

This repository lives on an internal GitLab instance and is not published.
The distribution name is `txt2epub-cli`; the CLI command is `txt2epub` and the
import package is `txt2epub_cli`. The names `txt2epub` and `text2epub` are
already taken on PyPI, so the separate import name keeps both distributions from
sharing `site-packages/txt2epub`. Prefer virtualenvs or `uv tool install` for
isolated installs. Do not push a `v*` tag or run the PyPI workflow until
publishing is explicitly approved. The GitHub Actions files are template
artifacts for a future mirror; GitLab CI in `.gitlab-ci.yml` is the active
pipeline.

## Template

`.copier-answers.yml` records the `copier-pyproject` revision and answers,
including the distribution, command, and import names. Verify a
`copier update` with `--pretend` before applying it; do not apply template
changes blindly.

## Docs (bilingual)

`docs/` is served by mkdocs with the i18n plugin (`docs_structure: suffix`):
every page has an English `*.md` and a Simplified-Chinese `*.zh.md` sibling
(e.g. `index.md` + `index.zh.md`). When adding or changing user-facing behavior,
update BOTH language files.
