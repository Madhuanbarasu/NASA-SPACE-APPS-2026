import type { ReactNode } from "react";

// LUNA-OPS 2.0 Phase 3: one telemetry value (label, value, optional note) inside a <dl className="metrics">. The value
// is always text the caller formatted from the API (with its unit); `state` only styles it: "unknown" for a missing
// value, "flag" for a count of uncertain or near-field items that deserves attention when it is not zero.

interface MetricProps {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  state?: "unknown" | "flag";
}

export function Metric({ label, value, note, state }: MetricProps) {
  return (
    <div className={state ? `metric is-${state}` : "metric"}>
      <dt>{label}</dt>
      <dd>{value}{note != null && note !== "" && <span className="metric-note">{note}</span>}</dd>
    </div>
  );
}
