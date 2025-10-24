import json
from pathlib import Path

import pytest

from compliance_service.models import FindingSeverity
from compliance_service.rules import RulePackManager, RulePackError


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
                        "severity": {
                            "PSRule.Azure.Storage.Account.DenyPublicNetworkAccess": "high",
                            "PSRule.Azure.AppService.RequireHttps": "medium",
                        },
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
                        "severity": {
                            "PSRule.Azure.Storage.Account.DenyPublicNetworkAccess": "critical",
                        },
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
    assert baseline.severity_overrides == {
        "PSRule.Azure.Storage.Account.DenyPublicNetworkAccess": FindingSeverity.CRITICAL,
        "PSRule.Azure.AppService.RequireHttps": FindingSeverity.MEDIUM,
    }

    naming = packs_by_name["azureNaming"]
    assert naming.enabled is True
    assert naming.module == "Custom.Rules.Naming"

    enabled = manager.enabled_packs([override_manifest])
    assert [pack.name for pack in enabled] == ["azureNaming"]


def test_default_manifest_loaded():
    manager = RulePackManager()
    packs = manager.enabled_packs()

    pack_names = {pack.name for pack in packs}
    assert "azureBaseline" in pack_names

    baseline = next(pack for pack in packs if pack.name == "azureBaseline")
    assert baseline.module == "PSRule.Rules.Azure"
    assert baseline.settings["baseline"] == "Azure"
    assert baseline.severity_overrides[
        "PSRule.Azure.Storage.Account.DenyPublicNetworkAccess"
    ] == FindingSeverity.CRITICAL


def test_missing_manifest_raises(tmp_path: Path):
    manager = RulePackManager()
    with pytest.raises(RulePackError):
        manager.load([tmp_path / "missing.yaml"])
