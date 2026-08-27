import { useEffect, useState } from "react";

import type { BrowserSessionInfo } from "@veyra/contracts";

import { closeBrowserSession, invokeTool, listBrowserSessions } from "../api";

// docs/phase-8/BROWSER-ARCHITECTURE.md — a diagnostic panel in the same
// spirit as PlatformPanel.tsx, not "the final UI" for this surface.
// Every action here goes through the real HTTP API (BrowserManager via
// the Tool Registry / Policy Engine), never a shortcut.
export default function BrowserPanel() {
  const [sessions, setSessions] = useState<BrowserSessionInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      setSessions(await listBrowserSessions());
    } catch {
      // Local API unreachable — leave the last-known list in place, App
      // already surfaces the top-level connectivity error.
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="platform-panel">
      <h2>VEYRA Browser</h2>
      <p className="dev-console-hint">
        Live browser sessions and tabs — every action below goes through the real
        BrowserManager / Policy Engine, nothing here bypasses it.
      </p>

      {error && <p className="status-error">{error}</p>}

      <button disabled={busy} onClick={() => run(() => invokeTool("browser.launch", {}))}>
        Launch Browser
      </button>

      <ul className="platform-list">
        {sessions.length === 0 && <li className="platform-list-item">No active sessions.</li>}
        {sessions.map((session) => (
          <li key={session.session_id} className="platform-list-item">
            <span>
              {session.browser_type} — <em>{session.connection_status}</em> (
              {session.tabs.length} tab{session.tabs.length === 1 ? "" : "s"})
            </span>
            <button disabled={busy} onClick={() => run(() => closeBrowserSession(session.session_id))}>
              Close
            </button>
            <ul className="platform-list">
              {session.tabs.map((tab) => (
                <li key={tab.tab_id} className="platform-list-item">
                  <span>
                    {tab.active ? "▶ " : ""}
                    {tab.title || tab.url} — <em>{tab.status}</em>
                  </span>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </section>
  );
}
