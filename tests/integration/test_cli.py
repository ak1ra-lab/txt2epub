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
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "simple_arabic.epub").is_file()
    assert (tmp_path / "simple_chinese.epub").is_file()
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert len(payload["files"]) == 2
    assert payload["files"][0]["output"].endswith(".epub")
    assert payload["files"][0]["status"] == "converted"


def test_cli_convert_skips_existing_output(tmp_path: Path):
    output = tmp_path / "simple_arabic.epub"
    first = run_cli("convert", str(FIXTURES / "simple_arabic.txt"), "-o", str(tmp_path))
    assert first.returncode == 0, first.stderr
    original = output.read_bytes()

    second = run_cli(
        "convert", str(FIXTURES / "simple_arabic.txt"), "-o", str(tmp_path)
    )
    assert second.returncode == 0, second.stderr
    assert "SKIP" in second.stdout
    assert "overwrite?" not in second.stdout + second.stderr
    assert "Summary: 0 succeeded, 0 failed, 1 skipped" in second.stdout
    assert output.read_bytes() == original


def test_cli_convert_force_overwrites_existing_output(tmp_path: Path):
    import zipfile

    output = tmp_path / "simple_arabic.epub"
    first = run_cli("convert", str(FIXTURES / "simple_arabic.txt"), "-o", str(tmp_path))
    assert first.returncode == 0, first.stderr
    output.write_bytes(b"stale")

    skipped = run_cli(
        "convert", str(FIXTURES / "simple_arabic.txt"), "-o", str(tmp_path)
    )
    assert skipped.returncode == 0, skipped.stderr
    assert output.read_bytes() == b"stale"

    forced = run_cli(
        "convert",
        str(FIXTURES / "simple_arabic.txt"),
        "-o",
        str(tmp_path),
        "--force",
    )
    assert forced.returncode == 0, forced.stderr
    assert "Summary: 1 succeeded, 0 failed, 0 skipped" in forced.stdout
    assert zipfile.is_zipfile(output)


def test_cli_convert_summary_counts_success_failure_and_skip(tmp_path: Path):
    first = run_cli("convert", str(FIXTURES / "simple_arabic.txt"), "-o", str(tmp_path))
    assert first.returncode == 0, first.stderr

    report = tmp_path / "report.json"
    result = run_cli(
        "convert",
        str(FIXTURES / "simple_arabic.txt"),
        str(FIXTURES / "simple_chinese.txt"),
        str(tmp_path / "missing.txt"),
        "-o",
        str(tmp_path),
        "--report",
        str(report),
    )
    assert result.returncode == 1, result.stderr
    assert "Summary: 1 succeeded, 1 failed, 1 skipped" in result.stdout

    payload = json.loads(report.read_text(encoding="utf-8"))
    statuses = sorted(entry["status"] for entry in payload["files"])
    assert statuses == ["converted", "failed", "skipped"]


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
        ]
    )
    assert code == 0
    assert output.exists()


def test_cli_inspect_issue_filters(tmp_path: Path):
    path = tmp_path / "gaps.txt"
    path.write_text(
        "第1章 占位标题\n　　正文。\n第5章 占位标题\n　　正文。\n",
        encoding="utf-8",
    )

    verbose = run_cli("inspect", str(path), "--verbose")
    assert verbose.returncode == 0, verbose.stderr
    assert "number_gap" in verbose.stdout

    ignored = run_cli("inspect", str(path), "--verbose", "--ignore-issue", "number_gap")
    assert ignored.returncode == 0, ignored.stderr
    assert "number_gap" not in ignored.stdout

    only = run_cli("inspect", str(path), "--only-issue", "number_gap")
    assert only.returncode == 0, only.stderr
    assert "number_gap" in only.stdout


def test_cli_inspect_verbose_shows_all_issues(tmp_path: Path):
    path = tmp_path / "many_gaps.txt"
    path.write_text(
        "".join(f"第{n}章 占位标题\n　　这是占位正文。\n" for n in range(1, 32, 2)),
        encoding="utf-8",
    )

    limited = run_cli("inspect", str(path))
    assert limited.returncode == 0, limited.stderr
    assert "... " in limited.stdout
    assert "more (see --json)" in limited.stdout

    verbose = run_cli("inspect", str(path), "--verbose")
    assert verbose.returncode == 0, verbose.stderr
    assert "number_gap" in verbose.stdout
    assert "more (see --json)" not in verbose.stdout


def test_cli_convert_rejects_non_positive_split_size(tmp_path: Path):
    result = run_cli(
        "convert",
        str(FIXTURES / "simple_arabic.txt"),
        "-o",
        str(tmp_path),
        "--split-size",
        "0",
    )
    assert result.returncode == 3
    assert "--split-size must be positive" in result.stderr
    assert not list(tmp_path.glob("*.epub"))


def test_cli_convert_no_indent_css(tmp_path: Path):
    result = run_cli(
        "convert",
        str(FIXTURES / "simple_arabic.txt"),
        "-o",
        str(tmp_path),
        "--no-indent",
    )
    assert result.returncode == 0, result.stderr
    import zipfile

    with zipfile.ZipFile(tmp_path / "simple_arabic.epub") as archive:
        css = archive.read("OEBPS/style.css").decode("utf-8")
        assert "text-indent: 0" in css
