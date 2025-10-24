"""Integration tests for the ``iac-compliance validate`` command."""

from __future__ import annotations

import json
import io
from contextlib import redirect_stdout
from pathlib import Path

from compliance_service.cli import app

FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "examples" / "azure" / "storage_account"


def invoke_cli(args: list[str]) -> tuple[int, str]:
    """Execute the CLI with the provided arguments and capture stdout."""

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = app.main(args)
    return exit_code, stdout.getvalue()


def test_validate_compliant_fixture_passes() -> None:
    """The compliant fixture should produce no findings and exit successfully."""

    fixture_dir = FIXTURES_ROOT / "compliant"
    exit_code, output = invoke_cli(["validate", str(fixture_dir)])

    assert exit_code == 0, output
    assert "No findings detected." in output


def test_validate_non_compliant_triggers_failure() -> None:
    """The non-compliant fixture should fail using the default fail-on threshold."""

    fixture_dir = FIXTURES_ROOT / "non_compliant"
    exit_code, output = invoke_cli(["validate", str(fixture_dir)])

    assert exit_code == 1
    assert "AZR-STR-001" in output


def test_validate_respects_fail_on_threshold() -> None:
    """Raising the fail-on threshold should allow the run to pass."""

    fixture_dir = FIXTURES_ROOT / "non_compliant"
    exit_code, output = invoke_cli(["validate", str(fixture_dir), "--fail-on", "critical"])

    assert exit_code == 0
    assert "AZR-STR-001" in output


def test_validate_outputs_json_when_requested() -> None:
    """The CLI should return a structured JSON document when asked."""

    fixture_dir = FIXTURES_ROOT / "non_compliant"
    exit_code, output = invoke_cli(["validate", str(fixture_dir), "--format", "json"])

    assert exit_code == 1
    payload = json.loads(output)
    assert payload["summary"]["total_findings"] == 2
    assert payload["summary"]["counts"]["error"] == 1
    assert payload["summary"]["counts"]["warning"] == 1
