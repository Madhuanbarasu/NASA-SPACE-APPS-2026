// LUNA-OPS 2.0 Phase 3: a validation status as the API states it. The text is always the API's own word ("Validated",
// "Pending validation", "passed", "not run", ...); the badge only picks a style for it. A word the interface does not
// recognise keeps its text and gets the neutral "unavailable" style, so no status is ever shown as better than it is.

// style tokens (class-name suffixes, never displayed)
const TONE = { pass: "pass", validated: "validated", pending: "pending", notrun: "notrun", fail: "fail", synthetic: "synthetic",
  unavailable: "unavailable" } as const;
export type StatusTone = (typeof TONE)[keyof typeof TONE];

export function statusTone(word: string): StatusTone {
  const w = word.trim().toLowerCase();
  if (w === "passed" || w === "pass") return TONE.pass;
  if (w.startsWith("validated")) return TONE.validated;
  if (w.startsWith("pending")) return TONE.pending;
  if (w === "not run" || w === "not_run") return TONE.notrun;
  if (w.startsWith("fail")) return TONE.fail;
  if (w.startsWith("synthetic")) return TONE.synthetic;
  return TONE.unavailable;
}

export function StatusBadge({ word, prefix }: { word: string; prefix?: string }) {
  return <span className={`status-badge is-${statusTone(word)}`}>{prefix && <span className="status-prefix">{prefix}</span>}{word}</span>;
}
