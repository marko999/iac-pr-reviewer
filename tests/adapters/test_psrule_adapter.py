import json
from pathlib import Path
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
        RulePack(
            name="azureBaseline",
            module="PSRule.Rules.Azure",
            settings={"baseline": "Azure"},
            severity_overrides={
                "PSRule.Azure.Storage.Account.DenyPublicNetworkAccess": FindingSeverity.CRITICAL,
            },
        ),
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
                    "ruleId": "PSRule.Azure.Storage.Account.DenyPublicNetworkAccess",
                    "level": "Warning",
                    "message": "Public access should be disabled.",
                    "targetId": "module.app.azurerm_storage_account.primary",
                    "recommendation": "Disable public network access",
                    "link": "https://aka.ms/psrule/storage",
                },
                {
                    "ruleId": "PSRule.Azure.AppService.RequireHttps",
                    "level": "Error",
                    "message": "HTTPS Only should be enabled.",
                    "targetId": "module.app.azurerm_storage_account.primary",
                    "recommendation": "Enforce HTTPS only connections",
                    "link": "https://aka.ms/psrule/appservice",
                },
            ]
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(output), stderr="")

    monkeypatch.setattr("compliance_service.adapters.rule_engine.subprocess.run", fake_run)

    findings = adapter.evaluate(resources)

    assert Path(recorded["command"][0]).name == "run_psrule.ps1"
    assert recorded["command"][1:3] == ["run", "--input-path"]
    assert "--module" in recorded["command"]
    assert "--source" in recorded["command"]
    assert {item["address"] for item in recorded["payload"]} == {
        "module.app.azurerm_storage_account.primary"
    }

    assert len(findings) == 2

    deny_public_access, enforce_https = findings

    assert deny_public_access.rule_id == "PSRule.Azure.Storage.Account.DenyPublicNetworkAccess"
    assert deny_public_access.severity == FindingSeverity.CRITICAL
    assert deny_public_access.resource is resources[0]
    assert deny_public_access.metadata["recommendation"] == "Disable public network access"
    assert deny_public_access.metadata["link"] == "https://aka.ms/psrule/storage"

    assert enforce_https.rule_id == "PSRule.Azure.AppService.RequireHttps"
    assert enforce_https.severity == FindingSeverity.HIGH
    assert enforce_https.resource is resources[0]
    assert enforce_https.metadata["recommendation"] == "Enforce HTTPS only connections"
    assert enforce_https.metadata["link"] == "https://aka.ms/psrule/appservice"


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


def test_severity_override_applied(monkeypatch):
    packs = [
        RulePack(
            name="azureBaseline",
            severity_overrides={"CriticalRule": FindingSeverity.CRITICAL},
        )
    ]
    adapter = PSRuleAdapter(rule_pack_manager=DummyManager(packs))
    resources = [make_resource("module.app.azurerm_storage_account.primary")]

    payload = {
        "results": [
            {
                "ruleId": "CriticalRule",
                "level": "Information",
                "message": "Critical finding",
                "targetId": "module.app.azurerm_storage_account.primary",
            }
        ]
    }

    def fake_run(command, capture_output, text):
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr("compliance_service.adapters.rule_engine.subprocess.run", fake_run)

    findings = adapter.evaluate(resources)
    assert len(findings) == 1
    assert findings[0].severity == FindingSeverity.CRITICAL
