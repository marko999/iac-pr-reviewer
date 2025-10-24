from __future__ import annotations

import json
from pathlib import Path

import pytest

from compliance_service.models import ChangeAction
from compliance_service.normalization import ResourceNormalizer


@pytest.fixture()
def azure_plan() -> dict:
    fixture_path = (
        Path(__file__).parent.parent
        / "fixtures"
        / "azure"
        / "app_service_storage_plan.json"
    )
    return json.loads(fixture_path.read_text())


def test_normalizes_resource_changes(azure_plan: dict) -> None:
    normalizer = ResourceNormalizer()

    resources = normalizer.normalize(azure_plan)

    assert len(resources) == 5

    indexed = {resource.address: resource for resource in resources}

    storage = indexed["azurerm_storage_account.storage"]
    assert storage.module_path == []
    assert storage.change_action is ChangeAction.CREATE
    assert storage.after and storage.after["account_kind"] == "StorageV2"

    app_plan = indexed["module.app.azurerm_app_service_plan.plan"]
    assert app_plan.module_path == ["app"]
    assert app_plan.change_action is ChangeAction.CREATE
    assert app_plan.after and app_plan.after["sku"]["tier"] == "Standard"

    app_service = indexed["module.app.azurerm_app_service.web"]
    assert app_service.module_path == ["app"]
    assert app_service.change_action is ChangeAction.UPDATE
    assert app_service.before and app_service.before["https_only"] is False
    assert app_service.after and app_service.after["https_only"] is True

    sql = indexed["module.data.azurerm_mssql_server.sql"]
    assert sql.change_action is ChangeAction.REPLACE
    assert sql.module_path == ["data"]
    assert sql.before and sql.before["public_network_access_enabled"] is True
    assert sql.after and sql.after["public_network_access_enabled"] is False

    key_vault = indexed["module.security.azurerm_key_vault.vault"]
    assert key_vault.module_path == ["security"]
    assert key_vault.change_action is ChangeAction.CREATE
    assert key_vault.after and key_vault.after["public_network_access_enabled"] is False


def test_handles_missing_sections() -> None:
    normalizer = ResourceNormalizer()

    resources = normalizer.normalize({})

    assert resources == []
