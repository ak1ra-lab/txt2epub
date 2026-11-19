# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Auditable TXT to EPUB 3 conversion with a line ledger, coverage
  verification, and an explicit `--allow-loss` escape hatch
- `inspect` and `convert` subcommands with JSON reports, batch processing,
  dry runs, and non-interactive overwrite handling
- Encoding detection for UTF-8, UTF-8 BOM, UTF-16, GB18030, and Big5
- Multi-level EPUB 3 `nav.xhtml` and EPUB 2 `toc.ncx` generation
- Heading support for volumes, chapters, sections, special sections, combined
  prefixes, multi-number headings, and indented headings
- Built-in rule profiles, TOML rule overrides, noise filtering, embedded TOC
  handling, and optional exact or similar chapter dedupe
- `argcomplete` shell completion for the `txt2epub` command
- Copier-based project scaffold with `uv`, `ruff`, `ty`, `pytest`,
  `mkdocs-material`, pre-commit, and bilingual documentation
- Explicit AI usage disclosure in the README and documentation

### Changed

- Move project hosting and package metadata URLs to
  <https://github.com/ak1ra-lab/txt2epub>
- Replace GitLab CI with GitHub Actions for lint, type checking, multi-version
  tests, and package builds; PyPI publishing remains tag-driven
- Rename the distribution to `txt2epub-cli`, keep the `txt2epub` CLI command,
  and move the import package to `txt2epub_cli` to avoid a collision with the
  PyPI package named `txt2epub`
- Adopt `hatch-vcs` dynamic versioning and read the version from installed
  package metadata
- Move Ruff configuration from `pyproject.toml` to `ruff.toml`
- Refresh scaffold versions: uv 0.13.9 on Debian trixie, Python 3.11-3.14 CI
  matrix, setup-uv 10.3.3, pypi-publish 1.14.3, ruff 0.17.5, ty 0.0.105,
  pytest 9.2.0, mkdocs-material 9.8.1, and pre-commit 4.7.0
- Refresh project metadata, README development commands, and `.gitignore`

### Fixed

- Strip literal body indentation and drive first-line indent from CSS
- Keep noise as body text, report long heading candidates, and cover section
  parsing
- Validate EPUB structure for every fixture and test span sequences,
  `--allow-loss`, and fixture golden counts

### Removed

- Unused `Dockerfile` and `.dockerignore`
- GitLab CI configuration; GitHub Actions is now the active pipeline
- Pre-release status notices from the README and documentation
- Committed local sample smoke script; use the opt-in
  `TXT2EPUB_LOCAL_SAMPLES=1` pytest marker instead
