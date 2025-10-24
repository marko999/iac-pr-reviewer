import json
from pathlib import Path

import pytest

from compliance_service.rules import RulePackError, RulePackManager


def write_manifest(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_merges_default_and_override_manifests(tmp_path: Path):
    default_manifest = write_manifest(
        tmp_path,
        "defaults.yaml",
        json.dumps(
            {
                "packs": [
                    {
                        "name": "azureBaseline",
                        "enabled": True,
                        "module": "PSRule.Rules.Azure",
                        "source": "baseline.yaml",
                        "settings": {"severity": "Major"},
                    }
                ]
            },
            indent=2,
        ),
    )

    override_manifest = write_manifest(
        tmp_path,
        "override.yaml",
        json.dumps(
            {
                "packs": [
                    {
                        "name": "azureBaseline",
                        "enabled": False,
                        "settings": {"severity": "Critical"},
                    },
                    {"name": "azureNaming", "module": "Custom.Rules.Naming"},
                ]
            },
            indent=2,
        ),
    )

    manager = RulePackManager(default_manifests=[default_manifest])
    packs = manager.load([override_manifest])

    packs_by_name = {pack.name: pack for pack in packs}
    assert set(packs_by_name) == {"azureBaseline", "azureNaming"}

    baseline = packs_by_name["azureBaseline"]
    assert baseline.enabled is False
    assert baseline.module == "PSRule.Rules.Azure"
    assert baseline.source == "baseline.yaml"
    assert baseline.settings["severity"] == "Critical"

    naming = packs_by_name["azureNaming"]
    assert naming.enabled is True
    assert naming.module == "Custom.Rules.Naming"

    enabled = manager.enabled_packs([override_manifest])
    assert [pack.name for pack in enabled] == ["azureNaming"]


def test_missing_manifest_raises(tmp_path: Path):
    manager = RulePackManager()
    with pytest.raises(RulePackError):
        manager.load([tmp_path / "missing.yaml"])
