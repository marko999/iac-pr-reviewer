"""Integration tests for the ``iac-compliance validate`` command."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from compliance_service.cli import app
from compliance_service.models import Finding, FindingSeverity, NormalizedResource
from compliance_service.service import ValidationResult

FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "examples" / "azure" / "storage_account"


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
    assert payload["summary"]["counts"]["high"] == 1
    assert payload["summary"]["counts"]["medium"] == 1

