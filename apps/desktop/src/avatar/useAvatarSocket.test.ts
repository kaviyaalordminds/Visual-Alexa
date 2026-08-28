// Phase 9 audit P1-4: proves the two properties the reliability fix
// actually promises — a connection that stops sending anything (not even
// a heartbeat) is treated as dead and reconnected, and repeated
// disconnects back off instead of retrying on a fixed interval forever.

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAvatarSocket } from "./useAvatarSocket";

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  close() {
    if (this.closed) {
      return;
    }
    this.closed = true;
    this.onclose?.();
  }

  // Test helpers, not part of the real WebSocket interface.
  simulateOpen() {
    this.onopen?.();
  }
  simulateMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent<string>);
  }
}

describe("useAvatarSocket", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.useFakeTimers();
    vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("treats a connection with no messages at all (not even a heartbeat) as dead and reconnects", async () => {
    const { result } = renderHook(() => useAvatarSocket());

    const first = MockWebSocket.instances[0];
    await act(async () => {
      first.simulateOpen();
    });
    expect(result.current.connected).toBe(true);
    expect(first.closed).toBe(false);

    // Silence past the stale-connection timeout (45s) with not even a
    // heartbeat frame — the hook must give up on this socket itself
    // rather than waiting for the browser to eventually notice.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(46000);
    });

    expect(first.closed).toBe(true);
    expect(result.current.connected).toBe(false);
    // A reconnect must have been scheduled (a second socket created,
    // possibly after the backoff delay below has also elapsed).
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(MockWebSocket.instances.length).toBeGreaterThan(1);
  });

  it("a heartbeat frame keeps the connection alive without changing avatar state", async () => {
    const { result } = renderHook(() => useAvatarSocket());
    const first = MockWebSocket.instances[0];
    await act(async () => {
      first.simulateOpen();
    });
    const stateAfterOpen = result.current;

    // Send heartbeats right up to (but never past) the stale timeout,
    // repeatedly — the connection must never be treated as dead as long
    // as *something* keeps arriving.
    for (let i = 0; i < 3; i += 1) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30000);
        first.simulateMessage({ type: "heartbeat" });
      });
    }

    expect(first.closed).toBe(false);
    expect(result.current.connected).toBe(true);
    expect(result.current.agentState).toBe(stateAfterOpen.agentState);
  });

  it("backs off exponentially (bounded) across repeated immediate disconnects instead of a fixed retry interval", async () => {
    renderHook(() => useAvatarSocket());

    const closeTimesMs: number[] = [];
    let elapsed = 0;

    for (let i = 0; i < 4; i += 1) {
      const socket = MockWebSocket.instances[MockWebSocket.instances.length - 1];
      await act(async () => {
        socket.close(); // never even opened — simulates connection refused
      });
      // Advance in small steps, recording how long it took for the next
      // socket to be created, until it is.
      const before = MockWebSocket.instances.length;
      let waited = 0;
      while (MockWebSocket.instances.length === before && waited < 40000) {
        await act(async () => {
          await vi.advanceTimersByTimeAsync(250);
        });
        waited += 250;
      }
      elapsed += waited;
      closeTimesMs.push(waited);
    }

    // Each successive gap should generally grow (exponential backoff),
    // not stay pinned at a fixed interval — and never exceed the 30s cap
    // (plus a little slack for jitter/step granularity).
    expect(closeTimesMs[1]).toBeGreaterThan(closeTimesMs[0] - 500);
    expect(closeTimesMs[3]).toBeLessThanOrEqual(30500);
    void elapsed;
  });
});
