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
    # Phase 3: OCR, vision-model, scene-diff, and visual-grounding tools —
    # perception, not action; see docs/phase-3/PHASE-3-IMPLEMENTATION-PLAN.md.
    VISION = "vision"
    BROWSER = "browser"
    COMMUNICATION = "communication"
    MEDIA = "media"
    DOCUMENTS = "documents"
    SYSTEM = "system"
    IOT = "iot"
    # Phase 7 — for a plugin- or integration-registered tool that doesn't
    # fit any category above (docs/phase-7/PLUGIN-ARCHITECTURE.md §9).
    CUSTOM = "custom"


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
    """docs/architecture/14-TASK-LIFECYCLE.md. Phase 4
    (docs/phase-4/TASK-STATE-MACHINE.md) adds TIMED_OUT additively — a
    budget exhaustion (max_steps/timeout_seconds) is now distinguishable
    from an ordinary tool failure rather than folding into FAILED. Phase 5
    (docs/phase-5/PHASE-5-IMPLEMENTATION-PLAN.md) adds PAUSED additively —
    a real, cooperative pause distinct from WAITING_PERMISSION/
    WAITING_USER (neither of which is user-initiated the way a voice
    "Wait" interruption is)."""

    RECEIVED = "RECEIVED"
    UNDERSTANDING = "UNDERSTANDING"
    PLANNING = "PLANNING"
    WAITING_PERMISSION = "WAITING_PERMISSION"
    EXECUTING = "EXECUTING"
    OBSERVING = "OBSERVING"
    VERIFYING = "VERIFYING"
    RECOVERING = "RECOVERING"
    WAITING_USER = "WAITING_USER"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"


