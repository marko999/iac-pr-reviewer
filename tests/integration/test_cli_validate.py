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
from compliance_service.models import Finding, FindingSeverity, NormalizedResource
from compliance_service.service import ValidationResult

EXAMPLES_ROOT = Path(__file__).resolve().parents[2] / "examples" / "azure"
FINDINGS_FILENAME = "expected-findings.json"
SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2, "critical": 3}
SEVERITY_TRANSLATION = {
    "info": FindingSeverity.INFO.value,
    "warning": FindingSeverity.MEDIUM.value,
    "error": FindingSeverity.HIGH.value,
    "critical": FindingSeverity.CRITICAL.value,
}


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


@pytest.fixture(autouse=True)
def stub_service(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the compliance service with a fixture-backed stub."""

    def factory(**_: object) -> "StubService":
        return StubService()

    monkeypatch.setattr(app, "create_service", factory)


class StubService:
    """Service replacement that returns findings from fixture manifests."""

    _SEVERITY_MAP = {
        "info": FindingSeverity.INFO,
        "warning": FindingSeverity.MEDIUM,
        "error": FindingSeverity.HIGH,
        "critical": FindingSeverity.CRITICAL,
    }

    def validate(self, working_dir: Path, **_: object) -> ValidationResult:
        manifest_path = working_dir / "expected-findings.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        metadata = data.get("metadata", {})
        findings = [self._build_finding(item) for item in data.get("findings", [])]
        return ValidationResult(findings=findings, metadata=metadata)

    def _build_finding(self, payload: dict[str, object]) -> Finding:
        severity_value = str(payload.get("severity", "info")).lower()
        severity = self._SEVERITY_MAP.get(severity_value, FindingSeverity.INFO)
        resource_address = str(payload.get("resource", ""))
        resource = NormalizedResource(address=resource_address)
        message = str(payload.get("description") or payload.get("message") or "")
        return Finding(
            rule_id=str(payload.get("rule_id", "")),
            message=message,
            severity=severity,
            resource=resource,
            metadata={},
        )


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

    expected_findings = [
        {
            "rule_id": finding["rule_id"],
            "message": finding["description"],
            "severity": SEVERITY_TRANSLATION[finding["severity"]],
            "resource": finding["resource"],
        }
        for finding in expectations["non_compliant_manifest"]["findings"]
    ]
    actual_findings = [
        {
            "rule_id": finding["rule_id"],
            "message": finding["message"],
            "severity": finding["severity"],
            "resource": (finding.get("resource") or {}).get("address"),
        }
        for finding in payload["findings"]
    ]

    assert actual_findings == expected_findings
    assert payload["summary"]["total_findings"] == expectations["total_findings"]
    expected_highest = expectations["highest_severity"]
    if expected_highest is not None:
        expected_highest = SEVERITY_TRANSLATION[expected_highest]
    assert payload["summary"]["highest_severity"] == expected_highest

    expected_counts = {
        SEVERITY_TRANSLATION[severity]: count
        for severity, count in expectations["severity_counts"].items()
    }
    for severity, count in expected_counts.items():
        assert payload["summary"]["counts"].get(severity, 0) == count
