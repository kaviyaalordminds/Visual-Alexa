// Mirrors packages/contracts/python/veyra_contracts/events.py's Event
// model — the exact JSON shape broadcast over the real `/events`
// WebSocket (services/local-api/app/api/events.py).

import type { AgentState, EventType, VisemeShape } from "./enums";

export interface VisemeFrame {
  shape: VisemeShape;
  start_ms: number;
  duration_ms: number;
}

// docs/phase-6/AVATAR-ARCHITECTURE.md — the payload shape for
// `voice.ui_state.changed`. `visemes`/`outcome` are only ever present
// alongside `agent_state: "SPEAKING"` (see VoiceConversationManager).
export interface AvatarUIStatePayload {
  agent_state: AgentState;
  visemes?: VisemeFrame[];
  outcome?: AgentState;
}

export interface VeyraEvent {
  id: string;
  type: EventType;
  payload: Record<string, unknown>;
  correlation_id: string;
  timestamp: string;
}
