// docs/phase-6/AVATAR-ARCHITECTURE.md — the pure event -> runtime-state
// reducer for the avatar. Kept separate from the WebSocket hook
// (useAvatarSocket.ts) specifically so it's testable without a real
// socket: every state transition here is driven by a real
// `voice.ui_state.changed` event VoiceConversationManager actually
// publishes (see services/local-api/app/services/voice/manager.py),
// never fabricated client-side.

import type { AgentState, AvatarUIStatePayload, VeyraEvent, VisemeFrame } from "@veyra/contracts";

export interface AvatarRuntimeState {
  agentState: AgentState;
  visemes: VisemeFrame[];
  outcome: AgentState | null;
  // performance.now() timestamp SPEAKING started, or null when not
  // speaking — lets the renderer compute "how far into the viseme
  // timeline are we" without storing a ticking value in state itself.
  speakingStartedAt: number | null;
  connected: boolean;
}

export const initialAvatarState: AvatarRuntimeState = {
  agentState: "IDLE",
  visemes: [],
  outcome: null,
  speakingStartedAt: null,
  connected: false,
};

function isAvatarUIStatePayload(payload: unknown): payload is AvatarUIStatePayload {
  return (
    typeof payload === "object" &&
    payload !== null &&
    "agent_state" in payload &&
    typeof (payload as { agent_state: unknown }).agent_state === "string"
  );
}

export function applyAvatarEvent(
  state: AvatarRuntimeState,
  event: VeyraEvent,
  now: number = performance.now(),
): AvatarRuntimeState {
  if (event.type !== "voice.ui_state.changed" || !isAvatarUIStatePayload(event.payload)) {
    return state;
  }
  const payload = event.payload;
  const speaking = payload.agent_state === "SPEAKING";
  return {
    ...state,
    agentState: payload.agent_state,
    visemes: speaking ? (payload.visemes ?? []) : [],
    outcome: speaking ? (payload.outcome ?? null) : null,
    speakingStartedAt: speaking ? now : null,
  };
}

// Which AgentState should drive eyes/eyebrows while SPEAKING — the real
// `outcome` the underlying task reached (e.g. concerned-while-speaking
// for an error) when the backend reported one, otherwise plain SPEAKING.
export function expressionStateFor(state: AvatarRuntimeState): AgentState {
  if (state.agentState === "SPEAKING" && state.outcome !== null) {
    return state.outcome;
  }
  return state.agentState;
}

export function activeVisemeAt(visemes: VisemeFrame[], elapsedMs: number): VisemeFrame | null {
  if (elapsedMs < 0) {
    return null;
  }
  for (const frame of visemes) {
    if (elapsedMs >= frame.start_ms && elapsedMs < frame.start_ms + frame.duration_ms) {
      return frame;
    }
  }
  return null;
}
