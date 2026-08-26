import type { HealthResponse, SystemStatus } from "@veyra/contracts";

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
