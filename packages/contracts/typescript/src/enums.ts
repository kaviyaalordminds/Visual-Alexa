// Mirrors packages/contracts/python/veyra_contracts/enums.py — keep in sync.
// See docs/architecture and docs/security for the design rationale behind
// each enum's values.

export type RiskLevel = "SAFE" | "MODERATE" | "SENSITIVE" | "CRITICAL";

export type ToolCategory =
  | "filesystem"
  | "windows"
  | "process"
  | "screen"
  | "keyboard"
  | "mouse"
  | "vision"
  | "browser"
  | "communication"
  | "media"
  | "documents"
  | "system"
  | "iot"
  | "custom";

export type TaskState =
  | "RECEIVED"
  | "UNDERSTANDING"
  | "PLANNING"
  | "WAITING_PERMISSION"
  | "EXECUTING"
  | "OBSERVING"
  | "VERIFYING"
  | "RECOVERING"
  | "WAITING_USER"
  | "PAUSED"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED"
  | "TIMED_OUT";

export type EventType =
  | "assistant.listening"
  | "assistant.thinking"
  | "assistant.planning"
  | "assistant.executing"
  | "assistant.confirmation_required"
  | "assistant.completed"
  | "assistant.error"
  | "task.started"
  | "task.progress"
  | "task.completed"
  | "device.connected"
  | "device.disconnected"
  | "system.health_changed"
  | "task.created"
  | "task.planned"
  | "task.step.started"
  | "task.step.completed"
  | "task.step.failed"
  | "task.confirmation.required"
  | "task.confirmation.received"
  | "task.recovery.started"
  | "task.recovery.completed"
  | "task.paused"
  | "task.resumed"
  | "task.cancelled"
  | "task.failed"
  | "task.timed_out"
  | "voice.wake_detected"
  | "voice.listening_started"
  | "voice.listening_stopped"
  | "voice.transcript.partial"
  | "voice.transcript.final"
  | "voice.language.detected"
  | "voice.intent.received"
  | "voice.response.started"
  | "voice.response.finished"
  | "voice.interrupted"
  | "voice.error"
  | "voice.ui_state.changed";

// docs/phase-4/AGENT-ARCHITECTURE.md §5 / docs/phase-6/AVATAR-ARCHITECTURE.md
// — semantic states for the avatar to render, computed server-side from
// TaskState (veyra_contracts.avatar.compute_agent_state_from_task) or set
// directly by the voice layer (SPEAKING has no TaskState equivalent).
// Delivered as an architecture-only stub in Phase 1 under the name
// `AvatarState`; renamed to `AgentState` and completed in Phase 6 to
// match the Python contract this always mirrored.
// Phase 8 (docs/phase-8/BROWSER-ARCHITECTURE.md §139) adds BROWSING/
// SEARCHING/READING/BLOCKED additively — like SPEAKING, these have no
// TaskState equivalent and are set directly by BrowserWorkflowEngine.
export type AgentState =
  | "IDLE"
  | "LISTENING"
  | "UNDERSTANDING"
  | "THINKING"
  | "PLANNING"
  | "EXECUTING"
  | "WAITING"
  | "CONFIRMING"
  | "RECOVERING"
  | "SPEAKING"
  | "SUCCESS"
  | "ERROR"
  | "PAUSED"
  | "BROWSING"
  | "SEARCHING"
  | "READING"
  | "BLOCKED";

// docs/phase-6/LIP-SYNC.md — a small, closed set of mouth-shape buckets a
// deterministic text-driven approximation classifies into (there is no
// real TTS audio/phoneme timing in this environment, see PHASE-6-TEST-
// RESULTS.md). Not any specific vendor's viseme set — a generic reduced
// grouping by mouth shape.
export type VisemeShape =
  | "REST"
  | "AI"
  | "E"
  | "FV"
  | "L"
  | "MBP"
  | "OH"
  | "U"
  | "WQ"
  | "ETC";

// docs/phase-7/INTEGRATION-ARCHITECTURE.md, PLUGIN-ARCHITECTURE.md,
// DEVICE-PAIRING.md.
export type AuthMethod = "OAUTH2" | "API_KEY" | "NONE";

export type IntegrationState =
  | "AVAILABLE"
  | "INSTALL_REQUIRED"
  | "CONNECT_REQUIRED"
  | "AUTHORIZING"
  | "CONNECTED"
  | "DISCONNECTED"
  | "EXPIRED"
  | "REVOKED"
  | "ERROR"
  | "UNAVAILABLE";

export type PluginState =
  | "UNTRUSTED"
  | "REVIEW_REQUIRED"
  | "TRUSTED"
  | "ENABLED"
  | "DISABLED"
  | "REVOKED";

export type DeviceType =
  | "AC"
  | "FAN"
  | "TV"
  | "REFRIGERATOR"
  | "LIGHT"
  | "SMART_PLUG"
  | "SPEAKER"
  | "OTHER";

export type DeviceTrustStatus = "UNPAIRED" | "PAIRING" | "PAIRED" | "REVOKED";

export type ConnectionProtocol = "MATTER" | "MQTT" | "LOCAL_HTTP" | "BLUETOOTH" | "VENDOR_API";

export type DevicePairingStage =
  | "PAIR"
  | "IDENTIFY"
  | "AUTHENTICATE"
  | "AUTHORIZE"
  | "REGISTER_CAPABILITIES"
  | "CONTROL";

// docs/phase-8/BROWSER-SECURITY.md §92 — a new domain always starts
// UNKNOWN, never automatically TRUSTED.
export type DomainTrustStatus = "TRUSTED" | "UNKNOWN" | "BLOCKED";
