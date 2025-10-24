"""Integration tests for the ``iac-compliance validate`` command."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from compliance_service.cli import app

EXAMPLES_ROOT = Path(__file__).resolve().parents[2] / "examples" / "azure"

TRACK_F_FIXTURES = {
    "storage_account": {
        "error_rule": "AZR-STR-001",
        "total_findings": 2,
        "severity_counts": {"error": 1, "warning": 1},
    },
    "app_service": {
        "error_rule": "AZR-WEB-001",
        "total_findings": 2,
        "severity_counts": {"error": 1, "warning": 1},
    },
    "key_vault": {
        "error_rule": "AZR-KV-001",
        "total_findings": 2,
        "severity_counts": {"error": 1, "warning": 1},
    },
    "sql_server": {
        "error_rule": "AZR-SQL-001",
        "total_findings": 2,
        "severity_counts": {"error": 1, "warning": 1},
    },
}


def invoke_cli(args: list[str]) -> tuple[int, str]:
    """Execute the CLI with the provided arguments and capture stdout."""

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = app.main(args)
    return exit_code, stdout.getvalue()


@pytest.mark.parametrize("fixture_name", sorted(TRACK_F_FIXTURES))
def test_validate_compliant_fixture_passes(fixture_name: str) -> None:
    """Each compliant fixture should produce no findings and exit successfully."""

    fixture_dir = EXAMPLES_ROOT / fixture_name / "compliant"
    exit_code, output = invoke_cli(["validate", str(fixture_dir)])

    assert exit_code == 0, output
    assert "No findings detected." in output


@pytest.mark.parametrize("fixture_name", sorted(TRACK_F_FIXTURES))
def test_validate_non_compliant_triggers_failure(fixture_name: str) -> None:
    """Each non-compliant fixture should fail using the default fail-on threshold."""

    expectations = TRACK_F_FIXTURES[fixture_name]
    fixture_dir = EXAMPLES_ROOT / fixture_name / "non_compliant"
    exit_code, output = invoke_cli(["validate", str(fixture_dir)])

    assert exit_code == 1
    assert expectations["error_rule"] in output


@pytest.mark.parametrize("fixture_name", sorted(TRACK_F_FIXTURES))
def test_validate_respects_fail_on_threshold(fixture_name: str) -> None:
    """Raising the fail-on threshold should allow each fixture run to pass."""

    expectations = TRACK_F_FIXTURES[fixture_name]
    fixture_dir = EXAMPLES_ROOT / fixture_name / "non_compliant"
    exit_code, output = invoke_cli(["validate", str(fixture_dir), "--fail-on", "critical"])

    assert exit_code == 0
    assert expectations["error_rule"] in output


@pytest.mark.parametrize("fixture_name", sorted(TRACK_F_FIXTURES))
def test_validate_outputs_json_when_requested(fixture_name: str) -> None:
    """The CLI should return a structured JSON document when asked for any fixture."""

    expectations = TRACK_F_FIXTURES[fixture_name]
    fixture_dir = EXAMPLES_ROOT / fixture_name / "non_compliant"
    exit_code, output = invoke_cli(["validate", str(fixture_dir), "--format", "json"])

    assert exit_code == 1
    payload = json.loads(output)
    assert payload["summary"]["total_findings"] == expectations["total_findings"]
    for severity, count in expectations["severity_counts"].items():
        assert payload["summary"]["counts"][severity] == count
