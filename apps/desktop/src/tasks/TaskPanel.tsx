import { useEffect, useState, type FormEvent } from "react";

import type { TaskOut, TaskStepOut } from "@veyra/contracts";

import { cancelTask, confirmTask, createAndRunTask, getTask, getTaskSteps } from "../api";

// Phase 13 (docs/phase-13-audit.md §8) — closes the two highest-
// visibility gaps the audit found: before this, a user driving VEYRA
// through the desktop app had no way to start, watch, or approve a task
// at all — only the low-level, single-tool-call DevConsole. This panel
// drives the real plan -> execute -> observe -> verify -> recover
// pipeline through the same `/tasks` API any other caller uses, and
// renders the real `confirmation_prompt` a WAITING_PERMISSION task
// carries (ConfirmationManager.build_prompt — never a vague "Allow?").
// Deliberately minimal: one task at a time, no history list, no
// retry/inspect UI, no ALLOW-FOR-THIS-TASK-vs-ALLOW-ONCE scope picker —
// docs/phase-13-audit.md §10 defers the full command-center polish.
const POLL_INTERVAL_MS = 1000;

const TERMINAL_STATES = new Set(["COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"]);
const ACTIVE_STATES = new Set([
  "RECEIVED",
  "UNDERSTANDING",
  "PLANNING",
  "WAITING_PERMISSION",
  "EXECUTING",
  "OBSERVING",
  "VERIFYING",
  "RECOVERING",
  "WAITING_USER",
  "PAUSED",
]);

function stateClassName(state: string): string {
  if (state === "COMPLETED") return "status-ok";
  if (state === "FAILED" || state === "CANCELLED" || state === "TIMED_OUT") return "status-error";
  return "status-neutral";
}

export default function TaskPanel() {
  const [description, setDescription] = useState("");
  const [task, setTask] = useState<TaskOut | null>(null);
  const [steps, setSteps] = useState<TaskStepOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // A self-rescheduling timeout rather than setInterval: each tick only
  // queues the next one after its own request settles, so a slow poll
  // can never stack up overlapping requests. Depending on the whole
  // `task` object (not just its id/state) keeps this honest for
  // react-hooks/exhaustive-deps — the effect legitimately reads `task`
  // to decide whether to keep polling, and naturally re-arms on every
  // fresh state the poll itself produces.
  useEffect(() => {
    if (!task || TERMINAL_STATES.has(task.state)) {
      return;
    }
    let cancelled = false;
    const id = task.id;

    const timeoutId = setTimeout(async () => {
      try {
        const [nextTask, nextSteps] = await Promise.all([getTask(id), getTaskSteps(id)]);
        if (!cancelled) {
          setTask(nextTask);
          setSteps(nextSteps);
        }
      } catch {
        // A transient poll failure (e.g. backend restart mid-task)
        // shouldn't wipe the last-known state off the screen — the
        // top-level App status already surfaces API connectivity loss.
      }
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [task]);

  async function handleStartTask(event: FormEvent) {
    event.preventDefault();
    if (!description.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await createAndRunTask(description.trim());
      setTask(created);
      setSteps(await getTaskSteps(created.id));
      setDescription("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  async function handleCancel() {
    if (!task) return;
    setBusy(true);
    setError(null);
    try {
      setTask(await cancelTask(task.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm(decision: "ALLOW_ONCE" | "DENY") {
    if (!task) return;
    setBusy(true);
    setError(null);
    try {
      setTask(await confirmTask(task.id, decision));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  const isActive = task ? ACTIVE_STATES.has(task.state) : false;
  const confirmationPrompt =
    task?.state === "WAITING_PERMISSION" && task.result
      ? (task.result.confirmation_prompt as string | undefined)
      : undefined;
  const isAwaitingConfirmation = Boolean(confirmationPrompt);

  return (
    <section className="platform-panel">
      <h2>VEYRA Tasks</h2>
      <p className="dev-console-hint">
        Runs a real task through the plan → execute → observe → verify → recover pipeline
        (Policy Engine included) — the same API any other caller of VEYRA uses.
      </p>

      {error && <p className="status-error">{error}</p>}

      <form className="dev-console-row" onSubmit={handleStartTask}>
        <label htmlFor="task-description">Task</label>
        <input
          id="task-description"
          type="text"
          placeholder='e.g. "Open Notepad"'
          value={description}
          disabled={busy || isActive}
          onChange={(event) => setDescription(event.target.value)}
        />
        <button type="submit" disabled={busy || isActive || !description.trim()}>
          Run Task
        </button>
      </form>

      {task && (
        <div className="task-current">
          <div className="platform-list-item">
            <span>
              <strong>{task.description}</strong> — step {task.current_step}/{task.total_steps}
            </span>
            <span className={stateClassName(task.state)}>{task.state}</span>
            {isActive && (
              <button disabled={busy} onClick={handleCancel}>
                Cancel
              </button>
            )}
          </div>

          {isAwaitingConfirmation && confirmationPrompt && (
            <div className="task-confirmation" role="alert">
              <p>{confirmationPrompt}</p>
              <button disabled={busy} onClick={() => handleConfirm("ALLOW_ONCE")}>
                Allow
              </button>
              <button disabled={busy} onClick={() => handleConfirm("DENY")}>
                Deny
              </button>
            </div>
          )}

          {task.state === "FAILED" && task.failure_reason && (
            <p className="status-error">{task.failure_reason}</p>
          )}

          <ul className="platform-list">
            {steps.map((step) => (
              <li key={step.id} className="platform-list-item">
                <span>
                  #{step.step_number} {step.description ?? step.tool_id} —{" "}
                  <em className={stateClassName(step.state)}>{step.state}</em>
                  {step.retry_count > 0 && ` (retried ${step.retry_count}x)`}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
