"""Helpers for publishing compliance findings to GitHub Actions surfaces."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Sequence, Tuple

SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]
ANNOTATION_LEVELS = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "notice",
    "info": "notice",
}


def _normalize_counts(raw_counts: Mapping[str, int] | None) -> MutableMapping[str, int]:
    counts: MutableMapping[str, int] = {severity: 0 for severity in SEVERITY_ORDER}
    if not raw_counts:
        return counts
    for severity, value in (raw_counts or {}).items():
        severity_key = str(severity).lower()
        if severity_key in counts:
            counts[severity_key] = int(value)
    return counts


def format_summary(report: Mapping[str, object]) -> str:
    """Render a Markdown job summary for the provided report."""

    summary: Mapping[str, object] = report.get("summary") or {}
    metadata: Mapping[str, object] = report.get("metadata") or {}
    findings: Sequence[Mapping[str, object]] = report.get("findings") or []

    total_findings = int(summary.get("total_findings", 0))
    highest = summary.get("highest_severity")
    highest_display = str(highest).title() if highest else "None"

    counts = _normalize_counts(summary.get("counts"))

    lines: list[str] = [
        "# IaC Compliance Report",
        "",
        f"**Total findings:** {total_findings}",
        f"**Highest severity:** {highest_display}",
        "",
        "| Severity | Findings |",
        "| --- | ---: |",
    ]

    for severity in SEVERITY_ORDER:
        lines.append(f"| {severity.title()} | {counts[severity]} |")

    if metadata:
        lines.extend(["", "## Metadata", ""])
        for key in sorted(metadata):
            value = metadata[key]
            lines.append(f"- **{key}:** {value}")

    if findings:
        lines.extend(["", "## Findings", ""])
        display_limit = 10
        for finding in findings[:display_limit]:
            severity = str(finding.get("severity", "info")).lower()
            rule_id = str(finding.get("rule_id", "")).strip()
            message = str(finding.get("message", "")).strip()
            resource = finding.get("resource") or {}
            resource_address = str(resource.get("address", "")).strip()

            bullet = f"- **{severity.title()}**"
            if rule_id:
                bullet += f" `{rule_id}`"
            if message:
                bullet += f" – {message}"
            if resource_address:
                bullet += f" _(Resource: `{resource_address}`)_"
            lines.append(bullet)

        remaining = len(findings) - display_limit
        if remaining > 0:
            lines.append(f"- ...and {remaining} more findings.")

    lines.append("")
    return "\n".join(lines)


def iter_annotations(report: Mapping[str, object]) -> Iterable[str]:
    """Generate GitHub Actions workflow command annotations for the findings."""

    findings: Sequence[Mapping[str, object]] = report.get("findings") or []
    for finding in findings:
        severity = str(finding.get("severity", "info")).lower()
        level = ANNOTATION_LEVELS.get(severity, "notice")
        rule_id = str(finding.get("rule_id", "")).strip()
        message = str(finding.get("message", "")).strip()
        resource = finding.get("resource") or {}
        resource_address = str(resource.get("address", "")).strip()
        metadata: Mapping[str, object] = finding.get("metadata") or {}

        file_path, line, end_line, column, end_column = _extract_annotation_location(metadata)

        title_parts: list[str] = []
        if severity:
            title_parts.append(severity.title())
        if rule_id:
            title_parts.append(rule_id)
        title = " - ".join(title_parts)

        body_parts = [message] if message else []
        if resource_address:
            body_parts.append(f"Resource: {resource_address}")
        if not body_parts:
            body_parts.append("Compliance finding reported without message.")

        body = "; ".join(body_parts)
        body = body.replace("%", "%25").replace("\r", "").replace("\n", "%0A")

        attributes: list[str] = []
        if file_path:
            attributes.append(f"file={file_path}")
        if line is not None:
            attributes.append(f"line={line}")
        if end_line is not None and end_line != line:
            attributes.append(f"endLine={end_line}")
        if column is not None:
            attributes.append(f"col={column}")
        if end_column is not None and (end_column != column or column is None):
            attributes.append(f"endColumn={end_column}")
        if title:
            attributes.append(f"title={title}")

        attribute_segment = ""
        if attributes:
            attribute_segment = " " + ",".join(attributes)

        yield f"::{level}{attribute_segment}::{body}"


def _extract_annotation_location(
    metadata: Mapping[str, object]
) -> Tuple[str | None, int | None, int | None, int | None, int | None]:
    """Extract file and position details from finding metadata."""

    if not isinstance(metadata, Mapping):
        return None, None, None, None, None

    file_path = _first_non_empty_str(
        metadata,
        "file_path",
        "filepath",
        "file",
        "path",
        "source_file",
        "target_file",
    )
    line = _coerce_int(_first_value(metadata, "line", "line_number", "start_line", "source_line"))
    end_line = _coerce_int(_first_value(metadata, "end_line", "end_line_number", "stop_line"))
    column = _coerce_int(
        _first_value(metadata, "column", "col", "start_column", "column_number", "source_column")
    )
    end_column = _coerce_int(_first_value(metadata, "end_column", "end_col", "stop_column"))

    for nested_key in ("source", "location", "range"):
        nested = metadata.get(nested_key)
        if isinstance(nested, Mapping):
            nested_path, nested_line, nested_end_line, nested_col, nested_end_col = (
                _extract_annotation_location(nested)
            )
            if not file_path:
                file_path = nested_path
            if line is None:
                line = nested_line
            if end_line is None:
                end_line = nested_end_line
            if column is None:
                column = nested_col
            if end_column is None:
                end_column = nested_end_col

    return file_path, line, end_line, column, end_column


def _first_value(metadata: Mapping[str, object], *keys: str) -> object | None:
    for key in keys:
        if key in metadata:
            value = metadata[key]
            if value is not None:
                return value
    return None


def _first_non_empty_str(metadata: Mapping[str, object], *keys: str) -> str | None:
    value = _first_value(metadata, *keys)
    if isinstance(value, str):
        trimmed = value.strip()
        if trimmed:
            return trimmed
    return None


def _coerce_int(value: object | None) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(stripped)
        except ValueError:
            return None
    return None


def _load_report(path: Path) -> Mapping[str, object]:
    raw = path.read_text(encoding="utf-8-sig")
    if not raw.strip():
        return {}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Failed to parse report JSON from '{path}': {exc.msg}.") from exc

    if not isinstance(data, Mapping):
        raise ValueError("Report JSON must be an object.")
    return data


def _write_summary(report: Mapping[str, object], destination: Path | None) -> None:
    if destination is None:
        return

    content = format_summary(report)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as handle:
        handle.write(content)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Publish compliance findings as GitHub job summary and annotations."
    )
    parser.add_argument("report", type=Path, help="Path to the compliance report JSON file.")
    parser.add_argument(
        "--summary-path",
        type=Path,
        default=None,
        help="Optional explicit path for the GitHub job summary output.",
    )

    args = parser.parse_args(argv)

    summary_path = args.summary_path
    if summary_path is None:
        summary_env = os.getenv("GITHUB_STEP_SUMMARY")
        if summary_env:
            summary_path = Path(summary_env)

    report = _load_report(args.report)

    _write_summary(report, summary_path)

    for command in iter_annotations(report):
        print(command)

    return 0


def run() -> None:  # pragma: no cover - wrapper for console entry point
    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover - module execution guard
    run()
