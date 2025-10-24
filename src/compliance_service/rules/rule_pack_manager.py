"""Utilities for loading and merging rule pack manifest files."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Sequence

from ..models import FindingSeverity

try:  # pragma: no cover - import guarded for optional dependency
    import yaml
except ModuleNotFoundError:  # pragma: no cover - handled in loader
    yaml = None  # type: ignore[assignment]


class RulePackError(RuntimeError):
    """Raised when rule pack manifests cannot be loaded or parsed."""


@dataclass(slots=True)
class RulePack:
    """Configuration describing a logical rule pack to execute."""

    name: str
    enabled: bool = True
    module: str | None = None
    source: str | None = None
    settings: Dict[str, Any] = field(default_factory=dict)
    severity_overrides: Dict[str, FindingSeverity] = field(default_factory=dict)


_DEFAULT_MANIFEST = Path(__file__).resolve().parent / "manifests" / "psrule.azure-baseline.yaml"


class RulePackManager:
    """Load rule pack manifests and expose enabled packs for rule engines."""

    def __init__(self, default_manifests: Sequence[Path | str] | None = None) -> None:
        manifest_paths: List[Path]
        if default_manifests is None:
            manifest_paths = []
            if _DEFAULT_MANIFEST.exists():
                manifest_paths.append(_DEFAULT_MANIFEST)
        else:
            manifest_paths = [Path(path) for path in default_manifests]

        self._default_manifests = manifest_paths

    # ------------------------------------------------------------------
    def load(self, manifests: Sequence[Path | str] | None = None) -> List[RulePack]:
        """Return all packs defined by the provided manifests."""

        manifest_paths = [Path(path) for path in self._default_manifests]
        if manifests:
            manifest_paths.extend(Path(path) for path in manifests)

        packs: MutableMapping[str, RulePack] = {}
        for manifest_path in manifest_paths:
            data = self._load_manifest(manifest_path)
            for pack_config in data.get("packs", []) or []:
                name = pack_config.get("name")
                if not name:
                    continue

                pack = packs.get(name, RulePack(name=name))
                if "enabled" in pack_config:
                    pack.enabled = bool(pack_config["enabled"])
                if pack_config.get("module"):
                    pack.module = str(pack_config["module"])
                if pack_config.get("source"):
                    pack.source = str(pack_config["source"])

                settings = pack_config.get("settings")
                if isinstance(settings, Mapping):
                    pack.settings.update(settings)

                severity = pack_config.get("severity")
                if isinstance(severity, Mapping):
                    for rule_id, level in severity.items():
                        if not isinstance(rule_id, str):
                            continue

                        severity_value: FindingSeverity | None
                        if isinstance(level, FindingSeverity):
                            severity_value = level
                        elif isinstance(level, str):
                            try:
                                severity_value = FindingSeverity(level.strip().lower())
                            except ValueError:
                                continue
                        else:
                            continue

                        pack.severity_overrides[rule_id.strip()] = severity_value

                packs[name] = pack

        return list(packs.values())

    # ------------------------------------------------------------------
    def enabled_packs(self, manifests: Sequence[Path | str] | None = None) -> List[RulePack]:
        """Return only the packs that are enabled after merging manifests."""

        return [pack for pack in self.load(manifests) if pack.enabled]

    # ------------------------------------------------------------------
    def _load_manifest(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            raise RulePackError(f"Rule pack manifest not found: {path}")

        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover - filesystem errors surfaced to caller
            raise RulePackError(f"Failed to read rule pack manifest {path}") from exc

        if yaml is not None:
            try:
                data = yaml.safe_load(content) or {}
            except yaml.YAMLError as exc:
                raise RulePackError(f"Invalid YAML in rule pack manifest {path}") from exc
        else:
            try:
                data = json.loads(content or "{}")
            except json.JSONDecodeError as exc:
                raise RulePackError(
                    "PyYAML is required to parse non-JSON rule manifests"
                ) from exc

        if not isinstance(data, Mapping):
            raise RulePackError(f"Rule pack manifest must be a mapping: {path}")

        return dict(data)
