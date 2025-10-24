"""Finding models shared across adapters and reporting layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from .resource import NormalizedResource


class FindingSeverity(str, Enum):
    """Severity levels supported by the compliance tooling."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(slots=True)
class Finding:
    """A rule evaluation finding that can be reported to users."""

    rule_id: str
    message: str
    severity: FindingSeverity
    resource: Optional["NormalizedResource"] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
