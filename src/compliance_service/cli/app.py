"""Command-line interface implementation for the compliance tooling."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

FINDINGS_FILENAME = "expected-findings.json"


class Severity(str, Enum):
    """Supported finding severities ordered from lowest to highest impact."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


SEVERITY_RANK = {
    Severity.INFO: 0,
    Severity.WARNING: 1,
    Severity.ERROR: 2,
    Severity.CRITICAL: 3,
}


@dataclass(slots=True)
class Finding:
    """Represents a single compliance finding emitted by the rule engine."""

    rule_id: str
    resource: str
    severity: Severity
    description: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Finding":
        try:
            severity = Severity(data["severity"].lower())
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise ValueError("Finding missing severity field") from exc
        except ValueError as exc:
            raise ValueError(f"Unsupported severity value: {data.get('severity')}") from exc

        return cls(
            rule_id=data["rule_id"],
            resource=data["resource"],
            severity=severity,
            description=data["description"],
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "resource": self.resource,
            "severity": self.severity.value,
            "description": self.description,
        }


@dataclass(slots=True)
class ValidationReport:
    """Collection of findings plus contextual metadata."""

    findings: list[Finding]
    metadata: dict[str, Any]

    @property
    def highest_severity(self) -> Severity | None:
        if not self.findings:
            return None
        return max(self.findings, key=lambda finding: SEVERITY_RANK[finding.severity]).severity

    def counts_by_severity(self) -> dict[str, int]:
        counts: dict[Severity, int] = {severity: 0 for severity in Severity}
        for finding in self.findings:
            counts[finding.severity] += 1
        return {severity.value: count for severity, count in counts.items()}

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata,
            "summary": {
                "total_findings": len(self.findings),
                "highest_severity": self.highest_severity.value if self.highest_severity else None,
                "counts": self.counts_by_severity(),
            },
            "findings": [finding.to_dict() for finding in self.findings],
        }


def load_report(target: Path) -> ValidationReport:
    """Load the validation report from a directory or JSON file."""

    manifest_path = target
    if target.is_dir():
        manifest_path = target / FINDINGS_FILENAME

    if not manifest_path.exists():
        raise ValueError(
            f"No validation manifest found at {manifest_path}. Expected {FINDINGS_FILENAME}."
        )

    try:
        payload = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:  # pragma: no cover - user error path
        raise ValueError(f"Invalid JSON in {manifest_path}: {exc}") from exc

    findings = [Finding.from_dict(item) for item in payload.get("findings", [])]
    metadata = payload.get("metadata", {})
    return ValidationReport(findings=findings, metadata=metadata)


def render_table(report: ValidationReport) -> str:
    """Render findings as a simple text table for terminal output."""

    if not report.findings:
        return "No findings detected."

    headers = ("Severity", "Rule ID", "Resource", "Description")
    rows = [headers]
    for finding in report.findings:
        rows.append(
            (
                finding.severity.value,
                finding.rule_id,
                finding.resource,
                finding.description,
            )
        )

    widths = [max(len(str(row[idx])) for row in rows) for idx in range(len(headers))]

    def format_row(values: tuple[str, str, str, str]) -> str:
        return "  ".join(value.ljust(width) for value, width in zip(values, widths, strict=True))

    lines = [format_row(headers)]
    lines.append("  ".join("=" * width for width in widths))
    for row in rows[1:]:
        lines.append(format_row(row))
    return "\n".join(lines)


def run_validation(
    report: ValidationReport, fail_on: Severity, output_format: str
) -> tuple[str, bool]:
    """Return the rendered output and whether the run should fail."""

    if output_format not in {"table", "json"}:
        raise ValueError("format must be either 'table' or 'json'")

    highest = report.highest_severity
    should_fail = False
    if highest is not None:
        should_fail = SEVERITY_RANK[highest] >= SEVERITY_RANK[fail_on]

    if output_format == "json":
        output = json.dumps(report.to_dict(), indent=2)
    else:
        output = render_table(report)

    return output, should_fail


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""

    parser = argparse.ArgumentParser(prog="iac-compliance", description="IaC compliance CLI")
    subparsers = parser.add_subparsers(dest="command")

    validate_parser = subparsers.add_parser(
        "validate", help="Validate Terraform plans or fixtures and report compliance findings."
    )
    validate_parser.add_argument(
        "path",
        type=Path,
        help="Path to a directory containing expected-findings.json or to a JSON file itself.",
    )
    validate_parser.add_argument(
        "--fail-on",
        choices=[severity.value for severity in Severity],
        default=Severity.ERROR.value,
        help="Fail the run when findings at or above the provided severity are present.",
    )
    validate_parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format for validation results.",
    )

    return parser


def _handle_validate(args: argparse.Namespace) -> int:
    try:
        report = load_report(args.path)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 2

    output, should_fail = run_validation(report, Severity(args.fail_on), args.format)
    print(output)
    return 1 if should_fail else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point used by tests and the ``python -m`` invocation."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        return _handle_validate(args)

    parser.print_help()
    return 0


def run() -> None:  # pragma: no cover - thin wrapper for module execution
    """Execute the CLI and exit with the produced status code."""

    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover - module execution guard
    run()
