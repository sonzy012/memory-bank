"""Tests for memory_bank.cli — CLI commands."""

from click.testing import CliRunner
from unittest.mock import patch

from memory_bank.cli import cli


@patch("memory_bank.cli.ingest_sessions")
def test_ingest_command(mock_ingest):
    mock_ingest.return_value = {"ingested": 2, "updated": 1, "skipped": 3}
    runner = CliRunner()
    result = runner.invoke(cli, ["ingest"])
    assert result.exit_code == 0
    assert "2 ingested" in result.output
    assert "1 updated" in result.output
    assert "3 skipped" in result.output


@patch("memory_bank.cli.ingest_sessions")
def test_ingest_include_locked_flag(mock_ingest):
    mock_ingest.return_value = {"ingested": 5, "updated": 0, "skipped": 0}
    runner = CliRunner()
    result = runner.invoke(cli, ["ingest", "--include-locked"])
    assert result.exit_code == 0
    mock_ingest.assert_called_once()
    _, kwargs = mock_ingest.call_args
    assert kwargs["include_locked"] is True
