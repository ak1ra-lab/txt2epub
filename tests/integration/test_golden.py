from __future__ import annotations

import json
from pathlib import Path

from txt2epub_cli.parser import parse_file

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "txt"
GOLDEN = ROOT / "golden" / "samples.json"


def test_fixture_golden_counts():
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))["fixtures"]
    assert sorted(expected) == sorted(path.name for path in FIXTURES.glob("*.txt"))
    for name, snapshot in expected.items():
        result = parse_file(FIXTURES / name)
        assert result.stats.volumes == snapshot["volumes"], name
        assert result.stats.chapters == snapshot["chapters"], name
        assert result.stats.sections == snapshot["sections"], name
        assert result.stats.specials == snapshot["specials"], name
        first = result.stats.first_heading.title if result.stats.first_heading else None
        last = result.stats.last_heading.title if result.stats.last_heading else None
        assert first == snapshot["first"], name
        assert last == snapshot["last"], name
        assert result.coverage.ok == snapshot["coverage_ok"], name
