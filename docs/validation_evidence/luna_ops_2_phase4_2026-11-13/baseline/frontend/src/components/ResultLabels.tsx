import type { Result } from "../api/types";
import { S } from "../i18n";

// The result's validation chips and the ids of the analysis sections, shared by the analysis workspace (loaded on
// demand) and the mission dashboard, kept small so neither pulls the whole workspace into the first load.

const T = S.site;
const QUANTITY_NAMES: Record<string, string> = S.quantities;
// prefixes of the API's validation status words (protocol values, not display text)
const VALIDATED_PREFIX = "Validated";
const SYNTHETIC_PREFIX = "Synthetic";

/** Phase 5 prompt 4: ids of the result-view sections the mission dashboard links to (internal tokens). */
export const RESULT_SECTIONS = { summary: "result-summary", panorama: "result-panorama", timeline: "result-timeline",
  visibility: "result-visibility", earth: "result-earth", terrain: "result-terrain", validation: "result-validation",
  tables: "result-tables" } as const;

export function LabelChips({ result }: { result: Result }) {
  return (
    <div className="label-row" aria-label={T.labelsLabel}>
      {Object.entries(result.labels).map(([k, v]) => {
        const cls = v.validation.startsWith(VALIDATED_PREFIX) ? "validated" : v.validation.startsWith(SYNTHETIC_PREFIX) ? "synthetic" : "pending";
        return <span key={k} className={`chip ${cls}`} title={[...(v.reasons ?? []).map((r) => T.labelNotValidated(r)), ...Object.entries(v.tests).map(([t, s]) => T.labelTest(t, s))].join("\n")}>
          {T.labelChip(QUANTITY_NAMES[k] ?? k, v.kind, v.validation.toLowerCase())}</span>;
      })}
    </div>
  );
}
