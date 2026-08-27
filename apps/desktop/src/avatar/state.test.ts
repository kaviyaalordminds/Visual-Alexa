import { describe, expect, it } from "vitest";

import type { AgentState, VeyraEvent } from "@veyra/contracts";

import {
  activeVisemeAt,
  applyAvatarEvent,
  expressionStateFor,
  initialAvatarState,
} from "./state";

const ALL_AGENT_STATES: AgentState[] = [
  "IDLE",
  "LISTENING",
  "UNDERSTANDING",
  "THINKING",
  "PLANNING",
  "EXECUTING",
  "WAITING",
  "CONFIRMING",
  "RECOVERING",
  "SPEAKING",
  "SUCCESS",
  "ERROR",
  "PAUSED",
];

function uiEvent(agentState: AgentState, extra: Record<string, unknown> = {}): VeyraEvent {
  return {
    id: "evt-1",
    type: "voice.ui_state.changed",
    correlation_id: "session-1",
    timestamp: new Date().toISOString(),
    payload: { agent_state: agentState, ...extra },
  };
}

describe("applyAvatarEvent", () => {
  it("ignores events that are not voice.ui_state.changed", () => {
    const other: VeyraEvent = {
      id: "evt-2",
      type: "voice.response.started",
      correlation_id: "session-1",
      timestamp: new Date().toISOString(),
      payload: { text: "hello" },
    };
    expect(applyAvatarEvent(initialAvatarState, other)).toBe(initialAvatarState);
  });

  it("ignores a malformed payload without agent_state", () => {
    const malformed: VeyraEvent = {
      id: "evt-3",
      type: "voice.ui_state.changed",
      correlation_id: "session-1",
      timestamp: new Date().toISOString(),
      payload: {},
    };
    expect(applyAvatarEvent(initialAvatarState, malformed)).toBe(initialAvatarState);
  });

  it.each(ALL_AGENT_STATES)("updates agentState for %s", (state) => {
    const result = applyAvatarEvent(initialAvatarState, uiEvent(state));
    expect(result.agentState).toBe(state);
  });

  it("attaches visemes and outcome only for SPEAKING", () => {
    const visemes = [{ shape: "AI", start_ms: 0, duration_ms: 90 }];
    const result = applyAvatarEvent(
      initialAvatarState,
      uiEvent("SPEAKING", { visemes, outcome: "SUCCESS" }),
      1000,
    );
    expect(result.visemes).toEqual(visemes);
    expect(result.outcome).toBe("SUCCESS");
    expect(result.speakingStartedAt).toBe(1000);
  });

  it("clears visemes/outcome/speakingStartedAt when leaving SPEAKING", () => {
    const speaking = applyAvatarEvent(
      initialAvatarState,
      uiEvent("SPEAKING", { visemes: [{ shape: "AI", start_ms: 0, duration_ms: 90 }] }),
      1000,
    );
    const idle = applyAvatarEvent(speaking, uiEvent("IDLE"), 2000);
    expect(idle.visemes).toEqual([]);
    expect(idle.outcome).toBeNull();
    expect(idle.speakingStartedAt).toBeNull();
  });

  it("defaults to no visemes/outcome when SPEAKING payload omits them", () => {
    const result = applyAvatarEvent(initialAvatarState, uiEvent("SPEAKING"), 500);
    expect(result.visemes).toEqual([]);
    expect(result.outcome).toBeNull();
    expect(result.speakingStartedAt).toBe(500);
  });
});

describe("expressionStateFor", () => {
  it("returns the outcome while SPEAKING with a real outcome", () => {
    const state = applyAvatarEvent(initialAvatarState, uiEvent("SPEAKING", { outcome: "ERROR" }));
    expect(expressionStateFor(state)).toBe("ERROR");
  });

  it("returns SPEAKING when there is no outcome", () => {
    const state = applyAvatarEvent(initialAvatarState, uiEvent("SPEAKING"));
    expect(expressionStateFor(state)).toBe("SPEAKING");
  });

  it("returns the plain agentState when not speaking", () => {
    const state = applyAvatarEvent(initialAvatarState, uiEvent("LISTENING"));
    expect(expressionStateFor(state)).toBe("LISTENING");
  });
});

describe("activeVisemeAt", () => {
  const visemes = [
    { shape: "AI" as const, start_ms: 0, duration_ms: 100 },
    { shape: "REST" as const, start_ms: 100, duration_ms: 50 },
    { shape: "OH" as const, start_ms: 150, duration_ms: 100 },
  ];

  it("returns the frame covering the given elapsed time", () => {
    expect(activeVisemeAt(visemes, 0)?.shape).toBe("AI");
    expect(activeVisemeAt(visemes, 99)?.shape).toBe("AI");
    expect(activeVisemeAt(visemes, 100)?.shape).toBe("REST");
    expect(activeVisemeAt(visemes, 200)?.shape).toBe("OH");
  });

  it("returns null before the timeline starts or after it ends", () => {
    expect(activeVisemeAt(visemes, -1)).toBeNull();
    expect(activeVisemeAt(visemes, 250)).toBeNull();
  });

  it("returns null for an empty timeline", () => {
    expect(activeVisemeAt([], 0)).toBeNull();
  });
});
