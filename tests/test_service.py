from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import pytest

from compliance_service.adapters import RuleEvaluationError
from compliance_service.models import Finding, FindingSeverity, NormalizedResource
from compliance_service.normalization import ResourceNormalizer
from compliance_service.service import ComplianceService, ValidationResult


class DummyPlanLoader:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def load_plan(self) -> dict[str, Any]:
        return {
            "resource_changes": [
                {
                    "address": "aws_s3_bucket.example",
                    "change": {"actions": ["create"]},
                }
            ]
        }


class DummyNormalizer(ResourceNormalizer):
    def normalize(self, plan: dict[str, Any]) -> list[NormalizedResource]:
        return [NormalizedResource(address="aws_s3_bucket.example")]


@dataclass
class DummyRuleEngine:
    findings: Sequence[Finding]

    def evaluate(
        self,
        resources: Sequence[NormalizedResource],
        *,
        severity_threshold: FindingSeverity | None = None,
    ) -> list[Finding]:
        self.resources = list(resources)
        self.threshold = severity_threshold
        return list(self.findings)


def test_compliance_service_runs_pipeline() -> None:
    expected_findings = [
        Finding(
            rule_id="RULE-1",
            message="Example message",
            severity=FindingSeverity.MEDIUM,
            resource=NormalizedResource(address="aws_s3_bucket.example"),
            metadata={"hint": "value"},
        )
    ]

    engine = DummyRuleEngine(expected_findings)

    service = ComplianceService(
        plan_loader_factory=DummyPlanLoader,
        normalizer=DummyNormalizer(),
        rule_engine_factory=lambda manifests: engine,
    )

    result = service.validate(
        Path("/workspace"),
        manifests=["rules.yaml"],
        severity_threshold=FindingSeverity.MEDIUM,
    )

    assert isinstance(result, ValidationResult)
    assert result.findings == expected_findings
    assert result.metadata["resource_count"] == 1
    assert engine.threshold == FindingSeverity.MEDIUM


def test_missing_rule_engine_factory_raises() -> None:
    service = ComplianceService(plan_loader_factory=DummyPlanLoader, normalizer=DummyNormalizer())

    with pytest.raises(RuleEvaluationError):
        service.validate(Path("."))

