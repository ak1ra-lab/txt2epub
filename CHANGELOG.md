# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- `convert` now skips existing output files by default instead of prompting;
  pass `--force` to overwrite them. Batch summaries report succeeded, failed,
  and skipped counts.
- Removed the `--yes` option, which only existed to answer overwrite prompts.
- Removed the `zxs` built-in profile. Site-specific 知轩藏书 noise patterns are
  now a local TOML example in the documentation.
- Documentation now recommends only `uv tool install`, `uvx`, and `uv sync` for
  source checkouts; `pip install` guidance was removed.
- Trimmed `README.md` to install and quick-start guidance, and expanded the
  mkdocs site with CLI reference, TOML configuration, behavior, and development
  pages.

### Fixed

- Removed the accepted-but-unimplemented `[heading] require_column_zero` and
  `allowed_indent` TOML keys so configuration errors are explicit.

## [0.1.0] - 2026-11-19

### Added

- Auditable Chinese TXT to EPUB 3 conversion with a line ledger, coverage
  verification, and an explicit `--allow-loss` escape hatch
- `inspect` and `convert` subcommands with JSON reports, batch processing, dry
  runs, and non-interactive overwrite handling
- Encoding detection for UTF-8, UTF-8 BOM, UTF-16, GB18030, and Big5
- Multi-level EPUB 3 `nav.xhtml` and EPUB 2 `toc.ncx` generation
- Heading detection for volumes, chapters, sections, special sections,
  combined prefixes, multi-number headings, zero-padded numbers, and indented
  headings
- Built-in rule profiles, TOML rule overrides, noise filtering, embedded TOC
  handling, and optional exact or similar chapter dedupe
- CSS-driven first-line indentation with `--indent-em`, `--no-indent`, and
  custom `--css`
- `argcomplete` shell completion for the `txt2epub` command
- PyPI distribution `txt2epub-cli` with CLI command `txt2epub` and import
  package `txt2epub_cli`
- Bilingual English and Simplified Chinese documentation with GitHub Pages
  deployment
- Explicit AI usage disclosure in the README and documentation

[0.1.0]: https://github.com/ak1ra-lab/txt2epub/releases/tag/v0.1.0
