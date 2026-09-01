import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { TaskOut, TaskStepOut } from "@veyra/contracts";

import * as api from "../api";
import TaskRunner from "./TaskRunner";

vi.mock("../api");

const mockedApi = vi.mocked(api);

function task(overrides: Partial<TaskOut> = {}): TaskOut {
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

function step(overrides: Partial<TaskStepOut> = {}): TaskStepOut {
  return {
    id: "step-1",
    step_number: 1,
    state: "COMPLETED",
    tool_id: "application.launch",
    description: "Launch Notepad.",
    arguments: {},
    risk_level: "SAFE",
    retry_count: 0,
    error: null,
    actual_result: null,
    ...overrides,
  };
}

const LONG_WAIT = { timeout: 3000 };

beforeEach(() => {
  vi.resetAllMocks();
});

describe("TaskRunner", () => {
  it("running a task calls the real create/run API and polls for progress", async () => {
    mockedApi.createTask.mockResolvedValue(task({ state: "RECEIVED" }));
    mockedApi.runTask.mockResolvedValue(task({ state: "RECEIVED" }));
    mockedApi.getTask.mockResolvedValue(task({ state: "COMPLETED", current_step: 2 }));
    mockedApi.getTaskSteps.mockResolvedValue([step(), step({ id: "step-2", step_number: 2 })]);

    render(<TaskRunner />);
    fireEvent.change(screen.getByLabelText("Task"), { target: { value: "Open Notepad" } });
    fireEvent.click(screen.getByText("Run Task"));

    await waitFor(() => {
      expect(mockedApi.createTask).toHaveBeenCalledWith("Open Notepad");
      expect(mockedApi.runTask).toHaveBeenCalledWith("task-1");
    });

    await waitFor(() => {
      expect(screen.getByText("step 2/2")).toBeInTheDocument();
    }, LONG_WAIT);
    expect(screen.getAllByText(/Launch Notepad/).length).toBe(2);
  });

  it("a WAITING_PERMISSION task shows the real confirmation prompt and decision buttons", async () => {
    const waiting = task({
      state: "WAITING_PERMISSION",
      result: { confirmation_prompt: "I'd like to Create Folder — /a/b. Should I go ahead?" },
    });
    mockedApi.createTask.mockResolvedValue(task({ state: "RECEIVED" }));
    mockedApi.runTask.mockResolvedValue(task({ state: "RECEIVED" }));
    mockedApi.getTask.mockResolvedValue(waiting);
    mockedApi.getTaskSteps.mockResolvedValue([]);
    mockedApi.confirmTask.mockResolvedValue(task({ state: "EXECUTING" }));

    render(<TaskRunner />);
    fireEvent.change(screen.getByLabelText("Task"), { target: { value: "make a folder" } });
    fireEvent.click(screen.getByText("Run Task"));

    await waitFor(() => {
      expect(
        screen.getByText("I'd like to Create Folder — /a/b. Should I go ahead?"),
      ).toBeInTheDocument();
    }, LONG_WAIT);

    fireEvent.click(screen.getByText("Always Allow"));
    await waitFor(() => {
      expect(mockedApi.confirmTask).toHaveBeenCalledWith("task-1", "ALWAYS_ALLOW");
    });
  });

  it("surfaces an error message when creating a task fails", async () => {
    mockedApi.createTask.mockRejectedValue(new Error("Local API unreachable"));

    render(<TaskRunner />);
    fireEvent.change(screen.getByLabelText("Task"), { target: { value: "Open Notepad" } });
    fireEvent.click(screen.getByText("Run Task"));

    await waitFor(() => {
      expect(screen.getByText("Local API unreachable")).toBeInTheDocument();
    });
  });

  it("cancelling an active task calls the real cancel API", async () => {
    mockedApi.createTask.mockResolvedValue(task({ state: "RECEIVED" }));
    mockedApi.runTask.mockResolvedValue(task({ state: "RECEIVED" }));
    mockedApi.getTask.mockResolvedValue(task({ state: "EXECUTING" }));
    mockedApi.getTaskSteps.mockResolvedValue([]);
    mockedApi.cancelTask.mockResolvedValue(task({ state: "CANCELLED" }));

    render(<TaskRunner />);
    fireEvent.change(screen.getByLabelText("Task"), { target: { value: "Open Notepad" } });
    fireEvent.click(screen.getByText("Run Task"));

    await waitFor(() => expect(screen.getByText("Cancel")).toBeInTheDocument(), LONG_WAIT);
    fireEvent.click(screen.getByText("Cancel"));

    await waitFor(() => {
      expect(mockedApi.cancelTask).toHaveBeenCalledWith("task-1");
    });
  });
});
