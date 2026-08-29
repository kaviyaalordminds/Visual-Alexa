import type {
  BrowserSessionInfo,
  DeviceOut,
  HealthResponse,
  IntegrationOut,
  PermissionDecision,
  PluginOut,
  SystemStatus,
  TaskBudget,
  TaskOut,
  TaskStepOut,
  ToolDefinition,
  ToolResult,
} from "@veyra/contracts";

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

async function postJSON<T>(path: string, body: Record<string, unknown> = {}): Promise<T> {
  const response = await fetch(`${LOCAL_API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
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
  target?: string,
): Promise<ToolResult> {
  const response = await fetch(`${LOCAL_API_BASE_URL}/tools/${toolId}/invoke`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ arguments: args, target: target ?? null }),
  });
  if (!response.ok) {
    throw new Error(`invoke ${toolId} responded with ${response.status}`);
  }
  return (await response.json()) as ToolResult;
}

// docs/phase-7/INTEGRATION-ARCHITECTURE.md
export function listIntegrations(): Promise<IntegrationOut[]> {
  return getJSON<IntegrationOut[]>("/integrations");
}

export function connectIntegration(id: string, secret: string): Promise<IntegrationOut> {
  return postJSON<IntegrationOut>(`/integrations/${id}/connect`, { secret });
}

export function disconnectIntegration(id: string): Promise<IntegrationOut> {
  return postJSON<IntegrationOut>(`/integrations/${id}/disconnect`);
}

export function healthCheckIntegration(id: string): Promise<IntegrationOut> {
  return postJSON<IntegrationOut>(`/integrations/${id}/health-check`);
}

// docs/phase-7/DEVICE-PAIRING.md
export function listDevices(): Promise<DeviceOut[]> {
  return getJSON<DeviceOut[]>("/devices");
}

export function pairDevice(
  name: string,
  type: string,
  protocol: string,
): Promise<DeviceOut> {
  return postJSON<DeviceOut>("/devices/pair", { name, type, protocol });
}

export function identifyDevice(id: string): Promise<DeviceOut> {
  return postJSON<DeviceOut>(`/devices/${id}/identify`);
}

export function authenticateDevice(id: string, secret: string): Promise<DeviceOut> {
  return postJSON<DeviceOut>(`/devices/${id}/authenticate`, { secret });
}

export function authorizeDevice(id: string): Promise<DeviceOut> {
  return postJSON<DeviceOut>(`/devices/${id}/authorize`);
}

export function registerDeviceCapabilities(
  id: string,
  capabilityKeys: string[],
): Promise<DeviceOut> {
  return postJSON<DeviceOut>(`/devices/${id}/register-capabilities`, {
    capability_keys: capabilityKeys,
  });
}

export function grantDevicePermission(id: string, capabilityKey: string): Promise<unknown> {
  return postJSON(`/devices/${id}/permissions/grant`, { capability_key: capabilityKey });
}

export function revokeDevicePermission(id: string, capabilityKey: string): Promise<unknown> {
  return postJSON(`/devices/${id}/permissions/revoke`, { capability_key: capabilityKey });
}

// docs/phase-7/PLUGIN-ARCHITECTURE.md
export function listPlugins(): Promise<PluginOut[]> {
  return getJSON<PluginOut[]>("/plugins");
}

// docs/phase-8/BROWSER-SESSION.md
export function listBrowserSessions(): Promise<BrowserSessionInfo[]> {
  return getJSON<BrowserSessionInfo[]>("/browser/sessions");
}

export function closeBrowserSession(sessionId: string): Promise<ToolResult> {
  return invokeTool("browser.close", {}, sessionId);
}

// docs/phase-4/TASK-API.md, docs/phase-13-audit.md §8 — the real
// plan -> execute -> observe -> verify -> recover pipeline, driven the
// same way any other caller of this API drives it. No shortcut path.
const DEFAULT_TASK_BUDGET: TaskBudget = {
  max_steps: 20,
  timeout_seconds: 120,
  max_recovery_attempts: 3,
};

export function listTasks(): Promise<TaskOut[]> {
  return getJSON<TaskOut[]>("/tasks");
}

export function getTask(taskId: string): Promise<TaskOut> {
  return getJSON<TaskOut>(`/tasks/${taskId}`);
}

export function getTaskSteps(taskId: string): Promise<TaskStepOut[]> {
  return getJSON<TaskStepOut[]>(`/tasks/${taskId}/steps`);
}

export async function createAndRunTask(
  description: string,
  budget: TaskBudget = DEFAULT_TASK_BUDGET,
): Promise<TaskOut> {
  const task = await postJSON<TaskOut>("/tasks", { description, budget });
  return runTask(task.id);
}

export function runTask(taskId: string): Promise<TaskOut> {
  return postJSON<TaskOut>(`/tasks/${taskId}/run`);
}

export function cancelTask(taskId: string): Promise<TaskOut> {
  return postJSON<TaskOut>(`/tasks/${taskId}/cancel`);
}

export function confirmTask(
  taskId: string,
  decision: PermissionDecision,
): Promise<TaskOut> {
  return postJSON<TaskOut>(`/tasks/${taskId}/confirm`, { decision });
}
