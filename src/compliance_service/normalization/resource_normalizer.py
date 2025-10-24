"""Conversion helpers that turn raw Terraform plan JSON into service models."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from ..models import ChangeAction, NormalizedResource


class ResourceNormalizer:
    """Normalize Terraform plan JSON into :class:`NormalizedResource` instances."""

    def normalize(self, plan: Dict[str, Any]) -> List[NormalizedResource]:
        """Return normalized resources for the supplied plan structure."""

        resource_changes: Iterable[Dict[str, Any]] = plan.get("resource_changes", []) or []
        return [self._normalize_change(change) for change in resource_changes]

    # ------------------------------------------------------------------
    def _normalize_change(self, change: Dict[str, Any]) -> NormalizedResource:
        module_path = self._module_path(change.get("module_address"))
        action = self._normalize_action(change.get("change", {}).get("actions", []))

        return NormalizedResource(
            address=change.get("address", ""),
            module_path=module_path,
            type=change.get("type", ""),
            name=change.get("name", ""),
            provider_name=change.get("provider_name"),
            mode=change.get("mode", "managed"),
            index=change.get("index"),
            change_action=action,
            before=change.get("change", {}).get("before"),
            after=change.get("change", {}).get("after"),
        )

    def _module_path(self, module_address: str | None) -> List[str]:
        if not module_address:
            return []

        parts: List[str] = []
        for segment in module_address.split("."):
            if segment == "module":
                continue
            parts.append(segment)
        return parts

    def _normalize_action(self, actions: Iterable[str]) -> ChangeAction:
        action_list = list(actions)
        if not action_list:
            return ChangeAction.UNKNOWN

        if action_list == ["no-op"]:
            return ChangeAction.NOOP
        if action_list == ["create"]:
            return ChangeAction.CREATE
        if action_list == ["update"]:
            return ChangeAction.UPDATE
        if action_list == ["delete"]:
            return ChangeAction.DELETE
        if set(action_list) == {"delete", "create"}:
            return ChangeAction.REPLACE

        return ChangeAction.UNKNOWN
