"""txt2epub: an auditable Chinese TXT to EPUB 3 converter."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("txt2epub-cli")
except PackageNotFoundError:  # pragma: no cover - source tree without metadata
    __version__ = "0.0.0"
