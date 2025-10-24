from __future__ import annotations

import json
from pathlib import Path

import pytest

from compliance_service.models import ChangeAction
from compliance_service.normalization import ResourceNormalizer


@pytest.fixture()
def azure_plan() -> dict:
    fixture_path = Path(__file__).parent.parent / "fixtures" / "azure" / "app_service_storage_plan.json"
    return json.loads(fixture_path.read_text())


def test_normalizes_resource_changes(azure_plan: dict) -> None:
    normalizer = ResourceNormalizer()

    resources = normalizer.normalize(azure_plan)

    assert len(resources) == 3

    storage = resources[0]
    assert storage.address == "azurerm_storage_account.storage"
    assert storage.module_path == []
    assert storage.change_action is ChangeAction.CREATE
    assert storage.after and storage.after["account_kind"] == "StorageV2"

    app_service = resources[1]
    assert app_service.module_path == ["app_service"]
    assert app_service.change_action is ChangeAction.UPDATE
    assert app_service.before and app_service.before["https_only"] is False
    assert app_service.after and app_service.after["https_only"] is True

    sql = resources[2]
    assert sql.change_action is ChangeAction.REPLACE
    assert sql.module_path == ["sql"]


def test_handles_missing_sections() -> None:
    normalizer = ResourceNormalizer()

    resources = normalizer.normalize({})

    assert resources == []
