import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { TaskOut, TaskStepOut } from "@veyra/contracts";

import * as api from "../api";
import TaskPanel from "./TaskPanel";

vi.mock("../api");

const mockedApi = vi.mocked(api);

function makeTask(overrides: Partial<TaskOut> = {}): TaskOut {
  return {
    id: "task-1",
    description: "Open Notepad",
    state: "EXECUTING",
    max_steps: 20,
    timeout_seconds: 120,
    max_recovery_attempts: 3,
    correlation_id: "corr-1",
    created_at: "2026-01-01T00:00:00Z",
    current_step: 1,
    total_steps: 2,
    requires_confirmation: false,
    failure_reason: null,
    result: null,
    ...overrides,
  };
}

const step: TaskStepOut = {
  id: "step-1",
  step_number: 1,
  state: "COMPLETED",
  tool_id: "application.open",
  description: "Open Notepad",
  arguments: {},
  risk_level: "SAFE",
  retry_count: 0,
  error: null,
  actual_result: null,
};

beforeEach(() => {
  vi.resetAllMocks();
  mockedApi.getTaskSteps.mockResolvedValue([step]);
});

describe("TaskPanel", () => {
  it("starts a task through the real API and renders its progress", async () => {
    const created = makeTask();
    mockedApi.createAndRunTask.mockResolvedValue(created);

    render(<TaskPanel />);
    fireEvent.change(screen.getByLabelText("Task"), { target: { value: "Open Notepad" } });
    fireEvent.click(screen.getByText("Run Task"));

    await waitFor(() => {
      expect(mockedApi.createAndRunTask).toHaveBeenCalledWith("Open Notepad");
    });
    expect(await screen.findByText("EXECUTING")).toBeInTheDocument();
    expect(screen.getAllByText(/Open Notepad/).length).toBeGreaterThan(0);
  });

  it("renders the real confirmation_prompt with working Allow/Deny controls", async () => {
    const pending = makeTask({
      state: "WAITING_PERMISSION",
      result: {
        confirmation_prompt: "filesystem.delete — /tmp/report.pdf. Risk: SENSITIVE. Continue?",
        pending_tool_id: "filesystem.delete",
      },
    });
    mockedApi.createAndRunTask.mockResolvedValue(pending);
    mockedApi.confirmTask.mockResolvedValue(makeTask({ state: "EXECUTING" }));

    render(<TaskPanel />);
    fireEvent.change(screen.getByLabelText("Task"), { target: { value: "Delete report" } });
    fireEvent.click(screen.getByText("Run Task"));

    expect(
      await screen.findByText("filesystem.delete — /tmp/report.pdf. Risk: SENSITIVE. Continue?"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByText("Allow"));
    await waitFor(() => {
      expect(mockedApi.confirmTask).toHaveBeenCalledWith("task-1", "ALLOW_ONCE");
    });
  });

  it("Deny sends a real DENY decision", async () => {
    const pending = makeTask({
      state: "WAITING_PERMISSION",
      result: { confirmation_prompt: "process.kill — chrome.exe. Risk: CRITICAL. Continue?" },
    });
    mockedApi.createAndRunTask.mockResolvedValue(pending);
    mockedApi.confirmTask.mockResolvedValue(makeTask({ state: "CANCELLED" }));

    render(<TaskPanel />);
    fireEvent.change(screen.getByLabelText("Task"), { target: { value: "Kill Chrome" } });
    fireEvent.click(screen.getByText("Run Task"));

    fireEvent.click(await screen.findByText("Deny"));
    await waitFor(() => {
      expect(mockedApi.confirmTask).toHaveBeenCalledWith("task-1", "DENY");
    });
  });

  it("Cancel sends a real cancel request while a task is active", async () => {
    const running = makeTask({ state: "EXECUTING" });
    mockedApi.createAndRunTask.mockResolvedValue(running);
    mockedApi.cancelTask.mockResolvedValue(makeTask({ state: "CANCELLED" }));

    render(<TaskPanel />);
    fireEvent.change(screen.getByLabelText("Task"), { target: { value: "Open Notepad" } });
    fireEvent.click(screen.getByText("Run Task"));

    fireEvent.click(await screen.findByText("Cancel"));
    await waitFor(() => {
      expect(mockedApi.cancelTask).toHaveBeenCalledWith("task-1");
    });
  });

  it("never polls once a task has reached a terminal state", async () => {
    vi.useFakeTimers();
    try {
      const done = makeTask({ state: "COMPLETED", current_step: 2, total_steps: 2 });
      mockedApi.createAndRunTask.mockResolvedValue(done);

      render(<TaskPanel />);
      fireEvent.change(screen.getByLabelText("Task"), { target: { value: "Open Notepad" } });
      await act(async () => {
        fireEvent.click(screen.getByText("Run Task"));
      });

      expect(mockedApi.getTask).not.toHaveBeenCalled();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000);
      });
      expect(mockedApi.getTask).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it("polls for live progress while a task is active", async () => {
    vi.useFakeTimers();
    try {
      const running = makeTask({ state: "EXECUTING" });
      mockedApi.createAndRunTask.mockResolvedValue(running);
      mockedApi.getTask.mockResolvedValue(makeTask({ state: "COMPLETED" }));

      render(<TaskPanel />);
      fireEvent.change(screen.getByLabelText("Task"), { target: { value: "Open Notepad" } });
      await act(async () => {
        fireEvent.click(screen.getByText("Run Task"));
      });

      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000);
      });
      expect(mockedApi.getTask).toHaveBeenCalledWith("task-1");
    } finally {
      vi.useRealTimers();
    }
  });
});
