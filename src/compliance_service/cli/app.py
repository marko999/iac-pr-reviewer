"""Command-line interface implementation for the compliance tooling."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence

from ..adapters import PlanLoaderError, PSRuleAdapter, RuleEvaluationError
from ..models import Finding, FindingSeverity, NormalizedResource
from ..normalization import ResourceNormalizer
from ..rules import RulePackManager
from ..service import ComplianceService, ValidationResult

SEVERITY_RANK = {
    FindingSeverity.INFO: 0,
    FindingSeverity.LOW: 1,
    FindingSeverity.MEDIUM: 2,
    FindingSeverity.HIGH: 3,
    FindingSeverity.CRITICAL: 4,
}


@dataclass(slots=True)
class ValidationReport:
    """Collection of findings plus contextual metadata."""

    findings: Sequence[Finding]
    metadata: Mapping[str, Any]

    @property
    def highest_severity(self) -> FindingSeverity | None:
        if not self.findings:
            return None
        return max(self.findings, key=lambda finding: SEVERITY_RANK[finding.severity]).severity

    def counts_by_severity(self) -> dict[str, int]:
        counts: MutableMapping[FindingSeverity, int] = {
            severity: 0 for severity in FindingSeverity
        }
        for finding in self.findings:
            counts[finding.severity] += 1
        return {severity.value: count for severity, count in counts.items()}

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": dict(self.metadata),
            "summary": {
                "total_findings": len(self.findings),
                "highest_severity": self.highest_severity.value if self.highest_severity else None,
                "counts": self.counts_by_severity(),
            },
            "findings": [_serialize_finding(finding) for finding in self.findings],
        }


def _serialize_finding(finding: Finding) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rule_id": finding.rule_id,
        "message": finding.message,
        "severity": finding.severity.value,
        "metadata": dict(finding.metadata),
    }

    if finding.resource:
        payload["resource"] = _serialize_resource(finding.resource)
    else:
        payload["resource"] = None

    return payload


def _serialize_resource(resource: NormalizedResource) -> dict[str, Any]:
    return {
        "address": resource.address,
        "module_path": list(resource.module_path),
        "type": resource.type,
        "name": resource.name,
        "provider_name": resource.provider_name,
        "mode": resource.mode,
        "index": resource.index,
        "change_action": resource.change_action.value,
    }


def render_table(report: ValidationReport) -> str:
    """Render findings as a simple text table for terminal output."""

    if not report.findings:
        return "No findings detected."

    headers = ("Severity", "Rule ID", "Resource", "Message")
    rows = [headers]
    for finding in report.findings:
        resource_address = finding.resource.address if finding.resource else "-"
        rows.append(
            (
                finding.severity.value,
                finding.rule_id,
                resource_address,
                finding.message,
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


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""

    parser = argparse.ArgumentParser(prog="iac-compliance", description="IaC compliance CLI")
    subparsers = parser.add_subparsers(dest="command")

    validate_parser = subparsers.add_parser(
        "validate", help="Validate Terraform plans and report compliance findings."
    )
    validate_parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=Path.cwd(),
        help="Path to the directory containing Terraform configuration or plan artifacts.",
    )
    validate_parser.add_argument(
        "--plan-json",
        type=Path,
        default=None,
        help="Path to an existing Terraform plan exported with `terraform show -json`.",
    )
    validate_parser.add_argument(
        "--plan-file",
        type=Path,
        default=None,
        help="Path to a binary Terraform plan file generated via `terraform plan -out`.",
    )
    validate_parser.add_argument(
        "--module",
        dest="modules",
        action="append",
        type=Path,
        default=None,
        help="Explicit module directories to evaluate instead of auto-discovery.",
    )
    validate_parser.add_argument(
        "--no-auto-discover",
        dest="auto_discover_modules",
        action="store_false",
        default=True,
        help=(
            "Disable module discovery and only evaluate the provided "
            "working directory or modules."
        ),
    )
    validate_parser.add_argument(
        "--var-file",
        dest="var_files",
        action="append",
        type=Path,
        default=None,
        help="Additional Terraform variable files to pass when generating a plan.",
    )
    validate_parser.add_argument(
        "--env",
        dest="env",
        action="append",
        default=None,
        metavar="KEY=VALUE",
        help="Environment variables to provide to Terraform/PSRule during execution.",
    )
    validate_parser.add_argument(
        "--inherit-env",
        action="store_true",
        help="Inherit the current environment instead of a minimal PATH-only sandbox.",
    )
    validate_parser.add_argument(
        "--terraform-bin",
        default="terraform",
        help="Name or path of the Terraform executable to use when generating plans.",
    )
    validate_parser.add_argument(
        "--terragrunt-bin",
        default="terragrunt",
        help="Name or path of the Terragrunt executable to use when generating plans.",
    )
    validate_parser.add_argument(
        "--force-terragrunt",
        action="store_true",
        help="Always use Terragrunt when executing plans, even without a terragrunt.hcl file.",
    )
    validate_parser.add_argument(
        "--rule-manifest",
        dest="rule_manifests",
        action="append",
        default=None,
        type=str,
        help="Path to a rule manifest YAML/JSON file describing enabled rule packs.",
    )
    validate_parser.add_argument(
        "--psrule-exec",
        default=None,
        help=(
            "Executable used to invoke PSRule for Azure. Defaults to the packaged "
            "PowerShell wrapper when omitted."
        ),
    )
    validate_parser.add_argument(
        "--fail-on",
        choices=[severity.value for severity in FindingSeverity],
        default=FindingSeverity.HIGH.value,
        help="Fail the run when findings at or above the provided severity are present.",
    )
    validate_parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format for validation results.",
    )

    return parser


def create_service(
    *,
    psrule_executable: str | None = None,
    default_rule_manifests: Sequence[str] | None = None,
) -> ComplianceService:
    """Create a compliance service instance using PSRule and Terraform adapters."""

    manager = RulePackManager()
    normalizer = ResourceNormalizer()

    default_manifests = list(default_rule_manifests or [])

    def factory(manifests: Sequence[str] | None) -> PSRuleAdapter:
        manifest_list = list(default_manifests)
        if manifests:
            manifest_list.extend(str(manifest) for manifest in manifests)
        return PSRuleAdapter(
            psrule_executable=psrule_executable,
            rule_pack_manager=manager,
            manifests=manifest_list,
        )

    return ComplianceService(rule_engine_factory=factory, normalizer=normalizer)


def _normalize_modules(base_dir: Path, modules: Sequence[Path] | None) -> Sequence[Path]:
    if not modules:
        return ()
    normalized: list[Path] = []
    for module in modules:
        candidate = module if module.is_absolute() else base_dir / module
        normalized.append(candidate.resolve())
    return normalized


def _parse_env_values(values: Sequence[str] | None) -> Mapping[str, str]:
    if not values:
        return {}

    env: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Environment variables must be in KEY=VALUE form: {value}")
        key, raw = value.split("=", 1)
        env[key] = raw
    return env


def _build_report(result: ValidationResult) -> ValidationReport:
    return ValidationReport(findings=result.findings, metadata=result.metadata)


def _format_report(
    report: ValidationReport,
    *,
    fail_on: FindingSeverity,
    output_format: str,
) -> tuple[str, bool]:
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


def _handle_validate(args: argparse.Namespace) -> int:
    try:
        env = _parse_env_values(args.env)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 2

    service = create_service(psrule_executable=args.psrule_exec)

    working_dir = args.path.resolve()
    plan_json = args.plan_json.resolve() if args.plan_json else None
    plan_file = args.plan_file.resolve() if args.plan_file else None
    modules = _normalize_modules(working_dir, args.modules)
    var_files = [path.resolve() for path in args.var_files] if args.var_files else None
    manifests = list(args.rule_manifests or [])

    try:
        result = service.validate(
            working_dir,
            plan_json_path=plan_json,
            plan_file_path=plan_file,
            module_paths=modules,
            auto_discover_modules=args.auto_discover_modules,
            var_files=var_files,
            env=env,
            inherit_environment=args.inherit_env,
            terraform_bin=args.terraform_bin,
            terragrunt_bin=args.terragrunt_bin,
            force_terragrunt=args.force_terragrunt,
            manifests=manifests,
            severity_threshold=FindingSeverity(args.fail_on),
        )
    except (PlanLoaderError, RuleEvaluationError) as exc:
        print(f"Error: {exc}")
        return 2

    report = _build_report(result)
    output, should_fail = _format_report(
        report,
        fail_on=FindingSeverity(args.fail_on),
        output_format=args.format,
    )

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
