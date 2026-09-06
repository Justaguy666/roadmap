"""Tests for CLI quota command."""

import json

from typer.testing import CliRunner

from roadmap.cli.app import app

runner = CliRunner()


def test_quota_cli_text() -> None:
    result = runner.invoke(app, ["quota"])
    assert result.exit_code == 0
    assert "LLM Application Budget" in result.stdout
    assert "Workflow Allocations (Daily)" in result.stdout
    assert "Upstream Provider Health & Status" in result.stdout


def test_quota_cli_json() -> None:
    result = runner.invoke(app, ["quota", "--json"])
    assert result.exit_code == 0
    # Extract JSON string which begins at first '{' and ends at last '}'
    start = result.stdout.find("{")
    end = result.stdout.rfind("}") + 1
    json_str = result.stdout[start:end]
    data = json.loads(json_str)
    assert "global_budget" in data
    assert "workflow_budgets" in data
    assert "provider_states" in data
    assert "allocated" in data["global_budget"]
