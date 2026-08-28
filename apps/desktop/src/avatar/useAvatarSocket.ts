// docs/phase-6/AVATAR-ARCHITECTURE.md — subscribes to the real, existing
// `/events` WebSocket (services/local-api/app/api/events.py, delivered
// in Phase 1) and folds every message through the pure `applyAvatarEvent`
// reducer. This is the *only* place the avatar talks to the Local API —
// CLAUDE.md: the desktop shell talks only to the Local API, never
// fabricates state client-side.
//
// Phase 9 audit P1-4: reconnect used to retry on a fixed 2s interval
// forever, with no way to tell a temporarily-busy backend apart from a
// genuinely dead one, and no way to notice a connection that had gone
// silently dead without a clean close event. This now backs off
// exponentially (bounded, reset on a successful reconnect) and treats a
// stretch with no message at all — not even the backend's own heartbeat
// frame, see events.py — as a dead connection to force-close and retry.

import { useEffect, useState } from "react";

import type { VeyraEvent } from "@veyra/contracts";

import { applyAvatarEvent, initialAvatarState, type AvatarRuntimeState } from "./state";

const LOCAL_API_WS_URL = "ws://127.0.0.1:8756/events";

// Backend sends a heartbeat every 20s (events.py's HEARTBEAT_INTERVAL_SECONDS)
// when nothing else is happening; missing several in a row means the
// connection is dead even though the browser hasn't noticed yet.
const STALE_CONNECTION_TIMEOUT_MS = 45000;

const RECONNECT_BASE_DELAY_MS = 1000;
const RECONNECT_MAX_DELAY_MS = 30000;

function backoffDelay(attempt: number): number {
  const exponential = RECONNECT_BASE_DELAY_MS * 2 ** attempt;
  const jitter = Math.random() * 300;
  return Math.min(exponential, RECONNECT_MAX_DELAY_MS) + jitter;
}

export function useAvatarSocket(): AvatarRuntimeState {
  const [state, setState] = useState<AvatarRuntimeState>(initialAvatarState);

  useEffect(() => {
    let cancelled = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let staleTimer: ReturnType<typeof setTimeout> | undefined;
    let reconnectAttempt = 0;

    function clearStaleTimer() {
      if (staleTimer !== undefined) {
        clearTimeout(staleTimer);
        staleTimer = undefined;
      }
    }

    function armStaleTimer() {
      clearStaleTimer();
      staleTimer = setTimeout(() => {
        // No message — not even a heartbeat — in too long. Treat this
        // exactly like a detected disconnect rather than waiting for the
        // browser to eventually notice on its own.
        socket?.close();
      }, STALE_CONNECTION_TIMEOUT_MS);
    }

    function connect() {
      if (cancelled) {
        return;
      }
      socket = new WebSocket(LOCAL_API_WS_URL);

      socket.onopen = () => {
        if (cancelled) {
          return;
        }
        reconnectAttempt = 0;
        armStaleTimer();
        setState((prev) => ({ ...prev, connected: true }));
      };

      socket.onmessage = (message: MessageEvent<string>) => {
        if (cancelled) {
          return;
        }
        armStaleTimer();
        let event: VeyraEvent;
        try {
          event = JSON.parse(message.data) as VeyraEvent;
        } catch {
          return; // Malformed frame — never let it crash the avatar.
        }
        if ((event as { type?: string }).type === "heartbeat") {
          return; // Liveness-only frame — armStaleTimer() above already handled it.
        }
        setState((prev) => applyAvatarEvent(prev, event));
      };

      const scheduleReconnect = () => {
        clearStaleTimer();
        if (cancelled) {
          return;
        }
        setState((prev) => ({ ...prev, connected: false }));
        const delay = backoffDelay(reconnectAttempt);
        reconnectAttempt += 1;
        reconnectTimer = setTimeout(connect, delay);
      };
      socket.onclose = scheduleReconnect;
      socket.onerror = () => socket?.close();
    }

    connect();
    return () => {
      cancelled = true;
      clearTimeout(reconnectTimer);
      clearStaleTimer();
      socket?.close();
    };
  }, []);

  return state;
}
