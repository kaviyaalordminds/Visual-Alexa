// Mirrors packages/contracts/python/veyra_contracts/tools.py and
// services/local-api's /tools API — the developer diagnostic panel
// (product brief §36-37) is the only Phase 2 consumer of these in the
// desktop shell.

import type { RiskLevel, ToolCategory } from "./enums";

export interface ToolDefinition {
  id: string;
  name: string;
  description: string;
  category: ToolCategory;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  risk_level: RiskLevel;
  required_permission: string;
  confirmation_policy: "NEVER" | "SESSION" | "ALWAYS";
  timeout_seconds: number;
  cancellable: boolean;
  verification_strategy: string;
  // Phase 7 (docs/phase-7/TOOL-DISCOVERY.md, INTEGRATION-ARCHITECTURE.md)
  // — both additive.
  keywords: string[];
  integration_id: string | null;
}

export interface VerificationOutcome {
  passed: boolean;
  method: string;
  detail?: string | null;
}

export interface ErrorInfo {
  code: string;
  message: string;
  retryable: boolean;
  user_action_required: boolean;
  recovery_strategy?: string | null;
  correlation_id: string;
}

export interface ToolResult {
  call_id: string;
  status: "SUCCESS" | "FAILURE" | "TIMEOUT" | "CANCELLED";
  output: Record<string, unknown> | null;
  error: ErrorInfo | null;
  evidence_tier_used: string | null;
  duration_ms: number;
}
