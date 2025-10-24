"""Tests for GitHub Actions reporting helpers."""

from __future__ import annotations

from compliance_service.cli.github_reporting import format_summary, iter_annotations


def _build_report() -> dict[str, object]:
    return {
        "metadata": {"workspace": "iac-demo", "plan_path": "terraform/plan.json"},
        "summary": {
            "total_findings": 2,
            "highest_severity": "high",
            "counts": {
                "critical": 0,
                "high": 1,
                "medium": 1,
                "low": 0,
                "info": 0,
            },
        },
        "findings": [
            {
                "rule_id": "AZURE_001",
                "message": "Storage account should enforce HTTPS.",
                "severity": "high",
                "resource": {"address": "module.storage.azurerm_storage_account.main"},
            },
            {
                "rule_id": "AZURE_002",
                "message": "Enable diagnostics on the App Service.",
                "severity": "medium",
                "resource": {"address": "azurerm_app_service.example"},
            },
        ],
    }


def test_format_summary_includes_key_sections() -> None:
    """Rendered summaries should include metadata, counts, and findings."""

    summary = format_summary(_build_report())

    assert "# IaC Compliance Report" in summary
    assert "**Total findings:** 2" in summary
    assert "| High | 1 |" in summary
    assert "- **workspace:** iac-demo" in summary
    assert "Storage account should enforce HTTPS." in summary
    assert "_(Resource: `module.storage.azurerm_storage_account.main`)" in summary


def test_iter_annotations_maps_severity_levels() -> None:
    """Workflow commands should map severities to the correct annotation levels."""

    annotations = list(iter_annotations(_build_report()))

    assert annotations[0].startswith("::error")
    assert "Resource: module.storage.azurerm_storage_account.main" in annotations[0]

    assert annotations[1].startswith("::warning")
    assert "Enable diagnostics on the App Service." in annotations[1]
