// Mirrors services/local-api/app/api/tasks.py's TaskOut/TaskStepOut/
// ConfirmRequest — the real plan -> execute -> observe -> verify ->
// recover pipeline (docs/architecture/14-TASK-LIFECYCLE.md), the same
// API any other caller of VEYRA uses. Added alongside TaskRunner.tsx,
// the first frontend surface that actually drives a free-text task
// through this API end to end (previously only DevConsole's fixed
// diagnostic-tool dropdown existed).

import type { RiskLevel, TaskState } from "./enums";

export interface TaskBudget {
  max_steps: number;
  timeout_seconds: number;
  max_recovery_attempts: number;
  max_replans?: number;
}

export interface TaskResult {
  confirmation_prompt?: string;
  pending_tool_id?: string;
  pending_target?: string | null;
  pending_risk_level?: RiskLevel;
  outcome?: string;
  [key: string]: unknown;
}

export interface TaskOut {
  id: string;
  description: string;
  state: TaskState;
  max_steps: number;
  timeout_seconds: number;
  max_recovery_attempts: number;
  correlation_id: string;
  created_at: string;
  current_step: number;
  total_steps: number;
  requires_confirmation: boolean;
  failure_reason: string | null;
  result: TaskResult | null;
}

export interface TaskStepOut {
  id: string;
  step_number: number;
  state: TaskState;
  tool_id: string | null;
  description: string | null;
  arguments: Record<string, unknown>;
  risk_level: RiskLevel | null;
  retry_count: number;
  error: { code: string; message: string } | null;
  actual_result: Record<string, unknown> | null;
}

// docs/security/08-SENSITIVE-ACTION-POLICY.md §3. ALLOW_SESSION/
// ALWAYS_ALLOW are only meaningful for MODERATE/SENSITIVE steps — a
// CRITICAL step always re-confirms regardless of which of these is sent
// (enforced server-side in both PolicyEngine and confirmation_actions.py,
// never trust the client alone for that).
export type PermissionDecision =
  | "ALLOW_ONCE"
  | "ALLOW_SESSION"
  | "ALWAYS_ALLOW"
  | "DENY"
  | "CANCEL";
