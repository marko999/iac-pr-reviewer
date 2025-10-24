"""Rule engine adapter interfaces and implementations."""

from __future__ import annotations

import json
import subprocess
import tempfile
from abc import ABC, abstractmethod
from importlib import resources
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from ..models import Finding, FindingSeverity, NormalizedResource
from ..rules import RulePack, RulePackManager


class RuleEvaluationError(RuntimeError):
    """Raised when a rule engine fails to execute."""


class RuleEngineAdapter(ABC):
    """Abstract base class describing the rule engine contract."""

    @abstractmethod
    def evaluate(
        self,
        resources: Sequence[NormalizedResource],
        *,
        severity_threshold: FindingSeverity | None = None,
    ) -> List[Finding]:
        """Evaluate the supplied resources and return findings."""


class PSRuleAdapter(RuleEngineAdapter):
    """Adapter that shells out to the `ps-rule` CLI for Azure validation."""

    _SEVERITY_ORDER = {
        FindingSeverity.INFO: 0,
        FindingSeverity.LOW: 1,
        FindingSeverity.MEDIUM: 2,
        FindingSeverity.HIGH: 3,
        FindingSeverity.CRITICAL: 4,
    }

    _PSRULE_TO_FINDING = {
        "informational": FindingSeverity.INFO,
        "information": FindingSeverity.INFO,
        "info": FindingSeverity.INFO,
        "low": FindingSeverity.LOW,
        "minor": FindingSeverity.LOW,
        "warning": FindingSeverity.MEDIUM,
        "moderate": FindingSeverity.MEDIUM,
        "medium": FindingSeverity.MEDIUM,
        "advisory": FindingSeverity.MEDIUM,
        "major": FindingSeverity.HIGH,
        "important": FindingSeverity.HIGH,
        "high": FindingSeverity.HIGH,
        "error": FindingSeverity.HIGH,
        "critical": FindingSeverity.CRITICAL,
        "severe": FindingSeverity.CRITICAL,
        "fatal": FindingSeverity.CRITICAL,
    }

    def __init__(
        self,
        *,
        psrule_executable: str | None = None,
        rule_pack_manager: RulePackManager | None = None,
        manifests: Sequence[str] | None = None,
    ) -> None:
        if psrule_executable is None:
            self.psrule_executable = str(
                resources.files("compliance_service.rules") / "run_psrule.ps1"
            )
        else:
            self.psrule_executable = psrule_executable
        self.rule_pack_manager = rule_pack_manager or RulePackManager()
        self.manifests = list(manifests or [])

    # ------------------------------------------------------------------
    def evaluate(
        self,
        resources: Sequence[NormalizedResource],
        *,
        severity_threshold: FindingSeverity | None = None,
    ) -> List[Finding]:
        packs = self.rule_pack_manager.enabled_packs(self.manifests)
        payload = [self._serialize_resource(resource) for resource in resources]
        severity_overrides: Dict[str, FindingSeverity] = {}
        for pack in packs:
            severity_overrides.update(pack.severity_overrides)

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            json.dump(payload, handle)
            handle.flush()
            input_path = handle.name

        try:
            command = self._build_command(input_path, packs)
            result = subprocess.run(  # noqa: S603,S607 - deliberate invocation of external command
                command,
                capture_output=True,
                text=True,
            )
        finally:
            Path(input_path).unlink(missing_ok=True)

        if result.returncode != 0:
            raise RuleEvaluationError(result.stderr or "PSRule execution failed")

        findings = self._parse_results(
            result.stdout or "{}",
            resources,
            severity_overrides=severity_overrides,
        )

        if severity_threshold is None:
            return findings

        threshold_index = self._SEVERITY_ORDER.get(severity_threshold, 0)
        return [
            finding
            for finding in findings
            if self._SEVERITY_ORDER.get(finding.severity, 0) >= threshold_index
        ]

    # ------------------------------------------------------------------
    def _build_command(self, input_path: str, packs: Sequence[RulePack]) -> List[str]:
        command = [
            self.psrule_executable,
            "run",
            "--input-path",
            input_path,
            "--input-type",
            "terraform-plan",
            "--output-format",
            "json",
        ]

        for pack in packs:
            if pack.module:
                command.extend(["--module", pack.module])
            if pack.source:
                command.extend(["--source", pack.source])
            for key, value in pack.settings.items():
                command.extend(["--option", f"{key}={value}"])

        return command

    # ------------------------------------------------------------------
    def _parse_results(
        self,
        stdout: str,
        resources: Sequence[NormalizedResource],
        *,
        severity_overrides: Mapping[str, FindingSeverity] | None = None,
    ) -> List[Finding]:
        try:
            data = json.loads(stdout or "{}")
        except json.JSONDecodeError as exc:
            raise RuleEvaluationError("Failed to parse PSRule output") from exc

        results: Iterable[Mapping[str, Any]]
        if isinstance(data, Mapping):
            results = data.get("results", []) or []
        elif isinstance(data, list):
            results = data
        else:
            results = []

        resource_index: Dict[str, NormalizedResource] = {res.address: res for res in resources}

        findings: List[Finding] = []
        for entry in results:
            rule_id = str(entry.get("ruleId") or entry.get("rule") or "").strip()
            if not rule_id:
                continue

            severity = self._normalize_severity(entry.get("level") or entry.get("severity"))
            if severity_overrides and rule_id in severity_overrides:
                severity = severity_overrides[rule_id]
            message = str(entry.get("message") or entry.get("description") or "").strip()
            target_id = entry.get("targetId") or entry.get("target")
            target_address = str(target_id) if target_id else ""
            resource = resource_index.get(target_address)

            metadata = {
                "recommendation": entry.get("recommendation"),
                "link": entry.get("link"),
                "reference": entry.get("reference"),
                "data": entry.get("data"),
            }
            # Drop empty metadata entries
            metadata = {key: value for key, value in metadata.items() if value is not None}

            findings.append(
                Finding(
                    rule_id=rule_id,
                    message=message or rule_id,
                    severity=severity,
                    resource=resource,
                    metadata=metadata,
                )
            )

        return findings

    # ------------------------------------------------------------------
    def _normalize_severity(self, level: object) -> FindingSeverity:
        if isinstance(level, FindingSeverity):
            return level

        if isinstance(level, str):
            normalized = level.strip().lower()
            if normalized in self._PSRULE_TO_FINDING:
                return self._PSRULE_TO_FINDING[normalized]

        return FindingSeverity.INFO

    # ------------------------------------------------------------------
    def _serialize_resource(self, resource: NormalizedResource) -> Dict[str, Any]:
        return {
            "address": resource.address,
            "module_path": list(resource.module_path),
            "type": resource.type,
            "name": resource.name,
            "provider_name": resource.provider_name,
            "mode": resource.mode,
            "index": resource.index,
            "change_action": resource.change_action.value,
            "before": resource.before,
            "after": resource.after,
        }
