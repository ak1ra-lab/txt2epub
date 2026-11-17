from __future__ import annotations

import os
from pathlib import Path

import pytest

from txt2epub_cli.model import Disposition
from txt2epub_cli.parser import parse_file

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "examples" / "txt"


@pytest.mark.local
@pytest.mark.skipif(
    os.environ.get("TXT2EPUB_LOCAL_SAMPLES") != "1",
    reason="set TXT2EPUB_LOCAL_SAMPLES=1 to run local sample smoke tests",
)
def test_local_samples_generic_invariants():
    paths = sorted(SAMPLES.glob("*.txt"))
    assert paths, f"no local samples under {SAMPLES}"
    for path in paths:
        result = parse_file(path)
        assert result.coverage.ok, (
            path.name,
            result.coverage.missing,
            result.coverage.extra,
        )
        assert result.headings, path.name
        assert not [
            line for line in result.ledger if line.disposition is Disposition.UNATTACHED
        ], path.name
