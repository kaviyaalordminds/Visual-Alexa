// docs/phase-6/AVATAR-ARCHITECTURE.md — pure AgentState -> visual
// parameters. No animation/rendering logic here, only data, so it's
// trivially exhaustive-tested the same way
// veyra_contracts.avatar.compute_agent_state_from_task is on the backend.

import type { AgentState, VisemeShape } from "@veyra/contracts";

export type EyeState = "resting" | "open" | "soft" | "closed_happy" | "concerned";

export interface AgentVisual {
  auraColor: string;
  pulseSpeedMs: number;
  eyeState: EyeState;
  browTiltDeg: number;
  label: string;
}

const VISUALS: Record<AgentState, AgentVisual> = {
  IDLE: {
    auraColor: "#7c6fb0",
    pulseSpeedMs: 4200,
    eyeState: "resting",
    browTiltDeg: 0,
    label: "Idle",
  },
  LISTENING: {
    auraColor: "#8f7ff0",
    pulseSpeedMs: 1600,
    eyeState: "open",
    browTiltDeg: 2,
    label: "Listening",
  },
  UNDERSTANDING: {
    auraColor: "#8f7ff0",
    pulseSpeedMs: 1200,
    eyeState: "open",
    browTiltDeg: 2,
    label: "Understanding",
  },
  THINKING: {
    auraColor: "#6f8ff0",
    pulseSpeedMs: 1100,
    eyeState: "soft",
    browTiltDeg: 4,
    label: "Thinking",
  },
  PLANNING: {
    auraColor: "#6f8ff0",
    pulseSpeedMs: 1100,
    eyeState: "soft",
    browTiltDeg: 4,
    label: "Planning",
  },
  EXECUTING: {
    auraColor: "#6fb0f0",
    pulseSpeedMs: 900,
    eyeState: "open",
    browTiltDeg: 1,
    label: "Working",
  },
  WAITING: {
    auraColor: "#f0c56f",
    pulseSpeedMs: 1800,
    eyeState: "open",
    browTiltDeg: -3,
    label: "Waiting for you",
  },
  CONFIRMING: {
    auraColor: "#f0c56f",
    pulseSpeedMs: 1400,
    eyeState: "open",
    browTiltDeg: -4,
    label: "Needs your confirmation",
  },
  RECOVERING: {
    auraColor: "#f0a06f",
    pulseSpeedMs: 1000,
    eyeState: "concerned",
    browTiltDeg: -5,
    label: "Recovering",
  },
  SPEAKING: {
    auraColor: "#7c6fb0",
    pulseSpeedMs: 1000,
    eyeState: "open",
    browTiltDeg: 1,
    label: "Speaking",
  },
  SUCCESS: {
    auraColor: "#6fe0a0",
    pulseSpeedMs: 2200,
    eyeState: "closed_happy",
    browTiltDeg: 3,
    label: "Done",
  },
  ERROR: {
    auraColor: "#f06f6f",
    pulseSpeedMs: 900,
    eyeState: "concerned",
    browTiltDeg: -8,
    label: "Something went wrong",
  },
  PAUSED: {
    auraColor: "#9aa3b2",
    pulseSpeedMs: 3000,
    eyeState: "resting",
    browTiltDeg: 0,
    label: "Paused",
  },
};

export function agentVisual(state: AgentState): AgentVisual {
  return VISUALS[state];
}

export interface MouthShape {
  rx: number;
  ry: number;
}

// Reduced, generic mouth-shape buckets (see services/voice/voice/core/
// visemes.py's own docstring) — not any vendor's proprietary viseme set.
const MOUTH_SHAPES: Record<VisemeShape, MouthShape> = {
  REST: { rx: 13, ry: 2.5 },
  AI: { rx: 15, ry: 13 },
  E: { rx: 19, ry: 5.5 },
  FV: { rx: 14, ry: 2.5 },
  L: { rx: 11, ry: 9 },
  MBP: { rx: 12, ry: 1.2 },
  OH: { rx: 9, ry: 11 },
  U: { rx: 6.5, ry: 7.5 },
  WQ: { rx: 5.5, ry: 8.5 },
  ETC: { rx: 12, ry: 5.5 },
};

export function mouthShapeFor(shape: VisemeShape): MouthShape {
  return MOUTH_SHAPES[shape];
}
