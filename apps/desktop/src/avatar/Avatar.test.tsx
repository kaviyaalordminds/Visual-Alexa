import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Avatar } from "./Avatar";
import { initialAvatarState } from "./state";

describe("Avatar", () => {
  it("renders the idle state with an accessible label", () => {
    render(<Avatar runtime={initialAvatarState} />);
    expect(screen.getByRole("img", { name: /not connected/i })).toBeInTheDocument();
  });

  it("reflects the connected, real agent state in its label and data attribute", () => {
    render(<Avatar runtime={{ ...initialAvatarState, agentState: "LISTENING", connected: true }} />);
    const avatar = screen.getByRole("img", { name: /listening/i });
    expect(avatar).toHaveAttribute("data-agent-state", "LISTENING");
  });

  it("renders a SPEAKING state with an active viseme timeline without crashing", () => {
    render(
      <Avatar
        runtime={{
          agentState: "SPEAKING",
          visemes: [{ shape: "AI", start_ms: 0, duration_ms: 5000 }],
          outcome: "SUCCESS",
          speakingStartedAt: performance.now(),
          connected: true,
        }}
      />,
    );
    expect(screen.getByTestId("avatar")).toHaveAttribute("data-agent-state", "SPEAKING");
  });
});
