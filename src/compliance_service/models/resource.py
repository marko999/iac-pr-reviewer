"""Resource models used by the compliance service."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ChangeAction(str, Enum):
    """Enumeration of the planned action for a Terraform resource."""

    NOOP = "no-op"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    REPLACE = "replace"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class NormalizedResource:
    """Normalized representation of a Terraform resource change."""

    address: str
    module_path: List[str] = field(default_factory=list)
    type: str = ""
    name: str = ""
    provider_name: Optional[str] = None
    mode: str = "managed"
    index: Optional[str | int] = None
    change_action: ChangeAction = ChangeAction.UNKNOWN
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None

    @property
    def is_module_root(self) -> bool:
        """Return ``True`` when the resource is defined at the root module."""

        return not self.module_path