class ErrorCategory(StrEnum):
    """docs/security error model, product brief §27. Phase 2 additions are
    documented in docs/phase-2/ERROR-RECOVERY.md — note UI_ELEMENT_NOT_FOUND
    from the Phase 2 brief maps onto the existing UI_NOT_FOUND rather than
    duplicating it."""

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

    # --- Phase 2: computer-control engine ---
    APPLICATION_LAUNCH_FAILED = "APPLICATION_LAUNCH_FAILED"
    WINDOW_NOT_FOUND = "WINDOW_NOT_FOUND"
    WINDOW_NOT_ACTIVE = "WINDOW_NOT_ACTIVE"
    UI_ELEMENT_DISABLED = "UI_ELEMENT_DISABLED"
    PATH_NOT_ALLOWED = "PATH_NOT_ALLOWED"
    PATH_PROTECTED = "PATH_PROTECTED"
    TARGET_CONTEXT_REQUIRED = "TARGET_CONTEXT_REQUIRED"
    INPUT_BLOCKED = "INPUT_BLOCKED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    TOOL_DISABLED = "TOOL_DISABLED"
    OPERATION_CANCELLED = "OPERATION_CANCELLED"
    UNKNOWN_WINDOWS_ERROR = "UNKNOWN_WINDOWS_ERROR"
    # Not in the Phase 2 brief's list; added so a Windows-only tool fails
    # honestly on a non-Windows host instead of crashing or faking success —
    # see docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §2.
    PLATFORM_NOT_SUPPORTED = "PLATFORM_NOT_SUPPORTED"

    # --- Phase 4: AI brain / task execution engine ---
    # docs/phase-4/PHASE-4-IMPLEMENTATION-PLAN.md §1 — extends this same
    # enum rather than a second "FailureCategory," since Phase 4's failure
    # taxonomy (brief §47) and this one describe the same concept (why a
    # call failed) at the same granularity. Most of the brief's §47 list
    # already existed under a different name (see the plan doc's mapping
    # table); these five did not.
    AMBIGUOUS_TARGET = "AMBIGUOUS_TARGET"
    STATE_MISMATCH = "STATE_MISMATCH"
    RESOURCE_BUSY = "RESOURCE_BUSY"
    INVALID_PLAN = "INVALID_PLAN"
    UNKNOWN_TOOL = "UNKNOWN_TOOL"
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"

    # --- Phase 5: voice intelligence engine ---
    # docs/phase-5/PHASE-5-IMPLEMENTATION-PLAN.md §6, brief §112-113.
    MIC_NOT_FOUND = "MIC_NOT_FOUND"
    MIC_PERMISSION_DENIED = "MIC_PERMISSION_DENIED"
    AUDIO_INPUT_FAILED = "AUDIO_INPUT_FAILED"
    AUDIO_OUTPUT_FAILED = "AUDIO_OUTPUT_FAILED"
    WAKE_WORD_ERROR = "WAKE_WORD_ERROR"
    VAD_ERROR = "VAD_ERROR"
    STT_ERROR = "STT_ERROR"
    STT_TIMEOUT = "STT_TIMEOUT"
    LANGUAGE_UNKNOWN = "LANGUAGE_UNKNOWN"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    TTS_ERROR = "TTS_ERROR"
    TTS_TIMEOUT = "TTS_TIMEOUT"
    CLOUD_PROVIDER_ERROR = "CLOUD_PROVIDER_ERROR"
    VOICE_CANCELLED = "VOICE_CANCELLED"
    SESSION_TIMEOUT = "SESSION_TIMEOUT"

    # --- Phase 7: universal tool/integration/plugin platform ---
    # docs/phase-7/PHASE-7-IMPLEMENTATION-PLAN.md §1 — most of brief §32's
    # failure taxonomy already existed under an existing name (PERMISSION_
    # DENIED, CAPABILITY_UNAVAILABLE, NETWORK_ERROR, TIMEOUT, VALIDATION_
    # ERROR, OPERATION_CANCELLED, PLATFORM_NOT_SUPPORTED); these three did
    # not.
    AUTH_ERROR = "AUTH_ERROR"
    NOT_CONNECTED = "NOT_CONNECTED"
    RATE_LIMITED = "RATE_LIMITED"

    # --- Phase 8: browser & web intelligence engine ---
    # docs/phase-8/BROWSER-ARCHITECTURE.md §86. Most of brief §86's browser
    # error taxonomy already existed under an existing name
    # (ELEMENT_NOT_FOUND -> UI_NOT_FOUND, ELEMENT_NOT_INTERACTABLE ->
    # UI_ELEMENT_DISABLED, TIMEOUT/NETWORK_ERROR unchanged, LOGIN_REQUIRED
    # -> AUTHENTICATION_REQUIRED, PERMISSION_REQUIRED -> PERMISSION_DENIED);
    # these did not.
    NAVIGATION_FAILED = "NAVIGATION_FAILED"
    CAPTCHA_DETECTED = "CAPTCHA_DETECTED"
    OTP_REQUIRED = "OTP_REQUIRED"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    DOWNLOAD_BLOCKED = "DOWNLOAD_BLOCKED"
    PAGE_CHANGED = "PAGE_CHANGED"
    UNSAFE_URL = "UNSAFE_URL"
    PROMPT_INJECTION_BLOCKED = "PROMPT_INJECTION_BLOCKED"
    PAYMENT_CONFIRMATION_REQUIRED = "PAYMENT_CONFIRMATION_REQUIRED"
    EXTENSION_AUTH_FAILED = "EXTENSION_AUTH_FAILED"


