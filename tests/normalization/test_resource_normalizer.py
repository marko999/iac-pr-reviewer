from __future__ import annotations

import json
from pathlib import Path

import pytest

from compliance_service.models import ChangeAction
from compliance_service.normalization import ResourceNormalizer

PLAN_EXPECTATIONS: dict[str, dict[str, object]] = {
    "app_service_storage_plan.json": {
        "count": 5,
        "resources": {
            "azurerm_storage_account.storage": {
                "module_path": [],
                "action": ChangeAction.CREATE,
                "after": {"account_kind": "StorageV2"},
            },
            "module.app.azurerm_app_service_plan.plan": {
                "module_path": ["app"],
                "action": ChangeAction.CREATE,
                "after": {"sku": {"tier": "Standard"}},
            },
            "module.app.azurerm_app_service.web": {
                "module_path": ["app"],
                "action": ChangeAction.UPDATE,
                "before": {"https_only": False},
                "after": {"https_only": True},
            },
            "module.data.azurerm_mssql_server.sql": {
                "module_path": ["data"],
                "action": ChangeAction.REPLACE,
                "before": {"public_network_access_enabled": True},
                "after": {"public_network_access_enabled": False},
            },
            "module.security.azurerm_key_vault.vault": {
                "module_path": ["security"],
                "action": ChangeAction.CREATE,
                "after": {"public_network_access_enabled": False},
            },
        },
    },
    "app_service.json": {
        "count": 3,
        "resources": {
            "azurerm_resource_group.example": {
                "module_path": [],
                "action": ChangeAction.CREATE,
                "after": {"name": "rg-web-compliant"},
            },
            "azurerm_app_service_plan.example": {
                "module_path": [],
                "action": ChangeAction.CREATE,
                "after": {"sku": {"tier": "Standard"}},
            },
            "azurerm_app_service.example": {
                "module_path": [],
                "action": ChangeAction.UPDATE,
                "before": {"https_only": False},
                "after": {"https_only": True},
            },
        },
    },
    "key_vault.json": {
        "count": 1,
        "resources": {
            "azurerm_key_vault.example": {
                "module_path": [],
                "action": ChangeAction.UPDATE,
                "before": {"public_network_access_enabled": True},
                "after": {"public_network_access_enabled": False},
            }
        },
    },
    "sql_server.json": {
        "count": 1,
        "resources": {
            "azurerm_mssql_server.example": {
                "module_path": [],
                "action": ChangeAction.UPDATE,
                "before": {"minimum_tls_version": "1.0"},
                "after": {"minimum_tls_version": "1.2"},
            }
        },
    },
}


@pytest.mark.parametrize("fixture_name", sorted(PLAN_EXPECTATIONS))
def test_normalizes_resource_changes(fixture_name: str) -> None:
    fixture_path = (
        Path(__file__).parent.parent / "fixtures" / "azure" / fixture_name
    )
    plan = json.loads(fixture_path.read_text())

    normalizer = ResourceNormalizer()
    resources = normalizer.normalize(plan)

    expectation = PLAN_EXPECTATIONS[fixture_name]

    assert len(resources) == expectation["count"]

    indexed = {resource.address: resource for resource in resources}
    assert set(indexed) == set(expectation["resources"])

    for address, expected in expectation["resources"].items():
        resource = indexed[address]
        assert resource.module_path == expected.get("module_path", [])
        assert resource.change_action is expected["action"]

        before_expectation = expected.get("before")
        if before_expectation:
            assert resource.before is not None
            for key, value in before_expectation.items():
                assert resource.before.get(key) == value

        after_expectation = expected.get("after")
        if after_expectation:
            assert resource.after is not None
            for key, value in after_expectation.items():
                # nested dictionaries (e.g. sku) are compared shallowly
                actual = resource.after.get(key)
                if isinstance(value, dict):
                    assert isinstance(actual, dict)
                    for nested_key, nested_value in value.items():
                        assert actual.get(nested_key) == nested_value
                else:
                    assert actual == value


def test_handles_missing_sections() -> None:
    normalizer = ResourceNormalizer()

    resources = normalizer.normalize({})

    assert resources == []
