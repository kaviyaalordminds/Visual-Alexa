import { useEffect, useRef, useState } from "react";

import type { PermissionDecision, TaskOut, TaskStepOut } from "@veyra/contracts";

import { cancelTask, confirmTask, createTask, getTask, getTaskSteps, runTask } from "../api";

// The real plan -> execute -> observe -> verify -> recover pipeline
// (docs/architecture/14-TASK-LIFECYCLE.md, docs/phase-4/TASK-API.md) —
// the same /tasks API any other caller of VEYRA uses, Policy Engine
// included. Previously nothing in the desktop shell drove this at all;
// DevConsole only exposes a fixed set of read-only diagnostic tools.
const ACTIVE_STATES = new Set([
  "RECEIVED",
  "UNDERSTANDING",
  "PLANNING",
  "EXECUTING",
  "OBSERVING",
  "VERIFYING",
  "RECOVERING",
]);
const POLL_INTERVAL_MS = 600;

function stepClassName(state: TaskStepOut["state"]): string {
  if (state === "COMPLETED") return "task-step-completed";
  if (state === "FAILED" || state === "CANCELLED" || state === "TIMED_OUT") {
    return "task-step-failed";
  }
  if (state === "WAITING_PERMISSION" || state === "WAITING_USER" || state === "PAUSED") {
    return "task-step-waiting";
  }
  return "task-step-active";
}

const DECISIONS: Array<{ decision: PermissionDecision; label: string }> = [
  { decision: "ALLOW_ONCE", label: "Allow Once" },
  { decision: "ALLOW_SESSION", label: "Allow for Session" },
  { decision: "ALWAYS_ALLOW", label: "Always Allow" },
  { decision: "DENY", label: "Deny" },
];

export default function TaskRunner() {
  const [description, setDescription] = useState("");
  const [task, setTask] = useState<TaskOut | null>(null);
  const [steps, setSteps] = useState<TaskStepOut[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current !== null) window.clearInterval(pollRef.current);
    };
  }, []);

  function stopPolling() {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  function startPolling(taskId: string) {
    stopPolling();
    pollRef.current = window.setInterval(async () => {
      try {
        const [latest, latestSteps] = await Promise.all([
          getTask(taskId),
          getTaskSteps(taskId),
        ]);
        setTask(latest);
        setSteps(latestSteps);
        if (!ACTIVE_STATES.has(latest.state)) stopPolling();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
        stopPolling();
      }
    }, POLL_INTERVAL_MS);
  }

  async function handleRun() {
    if (!description.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await createTask(description.trim());
      setTask(created);
      setSteps([]);
      await runTask(created.id);
      startPolling(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  async function handleCancel() {
    if (!task) return;
    setBusy(true);
    try {
      await cancelTask(task.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  async function handleDecision(decision: PermissionDecision) {
    if (!task) return;
    setBusy(true);
    setError(null);
    try {
      await confirmTask(task.id, decision);
      startPolling(task.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  const waitingOnConfirmation = task?.state === "WAITING_PERMISSION" && task.result?.confirmation_prompt;

  return (
    <section className="task-runner">
      <h2>VEYRA Tasks</h2>
      <p className="dev-console-hint">
        Runs a real task through the plan → execute → observe → verify → recover pipeline
        (Policy Engine included) — the same API any other caller of VEYRA uses.
      </p>

      <div className="dev-console-row">
        <label htmlFor="task-description">Task</label>
        <input
          id="task-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleRun()}
          placeholder='e.g. "Open Notepad"'
          disabled={busy}
        />
      </div>
      <button onClick={handleRun} disabled={busy || !description.trim()}>
        Run Task
      </button>

      {error && <p className="status-error">{error}</p>}

      {task && (
        <div className="task-current">
          <div className="task-current-header">
            <strong>{task.description}</strong>
            <span>
              step {task.current_step}/{task.total_steps || "?"}
            </span>
            {ACTIVE_STATES.has(task.state) && (
              <button className="task-cancel" disabled={busy} onClick={handleCancel}>
                Cancel
              </button>
            )}
          </div>

          {task.state === "FAILED" && task.failure_reason && (
            <p className="status-error">{task.failure_reason}</p>
          )}

          {waitingOnConfirmation && (
            <div className="task-confirmation">
              <p>{task.result?.confirmation_prompt}</p>
              <div className="task-confirmation-actions">
                {DECISIONS.map(({ decision, label }) => (
                  <button
                    key={decision}
                    className={decision === "DENY" ? "task-deny" : undefined}
                    disabled={busy}
                    onClick={() => handleDecision(decision)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          )}

          <ul className="platform-list">
            {steps.map((step) => (
              <li key={step.id} className={`platform-list-item ${stepClassName(step.state)}`}>
                <span>
                  #{step.step_number} {step.description ?? step.tool_id}
                </span>
                <em>{step.state}</em>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
