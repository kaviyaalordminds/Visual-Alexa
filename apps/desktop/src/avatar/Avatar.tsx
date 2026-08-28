// docs/phase-6/AVATAR-ARCHITECTURE.md — VEYRA's original visual identity.
// An abstract, stylized presence (not a photorealistic face, not any
// existing product's mark) whose every animated state is driven by a
// real `voice.ui_state.changed` event from the Local API — nothing here
// is decorative-only invention layered on top of fake state.

import { useEffect, useState } from "react";

import type { VisemeShape } from "@veyra/contracts";

import { activeVisemeAt, expressionStateFor, type AvatarRuntimeState } from "./state";
import { agentVisual, mouthShapeFor } from "./visuals";

function useElapsedSince(startedAt: number | null): number {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (startedAt === null) {
      setElapsed(0);
      return;
    }
    let frame: number;
    const tick = () => {
      setElapsed(performance.now() - startedAt);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [startedAt]);

  return elapsed;
}

function EyePair({ eyeState }: { eyeState: ReturnType<typeof agentVisual>["eyeState"] }) {
  const eyeY = 96;
  const positions = [-24, 24];

  if (eyeState === "closed_happy") {
    return (
      <>
        {positions.map((dx) => (
          <path
            key={dx}
            d={`M ${100 + dx - 9} ${eyeY} Q ${100 + dx} ${eyeY - 9} ${100 + dx + 9} ${eyeY}`}
            className="avatar-eye avatar-eye-happy"
          />
        ))}
      </>
    );
  }

  const ry = eyeState === "resting" ? 3.5 : eyeState === "concerned" ? 7 : eyeState === "soft" ? 6 : 8;
  return (
    <>
      {positions.map((dx) => (
        <ellipse
          key={dx}
          cx={100 + dx}
          cy={eyeY}
          rx={9}
          ry={ry}
          className={`avatar-eye avatar-eye-${eyeState}`}
        />
      ))}
    </>
  );
}

function Eyebrows({ browTiltDeg }: { browTiltDeg: number }) {
  const positions = [-24, 24];
  return (
    <>
      {positions.map((dx, i) => {
        const sign = i === 0 ? -1 : 1;
        return (
          <rect
            key={dx}
            x={100 + dx - 11}
            y={80}
            width={22}
            height={4}
            rx={2}
            className="avatar-brow"
            transform={`rotate(${sign * browTiltDeg}, ${100 + dx}, 82)`}
          />
        );
      })}
    </>
  );
}

function Mouth({
  visemeShape,
  smile,
}: {
  visemeShape: VisemeShape | null;
  smile: "up" | "down" | null;
}) {
  if (visemeShape === null) {
    if (smile === "up") {
      return <path d="M 84 148 Q 100 160 116 148" className="avatar-mouth-curve" />;
    }
    if (smile === "down") {
      return <path d="M 84 154 Q 100 145 116 154" className="avatar-mouth-curve" />;
    }
    return <ellipse cx={100} cy={148} rx={13} ry={2.5} className="avatar-mouth" />;
  }
  const { rx, ry } = mouthShapeFor(visemeShape);
  return <ellipse cx={100} cy={148} rx={rx} ry={ry} className="avatar-mouth" />;
}

export function Avatar({ runtime }: { runtime: AvatarRuntimeState }) {
  const elapsed = useElapsedSince(runtime.speakingStartedAt);
  const expressionState = expressionStateFor(runtime);
  const visual = agentVisual(expressionState);
  const activeViseme =
    runtime.agentState === "SPEAKING" ? activeVisemeAt(runtime.visemes, elapsed) : null;
  const visemeShape = runtime.agentState === "SPEAKING" ? (activeViseme?.shape ?? "REST") : null;
  const smile =
    visemeShape === null
      ? expressionState === "SUCCESS"
        ? "up"
        : expressionState === "ERROR"
          ? "down"
          : null
      : null;

  return (
    <div
      className="avatar"
      data-testid="avatar"
      data-agent-state={runtime.agentState}
      data-connection-state={runtime.connectionState}
      role="img"
      aria-label={
        runtime.connectionState === "CONNECTED"
          ? visual.label
          : `VEYRA (${runtime.connectionState.toLowerCase()})`
      }
      style={
        {
          "--aura-color": visual.auraColor,
          "--pulse-speed": `${visual.pulseSpeedMs}ms`,
        } as React.CSSProperties
      }
    >
      <div className="avatar-aura" />
      <svg viewBox="0 0 200 220" className="avatar-face" aria-hidden="true">
        <defs>
          <linearGradient id="avatar-hair-gradient" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#7c6fb0" />
            <stop offset="100%" stopColor="#4a3f7a" />
          </linearGradient>
        </defs>
        <path
          d="M 42 92 C 30 40 62 8 100 8 C 138 8 170 40 158 92
             C 158 132 150 160 132 176 L 132 120
             C 150 96 146 54 108 48
             C 118 70 104 92 78 92
             C 60 92 46 104 42 130 Z"
          className="avatar-hair"
        />
        <ellipse cx={100} cy={112} rx={58} ry={68} className="avatar-face-shape" />
        <EyePair eyeState={visual.eyeState} />
        <Eyebrows browTiltDeg={visual.browTiltDeg} />
        <Mouth visemeShape={visemeShape} smile={smile} />
      </svg>
    </div>
  );
}
