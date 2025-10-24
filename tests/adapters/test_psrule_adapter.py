import json
from types import SimpleNamespace

import pytest

from compliance_service.adapters import PSRuleAdapter, RuleEvaluationError
from compliance_service.models import ChangeAction, FindingSeverity, NormalizedResource
from compliance_service.rules import RulePack, RulePackManager


class DummyManager(RulePackManager):
    def __init__(self, packs):
        super().__init__()
        self._packs = packs

    def enabled_packs(self, manifests=None):  # noqa: D401 - part of test double
        return list(self._packs)


def make_resource(address: str) -> NormalizedResource:
    return NormalizedResource(
        address=address,
        module_path=["module"],
        type="azurerm_storage_account",
        name="example",
        provider_name="registry.terraform.io/hashicorp/azurerm",
        mode="managed",
        index=None,
        change_action=ChangeAction.UPDATE,
        before=None,
        after={"name": "example"},
    )


def test_evaluate_invokes_psrule(monkeypatch, tmp_path):
    packs = [
        RulePack(name="azureBaseline", module="PSRule.Rules.Azure", settings={"baseline": "Azure"}),
        RulePack(name="customPack", source="custom/rules.yaml"),
    ]
    manager = DummyManager(packs)
    adapter = PSRuleAdapter(rule_pack_manager=manager)

    resources = [make_resource("module.app.azurerm_storage_account.primary")]
    recorded = {}

    def fake_run(command, capture_output, text):
        recorded["command"] = command
        input_idx = command.index("--input-path") + 1
        with open(command[input_idx], "r", encoding="utf-8") as handle:
            recorded["payload"] = json.load(handle)
        output = {
            "results": [
                {
                    "ruleId": "PSRule.Storage.DisablePublicAccess",
                    "level": "Warning",
                    "message": "Public access should be disabled.",
                    "targetId": "module.app.azurerm_storage_account.primary",
                    "recommendation": "Disable public network access",
                    "link": "https://aka.ms/psrule",
                }
            ]
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(output), stderr="")

    monkeypatch.setattr("compliance_service.adapters.rule_engine.subprocess.run", fake_run)

    findings = adapter.evaluate(resources)

    assert recorded["command"][:3] == ["ps-rule", "run", "--input-path"]
    assert "--module" in recorded["command"]
    assert "--source" in recorded["command"]
    assert {item["address"] for item in recorded["payload"]} == {
        "module.app.azurerm_storage_account.primary"
    }

    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule_id == "PSRule.Storage.DisablePublicAccess"
    assert finding.severity == FindingSeverity.MEDIUM
    assert finding.resource is resources[0]
    assert finding.metadata["recommendation"] == "Disable public network access"
    assert finding.metadata["link"] == "https://aka.ms/psrule"


def test_severity_threshold_filters(monkeypatch):
    adapter = PSRuleAdapter(rule_pack_manager=DummyManager([]))
    resources = [make_resource("module.app.azurerm_storage_account.primary")]

    payload = {
        "results": [
            {
                "ruleId": "CriticalRule",
                "level": "Critical",
                "message": "Critical finding",
                "targetId": "module.app.azurerm_storage_account.primary",
            },
            {
                "ruleId": "InformationalRule",
                "level": "Information",
                "message": "Info finding",
                "targetId": "module.app.azurerm_storage_account.primary",
            },
        ]
    }

    def fake_run(command, capture_output, text):
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr("compliance_service.adapters.rule_engine.subprocess.run", fake_run)

    findings = adapter.evaluate(resources, severity_threshold=FindingSeverity.HIGH)
    assert [finding.rule_id for finding in findings] == ["CriticalRule"]


def test_evaluate_raises_on_error(monkeypatch):
    adapter = PSRuleAdapter(rule_pack_manager=DummyManager([]))
    resources = [make_resource("module.app.azurerm_storage_account.primary")]

    def fake_run(command, capture_output, text):
        return SimpleNamespace(returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr("compliance_service.adapters.rule_engine.subprocess.run", fake_run)

    with pytest.raises(RuleEvaluationError):
        adapter.evaluate(resources)
