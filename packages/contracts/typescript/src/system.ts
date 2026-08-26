// Mirrors services/local-api/app/api/system.py's SystemStatus response
// model. Backs the Phase 1 status screen — product brief §40.

export type ComponentStatus =
  | "CONNECTED"
  | "NOT CONFIGURED"
  | "NOT ENABLED"
  | "NOT CONNECTED"
  | "ACTIVE"
  | "ERROR";

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
}

export interface HealthResponse {
  status: string;
  timestamp: string;
}
