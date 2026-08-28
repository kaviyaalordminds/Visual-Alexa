import { useEffect, useRef, useState } from "react";

import type { ComponentStatus, SystemStatus } from "@veyra/contracts";

import { getSystemStatus } from "./api";
import { Avatar } from "./avatar/Avatar";
import type { ConnectionState } from "./avatar/state";
import { useAvatarSocket } from "./avatar/useAvatarSocket";
import BrowserPanel from "./browser/BrowserPanel";
import DevConsole from "./DevConsole";
import PlatformPanel from "./platform/PlatformPanel";

// Phase 1 shipped only a technical status shell (product brief §40: "This
// is NOT the final UI"). Phase 6 (docs/phase-6/AVATAR-ARCHITECTURE.md)
// adds VEYRA's actual visual identity above it; the status list and dev
// console remain for diagnostics rather than being removed.
const POLL_INTERVAL_MS = 5000;

type StatusRowKey = Exclude<keyof SystemStatus, "details" | "version" | "uptime_seconds">;

const ROWS: Array<{ key: StatusRowKey; label: string }> = [
  { key: "desktop", label: "Desktop" },
  { key: "local_api", label: "Local API" },
  { key: "database", label: "Database" },
  { key: "ai", label: "AI" },
  { key: "voice", label: "Voice" },
  { key: "vision", label: "Vision" },
  { key: "computer_control", label: "Computer Control" },
  // Phase 12 (PHASE_12_AUDIT.md §3/§8 P0-2) — real backend health checks
  // for these two now exist; previously there was no field for either.
  { key: "browser", label: "Browser" },
  { key: "memory", label: "Memory" },
  { key: "iot", label: "IoT" },
  { key: "security", label: "Security" },
];

function statusClassName(status: ComponentStatus): string {
  if (status === "CONNECTED" || status === "ACTIVE") return "status-ok";
  if (status === "ERROR") return "status-error";
  return "status-neutral";
}

// Phase 12 (PHASE_12_AUDIT.md §5) — previously only a boolean, so a fresh
// mount and a mid-backoff reconnect attempt looked identical in the UI.
function connectionStatusClassName(state: ConnectionState): string {
  if (state === "CONNECTED") return "status-ok";
  if (state === "ERROR" || state === "DISCONNECTED") return "status-error";
  return "status-neutral"; // CONNECTING / RECONNECTING — in progress, not a failure
}

export default function App() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const avatarState = useAvatarSocket();

  // Phase 10 P1 (docs/phase-10/TESTING-AUDIT.md item 4): a plain
  // `cancelled` flag only guards against a response landing after
  // *unmount* — it does nothing if two overlapping polls are in flight
  // at once (a slow request A, followed by a fast request B that
  // resolves first) and A's now-stale response then lands and silently
  // overwrites B's newer state. requestIdRef makes each poll's response
  // only apply if it's still the most recently *issued* one, regardless
  // of resolution order.
  const requestIdRef = useRef(0);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      const requestId = ++requestIdRef.current;
      try {
        const next = await getSystemStatus();
        if (!cancelled && requestId === requestIdRef.current) {
          setStatus(next);
          setError(null);
        }
      } catch (err) {
        if (!cancelled && requestId === requestIdRef.current) {
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

      <Avatar runtime={avatarState} />

      {error && (
        <p className="status-error" role="alert">
          Local API unreachable: {error}
        </p>
      )}

      <dl className="status-list">
        <div className="status-row">
          <dt>Live Updates (WebSocket)</dt>
          <dd className={connectionStatusClassName(avatarState.connectionState)}>
            {avatarState.connectionState}
          </dd>
        </div>
        {ROWS.map(({ key, label }) => {
          const value = status ? status[key] : "NOT CONNECTED";
          const reason = status?.details?.[key];
          return (
            <div className="status-row" key={key}>
              <dt>{label}</dt>
              <dd className={statusClassName(value)}>
                {value}
                {reason && <span className="status-reason">{reason}</span>}
              </dd>
            </div>
          );
        })}
      </dl>

      <PlatformPanel />

      <BrowserPanel />

      <DevConsole />
    </main>
  );
}