class EventType(StrEnum):
    """docs/architecture/12-EVENTS.md §2. Phase 4
    (docs/phase-4/AGENT-ARCHITECTURE.md §5) adds the granular `task.*`
    events brief §84 asks for, additively — TASK_STARTED/PROGRESS/COMPLETED
    already existed from Phase 1 and are kept for compatibility."""

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

    # --- Phase 4 ---
    TASK_CREATED = "task.created"
    TASK_PLANNED = "task.planned"
    TASK_STEP_STARTED = "task.step.started"
    TASK_STEP_COMPLETED = "task.step.completed"
    TASK_STEP_FAILED = "task.step.failed"
    TASK_CONFIRMATION_REQUIRED = "task.confirmation.required"
    TASK_CONFIRMATION_RECEIVED = "task.confirmation.received"
    TASK_RECOVERY_STARTED = "task.recovery.started"
    TASK_RECOVERY_COMPLETED = "task.recovery.completed"
    TASK_PAUSED = "task.paused"
    TASK_RESUMED = "task.resumed"
    TASK_CANCELLED = "task.cancelled"
    TASK_FAILED = "task.failed"
    TASK_TIMED_OUT = "task.timed_out"

    # --- Phase 5: voice intelligence engine ---
    # docs/phase-5/VOICE-EVENTS.md, brief §44-45. These describe the voice
    # pipeline itself (audio -> transcript -> response); they never
    # duplicate the task.* events above, which still fire exactly as
    # Phase 4 defined them for whatever Task a voice turn creates.
    VOICE_WAKE_DETECTED = "voice.wake_detected"
    VOICE_LISTENING_STARTED = "voice.listening_started"
    VOICE_LISTENING_STOPPED = "voice.listening_stopped"
    VOICE_TRANSCRIPT_PARTIAL = "voice.transcript.partial"
    VOICE_TRANSCRIPT_FINAL = "voice.transcript.final"
    VOICE_LANGUAGE_DETECTED = "voice.language.detected"
    VOICE_INTENT_RECEIVED = "voice.intent.received"
    VOICE_RESPONSE_STARTED = "voice.response.started"
    VOICE_RESPONSE_FINISHED = "voice.response.finished"
    VOICE_INTERRUPTED = "voice.interrupted"
    VOICE_ERROR = "voice.error"
    # UI-state events prepared for a future avatar (brief §69) — no
    # avatar/animation implementation ships in Phase 5, only the event.
    VOICE_UI_STATE_CHANGED = "voice.ui_state.changed"


class RecoveryStrategy(StrEnum):
    """docs/phase-4/RECOVERY.md"""

    RETRY = "RETRY"
    REOBSERVE = "REOBSERVE"
    REGROUND = "REGROUND"
    ALTERNATIVE_TOOL = "ALTERNATIVE_TOOL"
    REPLAN = "REPLAN"
    ASK_USER = "ASK_USER"
    ABORT = "ABORT"


class AgentState(StrEnum):
    """docs/phase-4/AGENT-ARCHITECTURE.md §7 — semantic states for a
    future avatar/UI to consume; computed from TaskState, never stored as
    a second, independently-mutable field (docs/phase-4/TASK-MEMORY.md).
    Phase 4 shipped only this enum and a mapping *convention* in prose —
    `veyra_contracts.avatar.compute_agent_state_from_task` is the real,
    tested function Phase 6 (docs/phase-6/AVATAR-ARCHITECTURE.md) added as
    its first actual caller. Phase 6 also adds `SPEAKING` and `PAUSED`
    additively: `SPEAKING` has no `TaskState` equivalent (VEYRA can be
    speaking a response while the underlying task is already terminal),
    so it's driven directly by the voice layer instead of the mapping
    table; `PAUSED` mirrors `TaskState.PAUSED` (Phase 5) 1:1."""

    IDLE = "IDLE"
    LISTENING = "LISTENING"
    UNDERSTANDING = "UNDERSTANDING"
    THINKING = "THINKING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    WAITING = "WAITING"
    CONFIRMING = "CONFIRMING"
    RECOVERING = "RECOVERING"
    SPEAKING = "SPEAKING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    PAUSED = "PAUSED"

    # --- Phase 8: browser & web intelligence engine ---
    # docs/phase-8/BROWSER-ARCHITECTURE.md §139. Like SPEAKING (Phase 6),
    # these have no TaskState equivalent and are set directly by
    # BrowserWorkflowEngine over the same shared `voice.ui_state.changed`
    # channel Phase 6 established as the one avatar-state broadcast
    # (never voice-exclusive despite the wire event name — see that
    # module's own docstring). ACTING/WAITING/CONFIRMING/COMPLETED/ERROR
    # from brief §139 already exist above (EXECUTING/WAITING/CONFIRMING/
    # SUCCESS/ERROR); only these four are new.
    BROWSING = "BROWSING"
    SEARCHING = "SEARCHING"
    READING = "READING"
    BLOCKED = "BLOCKED"


class TaskPriority(StrEnum):
    """docs/phase-4/TASK-ENGINE.md"""

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


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


