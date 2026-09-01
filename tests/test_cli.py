"""Tests for Typer CLI interface."""

from pathlib import Path

from typer.testing import CliRunner

from certified_dose.cli import app

runner = CliRunner()


def test_cli_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "certified-dose version 0.1.0" in result.stdout


def test_cli_simulate_basic() -> None:
    result = runner.invoke(app, ["simulate", "--steps", "25", "--seed", "123"])
    assert result.exit_code == 0
    assert "Simulation Benchmark" in result.stdout
    assert "Total Control Steps: 25" in result.stdout
    assert "0 VIOLATIONS" in result.stdout


def test_cli_simulate_csv_export(tmp_path: Path) -> None:
    csv_file = tmp_path / "telemetry_test.csv"
    result = runner.invoke(
        app, ["simulate", "--steps", "15", "--csv-export", str(csv_file)]
    )
    assert result.exit_code == 0
    assert csv_file.exists()

    content = csv_file.read_text(encoding="utf-8")
    assert "candidate_dose" in content
    assert "certified_dose" in content
    assert "certified_violated" in content


def test_cli_check_command() -> None:
    # Test safe dose
    res_safe = runner.invoke(
        app, ["check", "--dose", "22.0", "--turbidity", "25.0", "--limit", "1.0"]
    )
    assert res_safe.exit_code == 0
    assert "ACCEPTED" in res_safe.stdout

    # Test unsafe dose
    res_unsafe = runner.invoke(
        app, ["check", "--dose", "4.0", "--turbidity", "30.0", "--limit", "1.0"]
    )
    assert res_unsafe.exit_code == 0
    assert "REJECTED_CORRECTED" in res_unsafe.stdout


def test_cli_dashboard_invocation(monkeypatch) -> None:
    import subprocess
    from unittest.mock import MagicMock

    mock_run = MagicMock()
    monkeypatch.setattr(subprocess, "run", mock_run)

    result = runner.invoke(app, ["dashboard", "--port", "8502"])
    assert result.exit_code == 0
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "streamlit" in args
    assert "8502" in args
