import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Avatar } from "./Avatar";
import { initialAvatarState } from "./state";

describe("Avatar", () => {
  it("renders the idle (still-connecting) state with an accessible label", () => {
    render(<Avatar runtime={initialAvatarState} />);
    // initialAvatarState.connectionState is "CONNECTING" — the very
    // first render, before the WebSocket has ever opened.
    expect(screen.getByRole("img", { name: /connecting/i })).toBeInTheDocument();
  });

  it("reflects the connected, real agent state in its label and data attribute", () => {
    render(
      <Avatar
        runtime={{ ...initialAvatarState, agentState: "LISTENING", connectionState: "CONNECTED" }}
      />,
    );
    const avatar = screen.getByRole("img", { name: /listening/i });
    expect(avatar).toHaveAttribute("data-agent-state", "LISTENING");
    expect(avatar).toHaveAttribute("data-connection-state", "CONNECTED");
  });

  it.each(["RECONNECTING", "ERROR", "DISCONNECTED"] as const)(
    "reflects a %s connection state in its label rather than pretending to be connected",
    (connectionState) => {
      render(<Avatar runtime={{ ...initialAvatarState, connectionState }} />);
      const avatar = screen.getByTestId("avatar");
      expect(avatar).toHaveAttribute("data-connection-state", connectionState);
      expect(avatar.getAttribute("aria-label")).not.toMatch(/^VEYRA$/);
    },
  );

  it("renders a SPEAKING state with an active viseme timeline without crashing", () => {
    render(
      <Avatar
        runtime={{
          agentState: "SPEAKING",
          visemes: [{ shape: "AI", start_ms: 0, duration_ms: 5000 }],
          outcome: "SUCCESS",
          speakingStartedAt: performance.now(),
          connectionState: "CONNECTED",
        }}
      />,
    );
    expect(screen.getByTestId("avatar")).toHaveAttribute("data-agent-state", "SPEAKING");
  });
});
