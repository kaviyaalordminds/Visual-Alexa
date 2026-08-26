import type { HealthResponse, SystemStatus, ToolDefinition, ToolResult } from "@veyra/contracts";

// The Local API always binds to loopback only in Phase 1 — see
// docs/security/01-SECURITY-ARCHITECTURE.md. This is the one and only
// place the shell knows that address.
const LOCAL_API_BASE_URL = "http://127.0.0.1:8756";

async function getJSON<T>(path: string): Promise<T> {
  const response = await fetch(`${LOCAL_API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`${path} responded with ${response.status}`);
  }
  return (await response.json()) as T;
}

export function getHealth(): Promise<HealthResponse> {
  return getJSON<HealthResponse>("/health");
}

export function getSystemStatus(): Promise<SystemStatus> {
  return getJSON<SystemStatus>("/system");
}

export function listTools(): Promise<ToolDefinition[]> {
  return getJSON<ToolDefinition[]>("/tools");
}

// docs/phase-2 §37: the developer console only ever calls this — the same
// Tool Registry -> Policy Engine -> Executor path any future AI planner
// will use (docs/phase-2 §41). There is no other, "faster" path.
export async function invokeTool(
  toolId: string,
  args: Record<string, unknown>,
): Promise<ToolResult> {
  const response = await fetch(`${LOCAL_API_BASE_URL}/tools/${toolId}/invoke`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ arguments: args }),
  });
  if (!response.ok) {
    throw new Error(`invoke ${toolId} responded with ${response.status}`);
  }
  return (await response.json()) as ToolResult;
}
