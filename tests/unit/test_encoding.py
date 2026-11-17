"""Tests for byte decoding and encoding detection."""

from __future__ import annotations

import codecs
from pathlib import Path

import pytest

from txt2epub_cli.encoding import decode_bytes, read_text_file

UTF8_TEXT = "第一章\n这是正文。\n"


def test_decode_utf8() -> None:
    result = decode_bytes(UTF8_TEXT.encode("utf-8"))

    assert result.text == UTF8_TEXT
    assert result.encoding == "utf-8"
    assert result.confidence == 1.0
    assert result.errors == 0
    assert result.used_fallback is False
    assert result.had_bom is False
    assert result.newline == "\n"


def test_decode_utf8_bom() -> None:
    data = codecs.BOM_UTF8 + UTF8_TEXT.encode("utf-8")
    result = decode_bytes(data)

    assert result.text == UTF8_TEXT
    assert not result.text.startswith("\ufeff")
    assert result.encoding == "utf-8-sig"
    assert result.confidence == 1.0
    assert result.errors == 0
    assert result.used_fallback is False
    assert result.had_bom is True


@pytest.mark.parametrize(
    ("bom", "codec"),
    [
        (codecs.BOM_UTF16_LE, "utf-16-le"),
        (codecs.BOM_UTF16_BE, "utf-16-be"),
    ],
    ids=["utf-16-le", "utf-16-be"],
)
def test_decode_utf16_bom(bom: bytes, codec: str) -> None:
    data = bom + UTF8_TEXT.encode(codec)
    result = decode_bytes(data)

    assert result.text == UTF8_TEXT
    assert result.encoding == "utf-16"
    assert result.confidence == 1.0
    assert result.errors == 0
    assert result.used_fallback is False
    assert result.had_bom is True


def test_decode_gb18030() -> None:
    result = decode_bytes(UTF8_TEXT.encode("gb18030"))

    assert result.text == UTF8_TEXT
    assert result.encoding == "gb18030"
    assert result.confidence == 0.9
    assert result.errors == 0
    assert result.used_fallback is False
    assert result.had_bom is False


def test_decode_normalizes_crlf() -> None:
    result = decode_bytes("第一行\r\n第二行\r\n".encode())

    assert result.text == "第一行\n第二行\n"
    assert result.newline == "\r\n"


def test_decode_normalizes_lone_cr() -> None:
    result = decode_bytes(b"a\rb\rc")

    assert result.text == "a\nb\nc"
    assert result.newline == "\r"


def test_decode_mixed_newlines_uses_dominant() -> None:
    result = decode_bytes(b"a\r\nb\nc\r\nd\re")

    assert result.text == "a\nb\nc\nd\ne"
    assert result.newline == "\r\n"


def test_decode_without_newline_reports_lf() -> None:
    result = decode_bytes(b"abc")

    assert result.text == "abc"
    assert result.newline == "\n"


def test_invalid_utf8_falls_back_to_gb18030() -> None:
    result = decode_bytes(b"abc\xffdef")

    assert result.encoding == "gb18030"
    assert result.confidence == 0.3
    assert result.used_fallback is True
    assert result.errors == 1
    assert result.text == "abc\ufffddef"


def test_decode_empty_bytes() -> None:
    result = decode_bytes(b"")

    assert result.text == ""
    assert result.encoding == "utf-8"
    assert result.confidence == 1.0
    assert result.errors == 0
    assert result.used_fallback is False
    assert result.had_bom is False
    assert result.newline == "\n"


@pytest.mark.parametrize(
    ("data", "encoding"),
    [
        (codecs.BOM_UTF8, "utf-8-sig"),
        (codecs.BOM_UTF16_LE, "utf-16"),
        (codecs.BOM_UTF16_BE, "utf-16"),
    ],
    ids=["utf-8", "utf-16-le", "utf-16-be"],
)
def test_decode_bom_only(data: bytes, encoding: str) -> None:
    result = decode_bytes(data)

    assert result.text == ""
    assert result.encoding == encoding
    assert result.confidence == 1.0
    assert result.errors == 0
    assert result.used_fallback is False
    assert result.had_bom is True
    assert result.newline == "\n"


def test_forced_encoding_strict() -> None:
    data = "第一章".encode("gb18030")
    result = decode_bytes(data, forced_encoding="gb18030")

    assert result.text == "第一章"
    assert result.encoding == "gb18030"
    assert result.confidence == 1.0
    assert result.errors == 0
    assert result.used_fallback is False


def test_forced_encoding_normalizes_newlines() -> None:
    data = "甲\r\n乙".encode("gb18030")
    result = decode_bytes(data, forced_encoding="gb18030")

    assert result.text == "甲\n乙"
    assert result.newline == "\r\n"


def test_forced_encoding_falls_back_on_invalid_bytes() -> None:
    result = decode_bytes("第一章".encode("gb18030"), forced_encoding="utf-8")

    assert result.encoding == "utf-8"
    assert result.confidence == 0.5
    assert result.used_fallback is True
    assert result.errors > 0
    assert "\ufffd" in result.text


def test_forced_unknown_codec_raises_lookup_error() -> None:
    with pytest.raises(LookupError):
        decode_bytes(b"abc", forced_encoding="not-a-real-codec")


def test_read_text_file_detects_bom(tmp_path: Path) -> None:
    path = tmp_path / "book.txt"
    path.write_bytes(codecs.BOM_UTF8 + UTF8_TEXT.encode("utf-8"))

    result = read_text_file(path)

    assert result.text == UTF8_TEXT
    assert result.encoding == "utf-8-sig"
    assert result.had_bom is True


def test_read_text_file_honors_forced_encoding(tmp_path: Path) -> None:
    path = tmp_path / "book.txt"
    path.write_bytes("第一章".encode("gb18030"))

    result = read_text_file(path, forced_encoding="gb18030")

    assert result.text == "第一章"
    assert result.encoding == "gb18030"
    assert result.used_fallback is False
