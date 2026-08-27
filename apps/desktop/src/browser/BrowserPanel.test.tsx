import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import BrowserPanel from "./BrowserPanel";

vi.mock("../api");

const mockedApi = vi.mocked(api);

const session = {
  session_id: "session-1",
  browser_type: "chromium",
  connection_status: "READY",
  created_at: "2026-01-01T00:00:00Z",
  last_activity: "2026-01-01T00:00:00Z",
  active_tab_id: "tab-1",
  tabs: [
    {
      tab_id: "tab-1",
      title: "Example",
      url: "https://example.com/",
      domain: "example.com",
      status: "complete",
      active: true,
      favicon: null,
    },
  ],
};

beforeEach(() => {
  vi.resetAllMocks();
  mockedApi.listBrowserSessions.mockResolvedValue([session]);
});

describe("BrowserPanel", () => {
  it("renders sessions and tabs from the real API", async () => {
    render(<BrowserPanel />);
    await waitFor(() => {
      expect(screen.getByText(/chromium/)).toBeInTheDocument();
    });
    expect(screen.getByText(/Example/)).toBeInTheDocument();
  });

  it("shows an empty-state message when no sessions are active", async () => {
    mockedApi.listBrowserSessions.mockResolvedValue([]);
    render(<BrowserPanel />);
    await waitFor(() => {
      expect(screen.getByText("No active sessions.")).toBeInTheDocument();
    });
  });

  it("launching a browser calls the real invokeTool API and refreshes", async () => {
    mockedApi.invokeTool.mockResolvedValue({
      call_id: "x",
      status: "SUCCESS",
      output: {},
      error: null,
      evidence_tier_used: null,
      duration_ms: 1,
    });
    mockedApi.listBrowserSessions.mockResolvedValueOnce([]).mockResolvedValueOnce([session]);
    render(<BrowserPanel />);

    await waitFor(() => expect(screen.getByText("Launch Browser")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Launch Browser"));

    await waitFor(() => {
      expect(mockedApi.invokeTool).toHaveBeenCalledWith("browser.launch", {});
    });
  });

  it("closing a session calls the real API with the session id as target", async () => {
    mockedApi.closeBrowserSession.mockResolvedValue({
      call_id: "x",
      status: "SUCCESS",
      output: {},
      error: null,
      evidence_tier_used: null,
      duration_ms: 1,
    });
    render(<BrowserPanel />);

    await waitFor(() => expect(screen.getByText("Close")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Close"));

    await waitFor(() => {
      expect(mockedApi.closeBrowserSession).toHaveBeenCalledWith("session-1");
    });
  });

  it("surfaces an error message when an action fails", async () => {
    mockedApi.invokeTool.mockRejectedValue(new Error("boom"));
    render(<BrowserPanel />);

    await waitFor(() => expect(screen.getByText("Launch Browser")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Launch Browser"));

    await waitFor(() => {
      expect(screen.getByText("boom")).toBeInTheDocument();
    });
  });
});
