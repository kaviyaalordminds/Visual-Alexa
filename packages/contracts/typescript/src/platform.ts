// Mirrors the Pydantic response models in services/local-api's
// app/api/integrations.py, app/api/devices.py, app/api/plugins.py.
// docs/phase-7/*.

import type {
  AuthMethod,
  DevicePairingStage,
  DeviceTrustStatus,
  DeviceType,
  IntegrationState,
  PluginState,
  ToolCategory,
} from "./enums";

export interface IntegrationOut {
  id: string;
  name: string;
  category: ToolCategory;
  auth_method: AuthMethod;
  description: string;
  state: IntegrationState;
  connected: boolean;
  scopes: string[];
  connected_at: string | null;
  last_health_check_at: string | null;
}

export interface DeviceOut {
  id: string;
  name: string;
  type: DeviceType;
  trust_status: DeviceTrustStatus;
  pairing_stage: DevicePairingStage | null;
  last_seen_at: string | null;
}

export interface PluginPermissionOut {
  permission: string;
  granted: boolean;
}

export interface PluginOut {
  id: string;
  manifest_id: string;
  name: string;
  version: string;
  author: string;
  state: PluginState;
  permissions: PluginPermissionOut[];
}
