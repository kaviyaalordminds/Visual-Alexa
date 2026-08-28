import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ErrorBoundary } from "./ErrorBoundary";

function Boom(): never {
  throw new Error("simulated render crash");
}

describe("ErrorBoundary", () => {
  it("renders children normally when nothing throws", () => {
    render(
      <ErrorBoundary>
        <p>hello</p>
      </ErrorBoundary>,
    );
    expect(screen.getByText("hello")).toBeInTheDocument();
  });

  it("catches a render error instead of leaving the app blank", () => {
    // React logs the error to the console by default in test/dev; silence
    // it for this deliberately-throwing test so it doesn't look like a
    // real test failure in the output.
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      render(
        <ErrorBoundary>
          <Boom />
        </ErrorBoundary>,
      );
      expect(screen.getByRole("alert")).toHaveTextContent(/something went wrong/i);
      expect(screen.getByText("simulated render crash")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /reload/i })).toBeInTheDocument();
    } finally {
      consoleError.mockRestore();
    }
  });
});
