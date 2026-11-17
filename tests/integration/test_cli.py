from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "txt"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "txt2epub_cli", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_version():
    result = run_cli("--version")
    assert result.returncode == 0
    assert "txt2epub" in result.stdout


def test_cli_inspect_json():
    result = run_cli("inspect", str(FIXTURES / "simple_arabic.txt"), "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == 1
    assert payload["stats"]["chapters"] == 3
    assert payload["coverage"]["ok"] is True


def test_cli_inspect_batch_json():
    result = run_cli(
        "inspect",
        str(FIXTURES / "simple_arabic.txt"),
        str(FIXTURES / "simple_chinese.txt"),
        "--json",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert len(payload["files"]) == 2


def test_cli_convert_batch_and_report(tmp_path: Path):
    result = run_cli(
        "convert",
        str(FIXTURES / "simple_arabic.txt"),
        str(FIXTURES / "simple_chinese.txt"),
        "-o",
        str(tmp_path),
        "--report",
        str(tmp_path / "report.json"),
        "--yes",
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "simple_arabic.epub").is_file()
    assert (tmp_path / "simple_chinese.epub").is_file()
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert len(payload["files"]) == 2
    assert payload["files"][0]["output"].endswith(".epub")


def test_cli_dry_run_writes_nothing(tmp_path: Path):
    result = run_cli(
        "convert",
        str(FIXTURES / "simple_arabic.txt"),
        "-o",
        str(tmp_path),
        "--dry-run",
    )
    assert result.returncode == 0, result.stderr
    assert "DRY" in result.stdout
    assert not list(tmp_path.glob("*.epub"))


def test_cli_rules_error_exit_code(tmp_path: Path):
    rules = tmp_path / "bad.toml"
    rules.write_text("bad = [\n", encoding="utf-8")
    result = run_cli(
        "inspect", str(FIXTURES / "simple_arabic.txt"), "--rules", str(rules)
    )
    assert result.returncode == 3
    assert "rules error" in result.stderr


def test_cli_strict_profile_rejects_no_separator():
    result = run_cli(
        "inspect", str(FIXTURES / "no_separator.txt"), "--profile", "strict"
    )
    assert result.returncode == 0, result.stderr
    assert "0 chapters" in result.stdout


def test_convert_refuses_coverage_loss_unless_allowed(monkeypatch, tmp_path: Path):
    from txt2epub_cli import cli
    from txt2epub_cli.parser import parse_file

    result = parse_file(FIXTURES / "simple_arabic.txt")
    result.coverage.ok = False
    monkeypatch.setattr(cli, "parse_file", lambda *args, **kwargs: result)

    output = tmp_path / "simple_arabic.epub"
    code = cli.main(
        ["convert", str(FIXTURES / "simple_arabic.txt"), "-o", str(tmp_path)]
    )
    assert code == 2
    assert not output.exists()

    code = cli.main(
        [
            "convert",
            str(FIXTURES / "simple_arabic.txt"),
            "-o",
            str(tmp_path),
            "--allow-loss",
            "--yes",
        ]
    )
    assert code == 0
    assert output.exists()
