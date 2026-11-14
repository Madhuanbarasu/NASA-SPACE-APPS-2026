import { Component, type ReactNode } from "react";

/** Shows `fallback` instead of crashing the page when a lazily loaded pane (its JavaScript chunk) fails to load or render. */
export class LazyBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}
