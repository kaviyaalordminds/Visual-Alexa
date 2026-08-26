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
  | "browser"
  | "communication"
  | "media"
  | "documents"
  | "system"
  | "iot";

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
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

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
  | "system.health_changed";

// docs/architecture/02-DESKTOP-ARCHITECTURE.md / product brief §16 — the
// avatar state machine, driven 1:1 by TaskState + EventType via the event
// bus. Not rendered in Phase 1 (no avatar assets), but the type exists so
// the event-consumption contract is fixed before the avatar is built.
export type AvatarState =
  | "IDLE"
  | "LISTENING"
  | "THINKING"
  | "PLANNING"
  | "EXECUTING"
  | "WAITING_CONFIRMATION"
  | "SUCCESS"
  | "WARNING"
  | "ERROR"
  | "SPEAKING";
