// Mirrors services/local-api/app/api/tasks.py's TaskOut/TaskStepOut/
// TaskCreate request-response shapes, plus veyra_contracts.tasks.TaskBudget.
// docs/architecture/14-TASK-LIFECYCLE.md, docs/phase-4/TASK-API.md.
//
// Phase 13 (docs/phase-13-audit.md §8) — the desktop shell had no
// contract for these at all, which is exactly why nothing in the
// frontend could render a task's live progress or its real
// `confirmation_prompt` (carried in `TaskOut.result` while a task is
// WAITING_PERMISSION — see orchestrator.py's `_execute_plan`).

import type { RiskLevel, TaskState } from "./enums";

export interface TaskBudget {
  max_steps: number;
  timeout_seconds: number;
  max_recovery_attempts: number;
  max_replans?: number;
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
  // While `state` is WAITING_PERMISSION, carries `confirmation_prompt`
  // (the real, specific text from ConfirmationManager.build_prompt —
  // never a vague "Allow?"), `pending_tool_id`, `pending_target`, and
  // `pending_risk_level`. On COMPLETED, carries the task's real result.
  // Left as a loosely-typed record here rather than a full discriminated
  // union — the backend itself types this as a bare `dict | None`.
  result: Record<string, unknown> | null;
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
  error: Record<string, unknown> | null;
  actual_result: Record<string, unknown> | null;
}
