import { useEffect, useState } from "react";

import type { ToolDefinition, ToolResult } from "@veyra/contracts";

import { invokeTool, listTools } from "./api";

// docs/phase-2 §36-37: a developer/testing panel, NOT the final UI.
// Every invocation here goes through the exact same Tool Registry ->
// Policy Engine -> Executor path (services/local-api/app/services/
// tool_execution.py) that a future AI planner will use — see
// docs/phase-2 §41. There is deliberately no free-form command box: only
// a fixed set of registered, mostly read-only diagnostic tools can be
// selected, and every call is still policy-checked and audited like any
// other tool call.
const DIAGNOSTIC_TOOL_IDS = [
  "application.list_running",
  "window.list",
  "window.get_active",
  "filesystem.search",
  "screen.capture",
] as const;

type DiagnosticToolId = (typeof DIAGNOSTIC_TOOL_IDS)[number];

function defaultArgsFor(toolId: DiagnosticToolId): Record<string, unknown> {
  if (toolId === "filesystem.search") {
    return { directory: "" };
  }
  return {};
}

export default function DevConsole() {
  const [tools, setTools] = useState<ToolDefinition[]>([]);
  const [selected, setSelected] = useState<DiagnosticToolId>(DIAGNOSTIC_TOOL_IDS[0]);
  const [directory, setDirectory] = useState("");
  const [lastResult, setLastResult] = useState<ToolResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listTools()
      .then(setTools)
      .catch(() => setTools([]));
  }, []);

  const selectedDefinition = tools.find((t) => t.id === selected);

  async function handleRun() {
    setBusy(true);
    setError(null);
    try {
      const args =
        selected === "filesystem.search" ? { directory } : defaultArgsFor(selected);
      const result = await invokeTool(selected, args);
      setLastResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="dev-console">
      <h2>VEYRA Computer Control — Developer Console</h2>
      <p className="dev-console-hint">
        Diagnostics only. Every call below goes through the real Tool Registry and
        Policy Engine — nothing here bypasses it.
      </p>

      <div className="dev-console-row">
        <label htmlFor="tool-select">Tool</label>
        <select
          id="tool-select"
          value={selected}
          onChange={(e) => setSelected(e.target.value as DiagnosticToolId)}
        >
          {DIAGNOSTIC_TOOL_IDS.map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>
      </div>

      {selected === "filesystem.search" && (
        <div className="dev-console-row">
          <label htmlFor="directory-input">Directory</label>
          <input
            id="directory-input"
            value={directory}
            onChange={(e) => setDirectory(e.target.value)}
            placeholder="/path/to/search"
          />
        </div>
      )}

      <button onClick={handleRun} disabled={busy}>
        {busy ? "Running…" : "Run"}
      </button>

      {error && <p className="status-error">{error}</p>}

      <dl className="dev-console-summary">
        <div>
          <dt>Recent Tool</dt>
          <dd>{lastResult ? selected : "—"}</dd>
        </div>
        <div>
          <dt>Tool Status</dt>
          <dd>{lastResult?.status ?? "—"}</dd>
        </div>
        <div>
          <dt>Permission</dt>
          <dd>{selectedDefinition?.risk_level ?? "—"}</dd>
        </div>
        <div>
          <dt>Verification</dt>
          <dd>
            {lastResult?.output && typeof lastResult.output.verification === "object"
              ? JSON.stringify(lastResult.output.verification)
              : "—"}
          </dd>
        </div>
      </dl>

      {lastResult && (
        <pre className="dev-console-output">{JSON.stringify(lastResult, null, 2)}</pre>
      )}
    </section>
  );
}
