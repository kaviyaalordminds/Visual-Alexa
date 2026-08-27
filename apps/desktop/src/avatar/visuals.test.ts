import { describe, expect, it } from "vitest";

import type { AgentState, VisemeShape } from "@veyra/contracts";

import { agentVisual, mouthShapeFor } from "./visuals";

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

const ALL_VISEME_SHAPES: VisemeShape[] = [
  "REST",
  "AI",
  "E",
  "FV",
  "L",
  "MBP",
  "OH",
  "U",
  "WQ",
  "ETC",
];

describe("agentVisual", () => {
  it.each(ALL_AGENT_STATES)("has a complete visual definition for %s", (state) => {
    const visual = agentVisual(state);
    expect(visual.auraColor).toMatch(/^#[0-9a-f]{6}$/i);
    expect(visual.pulseSpeedMs).toBeGreaterThan(0);
    expect(visual.label).toBeTruthy();
  });

  it("gives ERROR a visibly distinct, concerned treatment", () => {
    const error = agentVisual("ERROR");
    expect(error.eyeState).toBe("concerned");
    expect(error.browTiltDeg).toBeLessThan(0);
  });

  it("gives SUCCESS a visibly distinct, happy treatment", () => {
    const success = agentVisual("SUCCESS");
    expect(success.eyeState).toBe("closed_happy");
  });
});

describe("mouthShapeFor", () => {
  it.each(ALL_VISEME_SHAPES)("has a mouth shape for %s", (shape) => {
    const mouth = mouthShapeFor(shape);
    expect(mouth.rx).toBeGreaterThan(0);
    expect(mouth.ry).toBeGreaterThan(0);
  });

  it("REST is nearly closed while AI is wide open", () => {
    const rest = mouthShapeFor("REST");
    const ai = mouthShapeFor("AI");
    expect(ai.ry).toBeGreaterThan(rest.ry);
  });
});
