import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import PlatformPanel from "./PlatformPanel";

vi.mock("../api");

const mockedApi = vi.mocked(api);

const integration = {
  id: "reference",
  name: "Reference Integration",
  category: "custom" as const,
  auth_method: "API_KEY" as const,
  description: "A reference integration.",
  state: "CONNECT_REQUIRED" as const,
  connected: false,
  scopes: [],
  connected_at: null,
  last_health_check_at: null,
};

const device = {
  id: "device-1",
  name: "Mock AC",
  type: "AC" as const,
  trust_status: "PAIRED" as const,
  pairing_stage: "REGISTER_CAPABILITIES" as const,
  last_seen_at: null,
};

const plugin = {
  id: "plugin-1",
  manifest_id: "mock-plugin",
  name: "Mock Plugin",
  version: "1.0.0",
  author: "test",
  state: "ENABLED" as const,
  permissions: [{ permission: "filesystem.read", granted: true }],
};

beforeEach(() => {
  vi.resetAllMocks();
  mockedApi.listIntegrations.mockResolvedValue([integration]);
  mockedApi.listDevices.mockResolvedValue([device]);
  mockedApi.listPlugins.mockResolvedValue([plugin]);
});

describe("PlatformPanel", () => {
  it("renders integrations, devices, and plugins from the real API", async () => {
    render(<PlatformPanel />);

    await waitFor(() => {
      expect(screen.getByText(/Reference Integration/)).toBeInTheDocument();
    });
    expect(screen.getByText("Turn On").closest("li")).toHaveTextContent(
      "Mock AC — PAIRED (REGISTER_CAPABILITIES)",
    );
    expect(screen.getByText(/Mock Plugin/)).toBeInTheDocument();
    expect(screen.getByText(/filesystem.read ✓/)).toBeInTheDocument();
  });

  it("shows an empty-state message when no plugins are installed", async () => {
    mockedApi.listPlugins.mockResolvedValue([]);
    render(<PlatformPanel />);
    await waitFor(() => {
      expect(screen.getByText("None installed.")).toBeInTheDocument();
    });
  });

  it("connecting an integration calls the real API and refreshes the list", async () => {
    mockedApi.connectIntegration.mockResolvedValue({ ...integration, connected: true });
    render(<PlatformPanel />);

    await waitFor(() => expect(screen.getByText(/Reference Integration/)).toBeInTheDocument());
    fireEvent.click(screen.getByText("Connect"));

    await waitFor(() => {
      expect(mockedApi.connectIntegration).toHaveBeenCalledWith("reference", "demo-key");
    });
    expect(mockedApi.listIntegrations).toHaveBeenCalledTimes(2); // initial + post-action refresh
  });

  it("turning the mock AC on invokes the tool with the device id as target", async () => {
    mockedApi.invokeTool.mockResolvedValue({
      call_id: "x",
      status: "SUCCESS",
      output: {},
      error: null,
      evidence_tier_used: null,
      duration_ms: 1,
    });
    render(<PlatformPanel />);

    await waitFor(() => expect(screen.getByText("Turn On")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Turn On"));

    await waitFor(() => {
      expect(mockedApi.invokeTool).toHaveBeenCalledWith(
        "iot.mock_ac.set_power",
        { power: true },
        "device-1",
      );
    });
  });

  it("surfaces an error message when an action fails", async () => {
    mockedApi.connectIntegration.mockRejectedValue(new Error("boom"));
    render(<PlatformPanel />);

    await waitFor(() => expect(screen.getByText("Connect")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Connect"));

    await waitFor(() => {
      expect(screen.getByText("boom")).toBeInTheDocument();
    });
  });
});
