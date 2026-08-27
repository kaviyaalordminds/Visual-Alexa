// docs/phase-6/AVATAR-ARCHITECTURE.md — subscribes to the real, existing
// `/events` WebSocket (services/local-api/app/api/events.py, delivered
// in Phase 1) and folds every message through the pure `applyAvatarEvent`
// reducer. This is the *only* place the avatar talks to the Local API —
// CLAUDE.md: the desktop shell talks only to the Local API, never
// fabricates state client-side.

import { useEffect, useState } from "react";

import type { VeyraEvent } from "@veyra/contracts";

import { applyAvatarEvent, initialAvatarState, type AvatarRuntimeState } from "./state";

const LOCAL_API_WS_URL = "ws://127.0.0.1:8756/events";
const RECONNECT_DELAY_MS = 2000;

export function useAvatarSocket(): AvatarRuntimeState {
  const [state, setState] = useState<AvatarRuntimeState>(initialAvatarState);

  useEffect(() => {
    let cancelled = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;

    function connect() {
      if (cancelled) {
        return;
      }
      socket = new WebSocket(LOCAL_API_WS_URL);

      socket.onopen = () => {
        if (!cancelled) {
          setState((prev) => ({ ...prev, connected: true }));
        }
      };

      socket.onmessage = (message: MessageEvent<string>) => {
        if (cancelled) {
          return;
        }
        let event: VeyraEvent;
        try {
          event = JSON.parse(message.data) as VeyraEvent;
        } catch {
          return; // Malformed frame — never let it crash the avatar.
        }
        setState((prev) => applyAvatarEvent(prev, event));
      };

      const scheduleReconnect = () => {
        if (cancelled) {
          return;
        }
        setState((prev) => ({ ...prev, connected: false }));
        reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
      };
      socket.onclose = scheduleReconnect;
      socket.onerror = () => socket?.close();
    }

    connect();
    return () => {
      cancelled = true;
      clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, []);

  return state;
}
