// Mirrors services/local-api/app/api/system.py's SystemStatus response
// model. Backs the Phase 1 status screen — product brief §40.
//
// Subsystem activation (docs/subsystem-activation/SUBSYSTEM-ACTIVATION-
// REPORT.md): DEGRADED and DISABLED were added additively — every value
// that could appear before still can, so existing callers are unaffected.
// `details` is likewise additive: an older client that doesn't read it
// simply ignores it.

export type ComponentStatus =
  | "CONNECTED"
  | "NOT CONFIGURED"
  | "NOT ENABLED"
  | "NOT CONNECTED"
  | "ACTIVE"
  | "ERROR"
  | "DEGRADED"
  | "DISABLED";

export interface SystemStatus {
  desktop: ComponentStatus;
  local_api: ComponentStatus;
  database: ComponentStatus;
  ai: ComponentStatus;
  voice: ComponentStatus;
  vision: ComponentStatus;
  computer_control: ComponentStatus;
  iot: ComponentStatus;
  security: ComponentStatus;
  // Human-readable reason per component key (e.g. "ai" -> "No AI
  // provider configured (missing: API key)."). Populated for ai/voice/
  // vision/computer_control/iot; absent keys mean no extra detail exists
  // for that component.
  details?: Record<string, string>;
  // Phase 10 Part 48/53 (diagnostics, versioning) — additive.
  version?: string;
  uptime_seconds?: number | null;
}

export interface HealthResponse {
  status: string;
  timestamp: string;
}

export interface ReadyResponse {
  ready: boolean;
}
