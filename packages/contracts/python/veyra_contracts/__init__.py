"""VEYRA shared contracts.

Phase 1 foundation package. These types are the single source of truth for
tool, permission, task, error, event, memory, and device shapes shared
between services (see docs/architecture and docs/security). No behavior
lives here — only typed data contracts and pure validation logic (e.g. the
task state transition table), matching CLAUDE.md's rule that the Policy
Engine and executors, not these contracts, own enforcement.
"""

from veyra_contracts.ambiguity import (
    AmbiguityCandidate,
    AmbiguityResolution,
    resolve_ambiguity,
)
from veyra_contracts.devices import (
    Command,
    Connection,
    Device,
    DeviceCapability,
    DevicePermission,
)
from veyra_contracts.enums import (
    TRUSTED_CONTENT_SOURCES,
    Confidence,
    ConfirmationPolicy,
    ConnectionProtocol,
    ContentSource,
    DeviceTrustStatus,
    DeviceType,
    ErrorCategory,
    EventType,
    EvidenceTier,
    MemoryCategory,
    PermissionDecision,
    RiskLevel,
    TaskState,
    ToolCategory,
    ToolResultStatus,
)
from veyra_contracts.errors import ErrorInfo
from veyra_contracts.events import Event
from veyra_contracts.memory import MemoryRecord
from veyra_contracts.permissions import PermissionGrant, PermissionRequest
from veyra_contracts.tasks import (
    TaskBudget,
    illegal_task_transition,
    is_legal_transition,
)
from veyra_contracts.tools import ToolCallRequest, ToolDefinition, ToolResult

__all__ = [
    "TRUSTED_CONTENT_SOURCES",
    "AmbiguityCandidate",
    "AmbiguityResolution",
    "Command",
    "Confidence",
    "ConfirmationPolicy",
    "Connection",
    "ConnectionProtocol",
    "ContentSource",
    "Device",
    "DeviceCapability",
    "DevicePermission",
    "DeviceTrustStatus",
    "DeviceType",
    "ErrorCategory",
    "ErrorInfo",
    "Event",
    "EventType",
    "EvidenceTier",
    "MemoryCategory",
    "MemoryRecord",
    "PermissionDecision",
    "PermissionGrant",
    "PermissionRequest",
    "RiskLevel",
    "TaskBudget",
    "TaskState",
    "ToolCallRequest",
    "ToolCategory",
    "ToolDefinition",
    "ToolResult",
    "ToolResultStatus",
    "illegal_task_transition",
    "is_legal_transition",
    "resolve_ambiguity",
]
