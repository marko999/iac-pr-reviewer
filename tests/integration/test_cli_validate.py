"""Integration tests for the ``iac-compliance validate`` command."""

from __future__ import annotations

import io
import json
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest

from compliance_service.cli import app

EXAMPLES_ROOT = Path(__file__).resolve().parents[2] / "examples" / "azure"
FINDINGS_FILENAME = "expected-findings.json"
SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2, "critical": 3}


def _load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _discover_fixtures() -> dict[str, dict[str, Any]]:
    fixtures: dict[str, dict[str, Any]] = {}
    for fixture_dir in sorted(EXAMPLES_ROOT.iterdir()):
        if not fixture_dir.is_dir():
            continue

        name = fixture_dir.name
        compliant_manifest = _load_manifest(
            fixture_dir / "compliant" / FINDINGS_FILENAME
        )
        non_compliant_manifest = _load_manifest(
            fixture_dir / "non_compliant" / FINDINGS_FILENAME
        )

        findings = [
            {
                "rule_id": finding["rule_id"],
                "resource": finding["resource"],
                "severity": finding["severity"].lower(),
                "description": finding["description"],
            }
            for finding in non_compliant_manifest.get("findings", [])
        ]

        counts = Counter(finding["severity"] for finding in findings)
        highest_severity = None
        if findings:
            highest_severity = max(
                (finding["severity"] for finding in findings),
                key=lambda severity: SEVERITY_RANK[severity],
            )

        fixtures[name] = {
            "compliant_manifest": compliant_manifest,
            "non_compliant_manifest": {
                "metadata": non_compliant_manifest.get("metadata", {}),
                "findings": findings,
            },
            "total_findings": len(findings),
            "severity_counts": {
                severity: counts.get(severity, 0) for severity in SEVERITY_RANK
            },
            "highest_severity": highest_severity,
        }

    return fixtures


TRACK_F_FIXTURES = _discover_fixtures()


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
    assert (
        TRACK_F_FIXTURES[fixture_name]["compliant_manifest"].get("findings", []) == []
    )


@pytest.mark.parametrize("fixture_name", sorted(TRACK_F_FIXTURES))
def test_validate_non_compliant_triggers_failure(fixture_name: str) -> None:
    """Each non-compliant fixture should fail using the default fail-on threshold."""

    expectations = TRACK_F_FIXTURES[fixture_name]
    fixture_dir = EXAMPLES_ROOT / fixture_name / "non_compliant"
    exit_code, output = invoke_cli(["validate", str(fixture_dir)])

    assert exit_code == 1
    for finding in expectations["non_compliant_manifest"]["findings"]:
        assert finding["rule_id"] in output


@pytest.mark.parametrize("fixture_name", sorted(TRACK_F_FIXTURES))
def test_validate_respects_fail_on_threshold(fixture_name: str) -> None:
    """Raising the fail-on threshold should allow each fixture run to pass."""

    expectations = TRACK_F_FIXTURES[fixture_name]
    fixture_dir = EXAMPLES_ROOT / fixture_name / "non_compliant"
    exit_code, output = invoke_cli(["validate", str(fixture_dir), "--fail-on", "critical"])

    assert exit_code == 0
    for finding in expectations["non_compliant_manifest"]["findings"]:
        assert finding["rule_id"] in output


@pytest.mark.parametrize("fixture_name", sorted(TRACK_F_FIXTURES))
def test_validate_outputs_json_when_requested(fixture_name: str) -> None:
    """The CLI should return a structured JSON document when asked for any fixture."""

    expectations = TRACK_F_FIXTURES[fixture_name]
    fixture_dir = EXAMPLES_ROOT / fixture_name / "non_compliant"
    exit_code, output = invoke_cli(["validate", str(fixture_dir), "--format", "json"])

    assert exit_code == 1
    payload = json.loads(output)
    assert payload["metadata"] == expectations["non_compliant_manifest"]["metadata"]
    assert payload["findings"] == expectations["non_compliant_manifest"]["findings"]
    assert payload["summary"]["total_findings"] == expectations["total_findings"]
    assert payload["summary"]["highest_severity"] == expectations["highest_severity"]
    assert payload["summary"]["counts"] == expectations["severity_counts"]
