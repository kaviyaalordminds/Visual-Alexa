import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { SystemStatus } from "@veyra/contracts";

import * as api from "./api";
import App from "./App";

vi.mock("./api");
vi.mock("./avatar/useAvatarSocket", () => ({
  useAvatarSocket: () => ({
    agentState: "IDLE",
    visemes: [],
    outcome: null,
    speakingStartedAt: null,
    connected: false,
  }),
}));
vi.mock("./browser/BrowserPanel", () => ({ default: () => null }));
vi.mock("./DevConsole", () => ({ default: () => null }));
vi.mock("./platform/PlatformPanel", () => ({ default: () => null }));

const mockedApi = vi.mocked(api);

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

const baseStatus: SystemStatus = {
  desktop: "CONNECTED",
  local_api: "CONNECTED",
  database: "CONNECTED",
  ai: "NOT CONFIGURED",
  voice: "NOT CONFIGURED",
  vision: "NOT CONFIGURED",
  computer_control: "NOT ENABLED",
  iot: "NOT CONNECTED",
  security: "ACTIVE",
};

describe("App status poll", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("a stale, slow response never overwrites a newer one that already resolved", async () => {
    const first = deferred<SystemStatus>();
    const second = deferred<SystemStatus>();
    mockedApi.getSystemStatus.mockReturnValueOnce(first.promise);
    mockedApi.getSystemStatus.mockReturnValueOnce(second.promise);

    render(<App />);

    // Advance to fire the second poll while the first is still pending.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(mockedApi.getSystemStatus).toHaveBeenCalledTimes(2);

    function aiRowText(): string | null {
      const row = screen.getByText("AI").closest(".status-row");
      return row?.querySelector("dd")?.textContent ?? null;
    }

    // Newer request (second) resolves first — its data should render.
    await act(async () => {
      second.resolve({ ...baseStatus, ai: "DEGRADED" });
    });
    expect(aiRowText()).toBe("DEGRADED");

    // Older, now-stale request (first) finally resolves — must NOT
    // overwrite the newer AI status that's already on screen.
    await act(async () => {
      first.resolve({ ...baseStatus, ai: "NOT CONFIGURED" });
    });
    expect(aiRowText()).toBe("DEGRADED");
  });
});
