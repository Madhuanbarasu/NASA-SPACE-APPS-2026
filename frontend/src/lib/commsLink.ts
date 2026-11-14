import type { CommsLinkForm } from "../api/types";

// The Communication tab's link-budget form -> the /api/comms request body (shared with the Compare summary, so both use
// exactly the same user-entered values; nothing is assumed: an empty field stays null).
const num = (v: string | undefined): number | null => (v == null || v.trim() === "" || !isFinite(Number(v)) ? null : Number(v));
const scaled = (v: string | undefined, k: number) => { const n = num(v); return n == null ? null : n * k; };

export function linkBody(f: CommsLinkForm) {
  const p = num(f.power);
  return { pt_w: f.powerUnit === "dbw" ? null : p, pt_dbw: f.powerUnit === "dbw" ? p : null, gt_dbi: num(f.gt), ltx_db: num(f.ltx),
    gr_dbi: num(f.gr), lrx_db: num(f.lrx), lother_db: num(f.lother), ts_k: num(f.ts), freq_hz: scaled(f.freqMHz, 1e6),
    bandwidth_hz: scaled(f.bwkHz, 1e3), rb_bps: scaled(f.rbkbps, 1e3), ebn0_req_db: num(f.ebn0),
    basis: f.basis === "specification" ? "specification" : "illustrative", reference: f.reference?.trim() || null };
}
/** whether any link field was filled in (basis and power unit are choices, not values) */
export const hasAny = (f: CommsLinkForm) => Object.entries(f).some(([k, v]) => k !== "basis" && k !== "powerUnit" && !!v && v.trim() !== "");
