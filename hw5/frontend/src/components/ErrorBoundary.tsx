import { Component, type ReactNode } from "react";

interface State { error: Error | null }

/** Keeps one broken panel from blanking the whole dashboard. */
export class ErrorBoundary extends Component<{ label: string; children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <section className="panel" role="alert">
          <p><strong>The {this.props.label} panel hit an error.</strong></p>
          <p className="muted small">{this.state.error.message}</p>
          <button className="btn btn-ghost btn-sm" style={{ marginTop: 10 }} onClick={() => this.setState({ error: null })}>
            Try again
          </button>
        </section>
      );
    }
    return this.props.children;
  }
}
