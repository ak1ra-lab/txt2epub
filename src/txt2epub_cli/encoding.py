"""Byte decoding with lightweight, Chinese-aware encoding detection."""

from __future__ import annotations

import codecs
from pathlib import Path

from .model import DecodedText

_REPLACEMENT_CHAR = "\ufffd"
_BOMS: tuple[tuple[bytes, str], ...] = (
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
)


def decode_bytes(data: bytes, forced_encoding: str | None = None) -> DecodedText:
    """Decode *data*, detecting the encoding unless one is forced.

    A forced encoding is always honored. Unknown codec names propagate
    ``LookupError`` to the caller.
    """
    if forced_encoding is not None:
        return _decode_forced(data, forced_encoding)

    if not data:
        return DecodedText(
            text="",
            encoding="utf-8",
            confidence=1.0,
            errors=0,
            used_fallback=False,
            had_bom=False,
            newline="\n",
        )

    for bom, encoding in _BOMS:
        if data.startswith(bom):
            return _decode_bom(data, encoding)

    return _detect_encoding(data)


def read_text_file(path: Path, forced_encoding: str | None = None) -> DecodedText:
    """Read *path* and decode it with the same rules as :func:`decode_bytes`."""
    return decode_bytes(path.read_bytes(), forced_encoding)


def _decode_forced(data: bytes, encoding: str) -> DecodedText:
    try:
        text = data.decode(encoding, errors="strict")
    except UnicodeDecodeError:
        text = data.decode(encoding, errors="replace")
        return _finalize(
            text,
            encoding,
            confidence=0.5,
            errors=text.count(_REPLACEMENT_CHAR),
            used_fallback=True,
        )
    return _finalize(text, encoding, confidence=1.0, errors=0, used_fallback=False)


def _decode_bom(data: bytes, encoding: str) -> DecodedText:
    try:
        text = data.decode(encoding, errors="strict")
    except UnicodeDecodeError:
        text = data.decode(encoding, errors="replace")
        return _finalize(
            text,
            encoding,
            confidence=0.5,
            errors=text.count(_REPLACEMENT_CHAR),
            used_fallback=True,
            had_bom=True,
        )
    return _finalize(
        text,
        encoding,
        confidence=1.0,
        errors=0,
        used_fallback=False,
        had_bom=True,
    )


def _detect_encoding(data: bytes) -> DecodedText:
    for encoding, confidence in (
        ("utf-8", 1.0),
        ("gb18030", 0.9),
        ("big5", 0.8),
    ):
        try:
            text = data.decode(encoding, errors="strict")
        except UnicodeDecodeError:
            continue
        return _finalize(
            text,
            encoding,
            confidence=confidence,
            errors=0,
            used_fallback=False,
        )

    text = data.decode("gb18030", errors="replace")
    return _finalize(
        text,
        "gb18030",
        confidence=0.3,
        errors=text.count(_REPLACEMENT_CHAR),
        used_fallback=True,
    )


def _finalize(
    text: str,
    encoding: str,
    *,
    confidence: float,
    errors: int,
    used_fallback: bool,
    had_bom: bool = False,
) -> DecodedText:
    newline = _dominant_newline(text)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return DecodedText(
        text=normalized,
        encoding=encoding,
        confidence=confidence,
        errors=errors,
        used_fallback=used_fallback,
        had_bom=had_bom,
        newline=newline,
    )


def _dominant_newline(text: str) -> str:
    remainder = text.replace("\r\n", "")
    counts = {
        "\r\n": text.count("\r\n"),
        "\r": remainder.count("\r"),
        "\n": remainder.count("\n"),
    }
    if not any(counts.values()):
        return "\n"
    return max(counts, key=lambda newline: counts[newline])
