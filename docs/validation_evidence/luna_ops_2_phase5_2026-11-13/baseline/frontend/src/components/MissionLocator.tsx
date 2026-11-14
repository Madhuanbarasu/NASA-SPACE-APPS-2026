import { fmtLatLon } from "../lib/format";
import { S } from "../i18n";
import { ChartLegend } from "../ui/ChartLegend";

// LUNA-OPS 2.0 Phase 4: a schematic south polar locator for the mission dashboard. It plots the selected site, the
// candidate sites and the sites analysed in this session around the pole: radius proportional to the angular distance
// from the pole (azimuthal equidistant), 0 deg E at the top and 90 deg E to the right, the same orientation as the south
// polar map (checked against the map's projection: scripts/locator_orientation_check.mjs in the Phase 4 evidence). The
// extent adapts to the plotted sites and is stated on the plot. Display only: no value is computed for any site, and
// the map remains the place for positions. Candidate marks are buttons that select the site (the same action as Select).

const M = S.mission;
export interface LocatorSite { lat: number; lon: number; name: string }
interface Props {
  selected: { lat: number; lon: number } | null;
  candidates: (LocatorSite & { isSelected: boolean })[];
  analysed: LocatorSite[];
  onSelect: (index: number) => void;
}

const SIZE = 300, C = SIZE / 2, R = 112;   // room outside the outer ring for the longitude labels
// extents (degrees of colatitude from the pole) the plot can take; the smallest that holds every plotted site is used
const EXTENTS = [0.5, 1, 2, 5, 10, 20, 30];
const LIMIT = -60;   // the registered terrain and the south polar map end at 60 deg S

export function MissionLocator({ selected, candidates, analysed, onSelect }: Props) {
  const inside = (p: { lat: number }) => p.lat <= LIMIT;
  const all = [...(selected ? [selected] : []), ...candidates, ...analysed].filter(inside);
  const maxCo = all.reduce((m, p) => Math.max(m, 90 + p.lat), 0);
  const extent = EXTENTS.find((e) => maxCo <= e * 0.92) ?? 30;
  const pos = (lat: number, lon: number) => {
    const r = (R * (90 + lat)) / extent, a = (lon * Math.PI) / 180;
    return { x: C + r * Math.sin(a), y: C - r * Math.cos(a) };
  };
  const rings = [0.25, 0.5, 0.75, 1].map((f) => ({ r: R * f, lat: -90 + extent * f }));
  const outside = [...(selected && !inside(selected) ? [selected] : []), ...candidates.filter((c) => !inside(c))];
  const pct = (v: number) => `${(100 * v) / SIZE}%`;

  return (
    <div className="locator">
      {/* the plot area takes the height the card has; the square inside it is min(width, height), so the marks (placed in
          percent of the square) stay exactly over the SVG positions */}
      <div className="locator-plot">
        <div className="locator-square">
        <svg viewBox={`0 0 ${SIZE} ${SIZE}`} role="img" aria-label={M.locatorLabel(String(-90 + extent))}>
          <circle cx={C} cy={C} r={R} fill="#0c141e" stroke="#2a3a4d" />
          {rings.map((g) => (
            <g key={g.r}>
              <circle cx={C} cy={C} r={g.r} fill="none" stroke="#2a3a4d" strokeDasharray={g.r === R ? "" : "2 4"} />
              {/* ring labels on the 45 deg diagonal, clear of the longitude spokes and their labels */}
              <text x={C + g.r * Math.SQRT1_2 + 3} y={C - g.r * Math.SQRT1_2 - 3} fontSize="9.5" fill="#8b9bad">{S.format.degrees(Math.abs(g.lat).toFixed(extent < 2 ? 2 : 0))}</text>
            </g>
          ))}
          {[0, 90, 180, 270].map((a) => {
            const p = pos(-90 + extent, a);
            // labels just outside the outer ring, anchored away from the plot so none is clipped
            const lx = a === 90 ? C + R + 6 : a === 270 ? C - R - 6 : C;
            const ly = a === 0 ? C - R - 7 : a === 180 ? C + R + 15 : C + 3.5;
            return (
              <g key={a}>
                <line x1={C} y1={C} x2={p.x} y2={p.y} stroke="#2a3a4d" />
                <text x={lx} y={ly} textAnchor={a === 90 ? "start" : a === 270 ? "end" : "middle"} fontSize="10" fill="#a7b4c3">{M.locatorLon(a)}</text>
              </g>
            );
          })}
          <path d={`M${C - 5},${C} L${C + 5},${C} M${C},${C - 5} L${C},${C + 5}`} stroke="#a7b4c3" />
          {analysed.filter(inside).map((p, k) => {
            const q = pos(p.lat, p.lon);
            return <circle key={`a${k}`} cx={q.x} cy={q.y} r={3} fill="#a7b4c3"><title>{M.locatorAnalysed(p.name)}</title></circle>;
          })}
          {selected && inside(selected) && (() => {
            const q = pos(selected.lat, selected.lon);
            return <g><circle cx={q.x} cy={q.y} r={7} fill="none" stroke="#f2b544" strokeWidth={2} /><circle cx={q.x} cy={q.y} r={2.5} fill="#f2b544" /></g>;
          })()}
        </svg>
        {/* candidate marks: buttons over the plot (24 px targets), selecting the site like its Select button */}
        {candidates.map((c, k) => {
          if (!inside(c)) return null;
          const q = pos(c.lat, c.lon);
          return (
            <button key={k} type="button" className={c.isSelected ? "locator-mark is-selected" : "locator-mark"} style={{ left: pct(q.x), top: pct(q.y) }}
                    aria-label={c.isSelected ? M.locatorIsSelected(c.name) : M.locatorSelect(c.name)} title={`${c.name} (${fmtLatLon(c.lat, c.lon)})`}
                    disabled={c.isSelected} onClick={() => onSelect(k)}><span aria-hidden /></button>
          );
        })}
        </div>
      </div>
      <ChartLegend label={S.analysis.legendLabel} items={[
        { swatch: "ring", color: "var(--sun)", text: M.locatorSelected },
        { swatch: "ring", color: "var(--candidate)", text: M.locatorCandidates },
        { swatch: "dot", color: "var(--muted)", text: M.locatorAnalysedKey },
      ]} />
      {all.length === 0 && <p className="hint locator-empty">{M.locatorEmpty}</p>}
      <p className="hint">{M.locatorNote(String(-90 + extent))}</p>
      {outside.length > 0 && <p className="hint">{M.locatorOutside(outside.length)}</p>}
    </div>
  );
}
