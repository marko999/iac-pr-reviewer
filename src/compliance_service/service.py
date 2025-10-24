"""Orchestration layer used by the CLI to execute compliance validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, MutableMapping, Sequence

from .adapters import PlanLoader, PlanLoaderError, RuleEngineAdapter, RuleEvaluationError
from .models import Finding, FindingSeverity
from .normalization import ResourceNormalizer


@dataclass(slots=True)
class ValidationResult:
    """Result returned by :class:`ComplianceService` runs."""

    findings: list[Finding]
    metadata: Mapping[str, Any]


PlanLoaderFactory = Callable[..., PlanLoader]
RuleEngineFactory = Callable[[Sequence[str] | None], RuleEngineAdapter]


class ComplianceService:
    """High level service responsible for plan ingestion and rule evaluation."""

    def __init__(
        self,
        *,
        plan_loader_factory: PlanLoaderFactory | None = None,
        normalizer: ResourceNormalizer | None = None,
        rule_engine_factory: RuleEngineFactory | None = None,
    ) -> None:
        self._plan_loader_factory = plan_loader_factory or PlanLoader
        self._normalizer = normalizer or ResourceNormalizer()
        self._rule_engine_factory = rule_engine_factory

    # ------------------------------------------------------------------
    def validate(
        self,
        working_dir: Path,
        *,
        plan_json_path: Path | None = None,
        plan_file_path: Path | None = None,
        module_paths: Sequence[Path] | None = None,
        auto_discover_modules: bool = True,
        var_files: Sequence[Path] | None = None,
        env: Mapping[str, str] | None = None,
        inherit_environment: bool = False,
        terraform_bin: str = "terraform",
        terragrunt_bin: str = "terragrunt",
        force_terragrunt: bool = False,
        manifests: Sequence[str] | None = None,
        severity_threshold: FindingSeverity | None = None,
    ) -> ValidationResult:
        """Execute a validation run and return the resulting findings."""

        loader_kwargs: MutableMapping[str, Any] = {
            "working_dir": working_dir,
            "plan_json_path": plan_json_path,
            "plan_file_path": plan_file_path,
            "auto_discover_modules": auto_discover_modules,
            "inherit_environment": inherit_environment,
            "terraform_bin": terraform_bin,
            "terragrunt_bin": terragrunt_bin,
            "force_terragrunt": force_terragrunt,
        }

        if module_paths:
            loader_kwargs["module_paths"] = list(module_paths)
        if var_files:
            loader_kwargs["var_files"] = list(var_files)
        if env:
            loader_kwargs["env"] = dict(env)

        loader = self._plan_loader_factory(**loader_kwargs)
        plan = loader.load_plan()

        resources = self._normalizer.normalize(plan)

        rule_engine = self._resolve_rule_engine(manifests)
        findings = rule_engine.evaluate(resources, severity_threshold=severity_threshold)

        metadata: dict[str, Any] = {
            "working_dir": str(working_dir),
            "resource_count": len(resources),
        }

        return ValidationResult(findings=list(findings), metadata=metadata)

    # ------------------------------------------------------------------
    def _resolve_rule_engine(self, manifests: Sequence[str] | None) -> RuleEngineAdapter:
        if self._rule_engine_factory is None:
            raise RuleEvaluationError("No rule engine factory configured for compliance service")

        return self._rule_engine_factory(manifests)


__all__ = ["ComplianceService", "ValidationResult", "PlanLoaderError", "RuleEvaluationError"]

