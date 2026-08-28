import { Component, type ErrorInfo, type ReactNode } from "react";

// Phase 10 P1 (docs/phase-10/TESTING-AUDIT.md item 1): no error boundary
// existed anywhere — a single uncaught render exception in any panel
// (e.g. malformed API JSON) took the entire app to a blank white screen
// with no user-visible explanation. This is intentionally the *only*
// boundary, wrapping the whole app in main.tsx — a crash is always
// something worth surfacing plainly (Part 27: "presented meaningfully to
// the user"), not something to hide by scattering silent per-panel
// boundaries that could mask a real bug.

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[VEYRA] Unhandled error in the desktop shell:", error, info.componentStack);
  }

  private handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.error) {
      return (
        <main className="shell">
          <h1>VEYRA</h1>
          <p className="status-error" role="alert">
            Something went wrong in the VEYRA desktop shell.
          </p>
          <p className="status-reason">{this.state.error.message}</p>
          <button type="button" onClick={this.handleReload}>
            Reload
          </button>
        </main>
      );
    }
    return this.props.children;
  }
}
