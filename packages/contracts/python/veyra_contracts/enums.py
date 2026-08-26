"""Enums shared across the VEYRA foundation. See docs/architecture and
docs/security for the design rationale behind each enum's values.
"""

from enum import StrEnum


class RiskLevel(StrEnum):
    """docs/security/08-SENSITIVE-ACTION-POLICY.md"""

    SAFE = "SAFE"
    MODERATE = "MODERATE"
    SENSITIVE = "SENSITIVE"
    CRITICAL = "CRITICAL"


class ToolCategory(StrEnum):
    """docs/architecture/04-TOOL-ARCHITECTURE.md §5"""

    FILESYSTEM = "filesystem"
    WINDOWS = "windows"
    PROCESS = "process"
    SCREEN = "screen"
    KEYBOARD = "keyboard"
    MOUSE = "mouse"
    BROWSER = "browser"
    COMMUNICATION = "communication"
    MEDIA = "media"
    DOCUMENTS = "documents"
    SYSTEM = "system"
    IOT = "iot"


class ConfirmationPolicy(StrEnum):
    """Per-tool default confirmation behavior. CRITICAL-risk tools always
    require confirmation regardless of this value — see
    docs/security/08-SENSITIVE-ACTION-POLICY.md §2."""

    NEVER = "NEVER"
    SESSION = "SESSION"
    ALWAYS = "ALWAYS"


class ToolResultStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"


class EvidenceTier(StrEnum):
    """docs/architecture/05-COMPUTER-CONTROL.md §1 — priority order matters;
    integer value doubles as priority rank (lower = preferred)."""

    NATIVE_API = "NATIVE_API"
    UI_AUTOMATION = "UI_AUTOMATION"
    ACCESSIBILITY_TREE = "ACCESSIBILITY_TREE"
    APP_INTEGRATION = "APP_INTEGRATION"
    BROWSER_DOM = "BROWSER_DOM"
    OCR = "OCR"
    VISION_MODEL = "VISION_MODEL"
    COORDINATE = "COORDINATE"


EVIDENCE_TIER_PRIORITY: dict[EvidenceTier, int] = {
    tier: index for index, tier in enumerate(EvidenceTier)
}


class PermissionDecision(StrEnum):
    """docs/security/02-PERMISSION-MODEL.md"""

    ALLOW_ONCE = "ALLOW_ONCE"
    ALLOW_SESSION = "ALLOW_SESSION"
    ALWAYS_ALLOW = "ALWAYS_ALLOW"
    DENY = "DENY"
    CANCEL = "CANCEL"


class TaskState(StrEnum):
    """docs/architecture/14-TASK-LIFECYCLE.md"""

    RECEIVED = "RECEIVED"
    UNDERSTANDING = "UNDERSTANDING"
    PLANNING = "PLANNING"
    WAITING_PERMISSION = "WAITING_PERMISSION"
    EXECUTING = "EXECUTING"
    OBSERVING = "OBSERVING"
    VERIFYING = "VERIFYING"
    RECOVERING = "RECOVERING"
    WAITING_USER = "WAITING_USER"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ErrorCategory(StrEnum):
    """docs/security error model, product brief §27"""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    DEVICE_UNAVAILABLE = "DEVICE_UNAVAILABLE"
    APPLICATION_NOT_FOUND = "APPLICATION_NOT_FOUND"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    UI_NOT_FOUND = "UI_NOT_FOUND"
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT = "TIMEOUT"
    TOOL_FAILURE = "TOOL_FAILURE"
    MODEL_FAILURE = "MODEL_FAILURE"
    VISION_FAILURE = "VISION_FAILURE"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class EventType(StrEnum):
    """docs/architecture/12-EVENTS.md §2"""

    ASSISTANT_LISTENING = "assistant.listening"
    ASSISTANT_THINKING = "assistant.thinking"
    ASSISTANT_PLANNING = "assistant.planning"
    ASSISTANT_EXECUTING = "assistant.executing"
    ASSISTANT_CONFIRMATION_REQUIRED = "assistant.confirmation_required"
    ASSISTANT_COMPLETED = "assistant.completed"
    ASSISTANT_ERROR = "assistant.error"
    TASK_STARTED = "task.started"
    TASK_PROGRESS = "task.progress"
    TASK_COMPLETED = "task.completed"
    DEVICE_CONNECTED = "device.connected"
    DEVICE_DISCONNECTED = "device.disconnected"
    SYSTEM_HEALTH_CHANGED = "system.health_changed"


class MemoryCategory(StrEnum):
    """docs/architecture/09-MEMORY.md §1"""

    SHORT_TERM = "SHORT_TERM"
    CONVERSATION = "CONVERSATION"
    TASK = "TASK"
    USER_PREFERENCE = "USER_PREFERENCE"
    SEMANTIC = "SEMANTIC"
    WORKFLOW = "WORKFLOW"
    DEVICE = "DEVICE"


class DeviceType(StrEnum):
    """docs/architecture/10-IOT.md §2"""

    AC = "AC"
    FAN = "FAN"
    TV = "TV"
    REFRIGERATOR = "REFRIGERATOR"
    LIGHT = "LIGHT"
    SMART_PLUG = "SMART_PLUG"
    SPEAKER = "SPEAKER"
    OTHER = "OTHER"


class DeviceTrustStatus(StrEnum):
    """docs/security/04-DEVICE-TRUST.md §2"""

    UNPAIRED = "UNPAIRED"
    PAIRING = "PAIRING"
    PAIRED = "PAIRED"
    REVOKED = "REVOKED"


class ConnectionProtocol(StrEnum):
    """docs/architecture/10-IOT.md §2"""

    MATTER = "MATTER"
    MQTT = "MQTT"
    LOCAL_HTTP = "LOCAL_HTTP"
    BLUETOOTH = "BLUETOOTH"
    VENDOR_API = "VENDOR_API"


class ContentSource(StrEnum):
    """docs/security/07-PROMPT-INJECTION.md §3 — provenance tag distinguishing
    trusted user instructions from observed (untrusted) content."""

    USER = "USER"
    OBSERVED_CONTENT = "OBSERVED_CONTENT"
    SYSTEM = "SYSTEM"


class Confidence(StrEnum):
    """docs/architecture/03-AI-ARCHITECTURE.md §5"""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
