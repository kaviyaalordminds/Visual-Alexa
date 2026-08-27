import { useEffect, useState } from "react";

import type { DeviceOut, IntegrationOut, PluginOut } from "@veyra/contracts";

import {
  authenticateDevice,
  authorizeDevice,
  connectIntegration,
  disconnectIntegration,
  grantDevicePermission,
  healthCheckIntegration,
  identifyDevice,
  invokeTool,
  listDevices,
  listIntegrations,
  listPlugins,
  pairDevice,
  registerDeviceCapabilities,
  revokeDevicePermission,
} from "../api";

// docs/phase-7/PHASE-7-IMPLEMENTATION-PLAN.md — a diagnostic panel in
// the same spirit as DevConsole.tsx, not "the final UI" for this
// surface. Every action here goes through the real HTTP API (Integration
// Registry / DevicePairingService / Plugin Registry), never a shortcut.
export default function PlatformPanel() {
  const [integrations, setIntegrations] = useState<IntegrationOut[]>([]);
  const [devices, setDevices] = useState<DeviceOut[]>([]);
  const [plugins, setPlugins] = useState<PluginOut[]>([]);
  const [secret, setSecret] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      const [i, d, p] = await Promise.all([listIntegrations(), listDevices(), listPlugins()]);
      setIntegrations(i);
      setDevices(d);
      setPlugins(p);
    } catch {
      // Local API unreachable — leave the last-known lists in place, App
      // already surfaces the top-level connectivity error.
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  async function pairAndSetUpMockAc() {
    const device = await pairDevice("Mock AC", "AC", "LOCAL_HTTP");
    await identifyDevice(device.id);
    await authenticateDevice(device.id, "mock-device-secret");
    await authorizeDevice(device.id);
    await registerDeviceCapabilities(device.id, ["power"]);
  }

  return (
    <section className="platform-panel">
      <h2>VEYRA Platform</h2>
      <p className="dev-console-hint">
        Integrations, devices, and plugins — every action below goes through the real
        Tool Registry / Policy Engine / Credential Manager, nothing here bypasses it.
      </p>

      {error && <p className="status-error">{error}</p>}

      <h3>Integrations</h3>
      <ul className="platform-list">
        {integrations.map((integration) => (
          <li key={integration.id} className="platform-list-item">
            <span>
              {integration.name} — <em>{integration.state}</em>
            </span>
            {integration.connected ? (
              <>
                <button
                  disabled={busy}
                  onClick={() => run(() => healthCheckIntegration(integration.id))}
                >
                  Health Check
                </button>
                <button
                  disabled={busy}
                  onClick={() => run(() => disconnectIntegration(integration.id))}
                >
                  Disconnect
                </button>
              </>
            ) : (
              <button
                disabled={busy}
                onClick={() => run(() => connectIntegration(integration.id, secret || "demo-key"))}
              >
                Connect
              </button>
            )}
          </li>
        ))}
      </ul>
      <div className="dev-console-row">
        <label htmlFor="integration-secret">API key (for Connect)</label>
        <input
          id="integration-secret"
          value={secret}
          onChange={(e) => setSecret(e.target.value)}
          placeholder="demo-key"
        />
      </div>

      <h3>Devices</h3>
      <button disabled={busy} onClick={() => run(pairAndSetUpMockAc)}>
        Pair a Mock AC
      </button>
      <ul className="platform-list">
        {devices.map((device) => (
          <li key={device.id} className="platform-list-item">
            <span>
              {device.name} — <em>{device.trust_status}</em> ({device.pairing_stage ?? "—"})
            </span>
            {device.pairing_stage === "REGISTER_CAPABILITIES" ||
            device.pairing_stage === "CONTROL" ? (
              <>
                <button
                  disabled={busy}
                  onClick={() => run(() => grantDevicePermission(device.id, "power"))}
                >
                  Grant Power
                </button>
                <button
                  disabled={busy}
                  onClick={() => run(() => revokeDevicePermission(device.id, "power"))}
                >
                  Revoke Power
                </button>
                <button
                  disabled={busy}
                  onClick={() =>
                    run(() => invokeTool("iot.mock_ac.set_power", { power: true }, device.id))
                  }
                >
                  Turn On
                </button>
                <button
                  disabled={busy}
                  onClick={() =>
                    run(() => invokeTool("iot.mock_ac.set_power", { power: false }, device.id))
                  }
                >
                  Turn Off
                </button>
              </>
            ) : null}
          </li>
        ))}
      </ul>

      <h3>Plugins</h3>
      <ul className="platform-list">
        {plugins.length === 0 && <li className="platform-list-item">None installed.</li>}
        {plugins.map((plugin) => (
          <li key={plugin.id} className="platform-list-item">
            <span>
              {plugin.name} v{plugin.version} — <em>{plugin.state}</em>
            </span>
            <span className="platform-permissions">
              {plugin.permissions.map((p) => `${p.permission}${p.granted ? " ✓" : ""}`).join(", ")}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
