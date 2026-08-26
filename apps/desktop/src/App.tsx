import { useEffect, useState } from "react";

import type { ComponentStatus, SystemStatus } from "@veyra/contracts";

import { getSystemStatus } from "./api";

// Phase 1 technical shell only — product brief §40: "This is NOT the final
// UI. Do not spend excessive time on visual design."
const POLL_INTERVAL_MS = 5000;

const ROWS: Array<{ key: keyof SystemStatus; label: string }> = [
  { key: "desktop", label: "Desktop" },
  { key: "local_api", label: "Local API" },
  { key: "database", label: "Database" },
  { key: "ai", label: "AI" },
  { key: "voice", label: "Voice" },
  { key: "vision", label: "Vision" },
  { key: "computer_control", label: "Computer Control" },
  { key: "iot", label: "IoT" },
  { key: "security", label: "Security" },
];

function statusClassName(status: ComponentStatus): string {
  if (status === "CONNECTED" || status === "ACTIVE") return "status-ok";
  if (status === "ERROR") return "status-error";
  return "status-neutral";
}

export default function App() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const next = await getSystemStatus();
        if (!cancelled) {
          setStatus(next);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setStatus(null);
          setError(err instanceof Error ? err.message : "Unknown error");
        }
      }
    }

    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <main className="shell">
      <h1>VEYRA</h1>
      <p className="tagline">Local-first Visual AI Computer Operating Layer</p>

      {error && (
        <p className="status-error" role="alert">
          Local API unreachable: {error}
        </p>
      )}

      <dl className="status-list">
        {ROWS.map(({ key, label }) => {
          const value = status ? status[key] : "NOT CONNECTED";
          return (
            <div className="status-row" key={key}>
              <dt>{label}</dt>
              <dd className={statusClassName(value)}>{value}</dd>
            </div>
          );
        })}
      </dl>
    </main>
  );
}
