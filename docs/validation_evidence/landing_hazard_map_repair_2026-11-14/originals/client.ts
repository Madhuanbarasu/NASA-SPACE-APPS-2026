import { S } from "../i18n";
import type { CatalogSite, CommsResult, Comparison, Coverage, Job, LandingAssessment, LandingFootprint, LandingPoint, Result, Status, TerrainGrid } from "./types";

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, { headers: { "Content-Type": "application/json" }, ...init });
  if (!r.ok) {
    let detail = r.statusText;
    try { const j = await r.json(); detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* keep */ }
    throw new Error(detail);
  }
  return r.json() as Promise<T>;
}

export const api = {
  status: () => req<Status>("/api/status"),
  catalog: () => req<{ sites: CatalogSite[]; sources: any[]; empty_reason: string | null }>("/api/catalog"),
  coverage: (lat: number, lon: number) => req<Coverage>(`/api/coverage?lat=${lat}&lon=${lon}`),
  analysis: (body: unknown) => req<{ result_id: string | null; job_id: string | null }>("/api/analysis",
    { method: "POST", body: JSON.stringify(body) }),
  compare: (body: unknown) => req<{ job_id: string }>("/api/compare", { method: "POST", body: JSON.stringify(body) }),
  job: (id: string) => req<Job>(`/api/jobs/${id}`),
  result: (id: string) => req<Result>(`/api/results/${id}`),
  comparison: (id: string) => req<Comparison>(`/api/compare/${id}`),
  terrain: (lat: number, lon: number, radiusKm: number) =>
    req<TerrainGrid>(`/api/terrain?lat=${lat}&lon=${lon}&radius_km=${radiusKm}&n=160`),
  tilesMeta: () => req<any>("/api/tiles/meta"),
  validation: () => req<any>("/api/validation"),
  // Phase 5: preliminary landing screening (backend/lunaops_landing)
  landingAssess: (body: unknown) => req<LandingAssessment>("/api/landing/assess", { method: "POST", body: JSON.stringify(body) }),
  landingFootprint: (id: string, body: unknown) =>
    req<LandingFootprint>(`/api/landing/${id}/footprint`, { method: "POST", body: JSON.stringify(body) }),
  landingPoint: (id: string, lat: number, lon: number) => req<LandingPoint>(`/api/landing/${id}/point?lat=${lat}&lon=${lon}`),
  // Phase 6: preliminary communication simulation (backend/lunaops_comms)
  commsSimulate: (body: unknown) => req<CommsResult>("/api/comms/simulate", { method: "POST", body: JSON.stringify(body) }),
  landingLayerUrl: (id: string, name: string, threshold?: number | null) =>
    `/api/landing/${id}/layer/${name}.png${threshold != null ? `?threshold=${threshold}` : ""}`,
};

export async function waitForJob(id: string, onProgress: (j: Job) => void, signal?: AbortSignal): Promise<Job> {
  for (;;) {
    if (signal?.aborted) throw new Error(S.errors.cancelled);
    const j = await api.job(id);
    onProgress(j);
    if (j.status === "done" || j.status === "error") return j;
    await new Promise((r) => setTimeout(r, 600));
  }
}
