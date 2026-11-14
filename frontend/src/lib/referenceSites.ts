// Sourced reference mission sites (frontend/src/data/reference_sites.json). Every entry carries its source; coordinates
// are copied from the source unchanged (east longitude 0-360). Entries outside 60-90 S are reference only: LUNA-OPS has
// no terrain there, so they can be shown but never analysed (the coverage check refuses them as well).
import data from "../data/reference_sites.json";

export type RefCategory = "landed" | "crashed" | "target";
export interface RefSource { title: string; url: string }
export interface RefSite {
  id: string; name: string; operator: string; country: string; category: RefCategory; status: string;
  lat: number; lon: number; elevation_m?: number; accuracy_m?: number; source: string; analysis: "eligible" | "reference_only";
}

export const REF_SITES: RefSite[] = (data.sites as RefSite[]).slice().sort((a, b) =>
  a.analysis === b.analysis ? a.name.localeCompare(b.name) : a.analysis === "eligible" ? -1 : 1);
export const REF_SOURCES: Record<string, RefSource> = data.sources;
export const REF_VERSION: string = data.version;
export const refSource = (s: RefSite): RefSource | undefined => REF_SOURCES[s.source];

/** case-insensitive match on name, operator, country and status */
export function searchRefSites(q: string): RefSite[] {
  const t = q.trim().toLowerCase();
  if (!t) return REF_SITES;
  return REF_SITES.filter((s) => `${s.name} ${s.operator} ${s.country} ${s.status}`.toLowerCase().includes(t));
}