class DevicePairingStage(StrEnum):
    """docs/phase-7/IOT-ARCHITECTURE.md — CLAUDE.md's six-stage device
    authorization flow ('PAIR -> IDENTIFY -> AUTHENTICATE -> AUTHORIZE ->
    REGISTER CAPABILITIES -> CONTROL, in order, with no stage
    skippable'), enforced procedurally by `DevicePairingService` against
    a `Device.pairing_stage` column. Deliberately finer-grained than
    `DeviceTrustStatus` (which only reflects the externally-meaningful
    coarse state) — this is the internal invariant a caller cannot skip
    past, not a second status a UI would show directly."""

    PAIR = "PAIR"
    IDENTIFY = "IDENTIFY"
    AUTHENTICATE = "AUTHENTICATE"
    AUTHORIZE = "AUTHORIZE"
    REGISTER_CAPABILITIES = "REGISTER_CAPABILITIES"
    CONTROL = "CONTROL"


class AuthMethod(StrEnum):
    """docs/phase-7/INTEGRATION-ARCHITECTURE.md — mirrors
    docs/architecture/11-INTEGRATIONS.md §2's documented `Integration`
    interface (`auth_method: AuthMethod`), now a real enum instead of an
    unconstrained string on the `Integration.auth_method` column."""

    OAUTH2 = "OAUTH2"
    API_KEY = "API_KEY"
    NONE = "NONE"


class IntegrationState(StrEnum):
    """docs/phase-7/INTEGRATION-ARCHITECTURE.md §23."""

    AVAILABLE = "AVAILABLE"
    INSTALL_REQUIRED = "INSTALL_REQUIRED"
    CONNECT_REQUIRED = "CONNECT_REQUIRED"
    AUTHORIZING = "AUTHORIZING"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    ERROR = "ERROR"
    UNAVAILABLE = "UNAVAILABLE"


class PluginState(StrEnum):
    """docs/phase-7/PLUGIN-ARCHITECTURE.md §63 — never treat every
    installed plugin as trusted; a plugin only reaches ENABLED (its tools
    live in the real ToolRegistry) through an explicit user action."""

    UNTRUSTED = "UNTRUSTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    TRUSTED = "TRUSTED"
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    REVOKED = "REVOKED"


class ContentSource(StrEnum):
    """docs/security/07-PROMPT-INJECTION.md §3 — provenance tag distinguishing
    trusted user instructions from observed (untrusted) content.

    Phase 3 (docs/phase-3/PROMPT-INJECTION.md) extends this set additively
    with more granular labels for the visual-perception pipeline. `USER`/
    `OBSERVED_CONTENT`/`SYSTEM` are the original Phase 1 values and are kept
    unchanged for backward compatibility with anything already tagging
    content that way."""

    USER = "USER"
    OBSERVED_CONTENT = "OBSERVED_CONTENT"
    SYSTEM = "SYSTEM"

    # --- Phase 3: visual perception trust boundaries ---
    USER_INPUT = "USER_INPUT"
    SYSTEM_STATE = "SYSTEM_STATE"
    UI_OBSERVATION = "UI_OBSERVATION"
    DOCUMENT_CONTENT = "DOCUMENT_CONTENT"
    WEB_CONTENT = "WEB_CONTENT"
    TOOL_RESULT = "TOOL_RESULT"
    AI_OUTPUT = "AI_OUTPUT"


TRUSTED_CONTENT_SOURCES: frozenset[ContentSource] = frozenset(
    {ContentSource.USER, ContentSource.USER_INPUT, ContentSource.SYSTEM, ContentSource.SYSTEM_STATE}
)
"""The one place 'which sources may authorize an action' is decided
(docs/phase-3/PROMPT-INJECTION.md). Everything else — including
UI_OBSERVATION and WEB_CONTENT — is untrusted by default: text observed on
screen, in a document, or on a web page must never be treated as
equivalent to a direct user instruction, no matter how imperative it
reads. A future AI planner must check membership in this set before ever
treating a ContentSource as authorization to act."""


class Confidence(StrEnum):
    """docs/architecture/03-AI-ARCHITECTURE.md §5"""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DomainTrustStatus(StrEnum):
    """docs/phase-8/BROWSER-SECURITY.md §92 — 'maintain optional domain
    trust information... do not automatically trust new domains.' A new
    domain a browser session encounters defaults to UNKNOWN, never
    TRUSTED."""

    TRUSTED = "TRUSTED"
    UNKNOWN = "UNKNOWN"
    BLOCKED = "BLOCKED"
