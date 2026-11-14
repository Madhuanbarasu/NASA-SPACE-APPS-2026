import { useEffect, useRef, useState } from "react";
import OlMap from "ol/Map";
import View from "ol/View";
import Feature from "ol/Feature";
import TileLayer from "ol/layer/Tile";
import VectorLayer from "ol/layer/Vector";
import TileImage from "ol/source/TileImage";
import TileState from "ol/TileState";
import type ImageTile from "ol/ImageTile";
import VectorSource from "ol/source/Vector";
import TileGrid from "ol/tilegrid/TileGrid";
import { LineString, Point, Polygon } from "ol/geom";
import { Circle as CircleStyle, Fill, Stroke, Style, Text } from "ol/style";
import { get as getProjection } from "ol/proj";
import { register } from "ol/proj/proj4";
import { Zoom } from "ol/control";
import proj4 from "proj4";
import { api } from "../api/client";
import type { CatalogSite } from "../api/types";
import { S } from "../i18n";
import { fmtLatLon } from "../lib/format";
import { greatCircleM, niceScale } from "../lib/mapScale";
import { siteCoords } from "../lib/moonGeo";
import { Icon } from "../ui/Icon";
import { StageLegend, type LegendItem } from "../ui/StageLegend";

const SPS = "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs";
proj4.defs("LUNAOPS:SPS", SPS);
proj4.defs("LUNAOPS:GEO", "+proj=longlat +R=1737400 +no_defs");
register(proj4);
const toXY = (lon: number, lat: number) => proj4("LUNAOPS:GEO", "LUNAOPS:SPS", [lon > 180 ? lon - 360 : lon, lat]);
const toLonLat = (x: number, y: number) => proj4("LUNAOPS:SPS", "LUNAOPS:GEO", [x, y]);

// Hillshade tiles are rendered by the server on request (backend api/tiles.py). A zoomed-out tile that contains terrain far
// finer than its scale (here the 5 m Site01 product inside tiles of zooms 1-4) is not rendered in minutes: the server reads
// the fine product over the whole tile (docs/validation_evidence/south_polar_map_fixes_2026-11-12). The backend is not
// changed (its code is covered by the code fingerprint that binds every validation result). Instead:
//  * a coarse tile (>= COMPOSE_MIN_RES m/pixel) that has not arrived after PATIENCE_MS is drawn from its four child tiles
//    one zoom finer (recursively), i.e. the server's own hillshade of the same LOLA heights, downscaled 2:1 per level;
//    nothing is stretched, interpolated or invented, and children the server cannot provide stay transparent;
//  * the slow tile's request is cancelled so it stops holding one of the browser's few connections, and the tile is
//    remembered (per backend build and terrain products) so later visits compose it at once without asking the server
//    again (each request starts another long server render);
//  * any other tile is given up after TILE_TIMEOUT_MS and reported. Normal tiles take up to about 7 s.
const TILE_TIMEOUT_MS = 20000;
const PATIENCE_MS = 10000;
const COMPOSE_MIN_RES = 400;
const SLOW_KEY = "luna-ops.map.slow-tiles.v1";
function readSlow(sig: string): { slow: Set<string>; stalled: Set<string> } {
  try {
    const v = JSON.parse(window.localStorage.getItem(SLOW_KEY) || "null");
    if (v && v.sig === sig) return { slow: new Set(v.slow ?? []), stalled: new Set(v.stalled ?? []) };
  } catch { /* storage unavailable */ }
  return { slow: new Set(), stalled: new Set() };
}
function writeSlow(sig: string, slow: Set<string>, stalled: Set<string>) {
  try { window.localStorage.setItem(SLOW_KEY, JSON.stringify({ sig, slow: [...slow], stalled: [...stalled] })); } catch { /* storage unavailable */ }
}
const TILE_PX = 256;

interface Props {
  lat: number | null; lon: number | null; catalog: CatalogSite[]; selectedId: string | null;
  onPick: (lat: number, lon: number) => void;
  /** LUNA-OPS 2.0 Phase 2 (explorer stage): pointer and scale readout, navigation buttons, tile status, legend, the 60 S
   *  edge drawn clearly and comparison candidates. Off in the analysis result, whose map is redesigned in Phase 3. */
  instruments?: boolean;
  candidates?: { lat: number; lon: number; name: string }[];
  /** whether the legend starts open on wide screens (Phase 3: closed in the smaller analysis map) */
  legendOpen?: boolean;
}

const LIMIT_LAT = -60;
const FIT_FALLBACK = [-9e5, -9e5, 9e5, 9e5];
const reducedMotion = () => !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

function graticule(): Feature[] {
  const out: Feature[] = [];
  for (const lat of [-89, -88, -87, -86, -85, -84, -82, -80, -75, -70, -65, LIMIT_LAT]) {
    const ring: number[][] = [];
    for (let lon = 0; lon <= 360; lon += 2) ring.push(toXY(lon, lat));
    const f = new Feature(new LineString(ring));
    f.set("label", S.map.latitudeLine(lat));
    if (lat === LIMIT_LAT) f.set("limit", true);
    out.push(f);
  }
  for (let lon = 0; lon < 360; lon += 30) {
    const f = new Feature(new LineString([toXY(lon, -89.999), toXY(lon, -60)]));
    f.set("label", S.map.longitudeLine(lon));
    out.push(f);
  }
  return out;
}

export function MapView({ lat, lon, catalog, selectedId, onPick, instruments = false, candidates = [], legendOpen = true }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const mapRef = useRef<OlMap | null>(null);
  const siteSrc = useRef(new VectorSource());
  const catSrc = useRef(new VectorSource());
  const candSrc = useRef(new VectorSource());
  const extentRef = useRef<number[]>(FIT_FALLBACK);
  const [note, setNote] = useState<string>(S.map.loadingTiles);
  const [tiles, setTiles] = useState({ pending: 0, composed: 0, stalled: 0, failed: 0 });
  const [outside, setOutside] = useState(false);
  const [pointer, setPointer] = useState<{ lat: number; lon: number; inside: boolean } | null>(null);
  const [scale, setScale] = useState<{ px: number; label: string } | null>(null);
  const pickRef = useRef(onPick);
  pickRef.current = onPick;
  const instrumentsRef = useRef(instruments);

  useEffect(() => {
    if (!host.current) return;
    const withInstruments = instrumentsRef.current;
    const proj = getProjection("LUNAOPS:SPS")!;
    const view = new View({ projection: proj, center: [0, 0], resolution: 2000 });
    const plainGrid = new Style({ stroke: new Stroke({ color: "rgba(163,177,191,0.28)", width: 1 }) });
    // Phase 2: on the explorer stage the 60 S circle (the edge of the map and of the registered terrain) is drawn clearly
    const limitLine = new Style({ stroke: new Stroke({ color: "rgba(127,200,169,0.9)", width: 1.6 }) });
    const grat = new VectorLayer({
      source: new VectorSource({ features: graticule() }),
      style: withInstruments ? (f) => (f.get("limit") ? limitLine : plainGrid) : plainGrid,
    });
    const cat = new VectorLayer({
      source: catSrc.current,
      style: (f) => f.getGeometry() instanceof Polygon
        ? new Style({ stroke: new Stroke({ color: "rgba(231,236,241,0.55)", width: 1, lineDash: [4, 4] }) })
        : new Style({
            image: new CircleStyle({ radius: 4, fill: new Fill({ color: "#e7ecf1" }), stroke: new Stroke({ color: "#17212c", width: 2 }) }),
            text: new Text({ text: f.get("name"), offsetY: -12, font: "12px 'Archivo Variable', sans-serif",
                             fill: new Fill({ color: "#e7ecf1" }), stroke: new Stroke({ color: "#17212c", width: 3 }) }),
          }),
    });
    const site = new VectorLayer({
      source: siteSrc.current,
      // U-04 (1.4.11): a dark halo keeps the gold ring visible on bright hillshade
      style: [new Style({ image: new CircleStyle({ radius: 8, stroke: new Stroke({ color: "#17212c", width: 6 }) }) }),
              new Style({ image: new CircleStyle({ radius: 8, stroke: new Stroke({ color: "#f2b544", width: 2.5 }),
                                                   fill: new Fill({ color: "rgba(242,181,68,0.25)" }) }) })],
    });
    // comparison candidates (Phase 2): an accent ring with a dark halo, smaller than the selected site's gold ring
    const cand = new VectorLayer({
      source: candSrc.current,
      style: [new Style({ image: new CircleStyle({ radius: 6, stroke: new Stroke({ color: "#17212c", width: 5 }) }) }),
              new Style({ image: new CircleStyle({ radius: 6, stroke: new Stroke({ color: "#4cc9d6", width: 2 }) }) })],
    });
    // U-04 (2.5.7): zoom buttons give a single-pointer alternative to wheel and drag (double-click zooms to a point)
    const map = new OlMap({ target: host.current, layers: [grat, cat, cand, site], view,
      controls: [new Zoom({ zoomInTipLabel: S.map.zoomIn, zoomOutTipLabel: S.map.zoomOut })] });
    host.current.querySelector(".ol-zoom-in")?.setAttribute("aria-label", S.map.zoomIn);
    host.current.querySelector(".ol-zoom-out")?.setAttribute("aria-label", S.map.zoomOut);
    mapRef.current = map;
    map.on("singleclick", (e) => {
      const [lo, la] = toLonLat(e.coordinate[0], e.coordinate[1]);
      // the shared conversion (lib/moonGeo); north of 60 S is outside the map, which is now said instead of ignored silently
      if (la <= -60) { const c = siteCoords(la, lo); setOutside(false); pickRef.current(c.lat, c.lon); } else setOutside(true);
    });
    // Phase 2 instruments: pointer position (the same inverse projection as a click) and a scale bar measured on the
    // 1737.4 km reference sphere at the view centre (lib/mapScale; checked against the projection's exact point scale)
    let ptrRaf = 0;
    const onLeave = () => { cancelAnimationFrame(ptrRaf); setPointer(null); };
    const updateScale = () => {
      const v = map.getView(), c = v.getCenter(), r = v.getResolution();
      if (!c || r == null) return;
      const a = toLonLat(c[0] - 50 * r, c[1]), b = toLonLat(c[0] + 50 * r, c[1]);
      const s = niceScale(greatCircleM(a[1], a[0], b[1], b[0]) / 100);
      setScale(s ? { px: Math.round(s.px), label: S.map.scale(s.metres >= 1000 ? S.map.km(String(s.metres / 1000)) : S.map.m(String(s.metres))) } : null);
    };
    if (withInstruments) {
      map.on("pointermove", (e) => {
        if (e.dragging) return;
        const [x, y] = e.coordinate;
        cancelAnimationFrame(ptrRaf);
        ptrRaf = requestAnimationFrame(() => { const [lo, la] = toLonLat(x, y); setPointer({ lat: la, lon: lo, inside: la <= LIMIT_LAT }); });
      });
      map.getViewport()?.addEventListener("pointerleave", onLeave);
      map.on("moveend", updateScale);
    }
    let disposed = false;
    const inflight = new Set<AbortController>();
    Promise.all([api.tilesMeta(), api.status().catch(() => null)]).then(([meta, status]) => {
      if (!meta.available) { setNote(S.map.noTerrain); view.fit(FIT_FALLBACK); return; }
      proj.setExtent(meta.extent);
      extentRef.current = meta.extent;
      // the view stays on the map's data square: no panning or zooming out into empty space beyond it (the only dark
      // areas left are the square's corners beyond 60 S, where no registered terrain exists)
      const bounded = new View({ projection: proj, extent: meta.extent, constrainOnlyCenter: false, showFullExtent: false,
                                 center: [0, 0], resolution: view.getResolution() ?? 2000 });
      map.setView(bounded);
      // U-06: never request zoom level 0. The server's zoom-0 tile reads every registered DEM over the whole polar window
      // and did not return within 120 s (docs/validation_evidence/u06_2026-11-11), so the welcome map stayed blank; zoom-1
      // tiles take about 0.5 s and OpenLayers draws the zoomed-out view from them. Display only; no data changes.
      const grid = new TileGrid({ origin: meta.origin, resolutions: meta.resolutions, tileSize: meta.tile_size, extent: meta.extent,
                                  minZoom: Math.min(1, meta.resolutions.length - 1) });
      const sig = JSON.stringify([status?.code_fingerprint ?? null, meta.extent, meta.resolutions, meta.levels.map((l: any) => l.product)]);
      const { slow, stalled } = readSlow(sig);
      const failedTiles = new Set<string>(), composedTiles = new Set<string>();
      const res: number[] = meta.resolutions;
      const remember = () => writeSlow(sig, slow, stalled);

      // one tile as a PNG blob: from the server, or composed from the four tiles one zoom finer (see above)
      const getTile = (z: number, x: number, y: number): Promise<Blob | null> => {
        const key = `${z}/${x}/${y}`;
        const composable = res[z] >= COMPOSE_MIN_RES && z + 1 < res.length;
        if (composable && slow.has(key)) { composedTiles.add(key); return compose(z, x, y); }
        if (stalled.has(key)) return Promise.resolve(null);
        return new Promise((resolve) => {
          let settled = false, composing = false;
          const finish = (b: Blob | null) => { if (!settled) { settled = true; resolve(b); } };
          const ctrl = new AbortController();
          inflight.add(ctrl);
          const hard = window.setTimeout(() => ctrl.abort(), TILE_TIMEOUT_MS);
          const soft = composable ? window.setTimeout(() => {
            if (settled || disposed) return;
            composing = true; ctrl.abort();
            slow.add(key); composedTiles.add(key); remember();
            compose(z, x, y).then(finish);
          }, PATIENCE_MS) : 0;
          fetch(`/api/tiles/${key}.png`, { signal: ctrl.signal })
            .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.blob(); })
            .then((b) => finish(b))
            .catch(() => {
              if (disposed) return finish(null);
              if (composing) return;                       // the composed tile resolves instead
              if (ctrl.signal.aborted) { stalled.add(key); remember(); } else failedTiles.add(key);
              finish(null);
            })
            .finally(() => { window.clearTimeout(hard); window.clearTimeout(soft); inflight.delete(ctrl); });
        });
      };
      const compose = async (z: number, x: number, y: number): Promise<Blob | null> => {
        const kids = await Promise.all([0, 1].flatMap((j) => [0, 1].map((i) =>
          getTile(z + 1, 2 * x + i, 2 * y + j).then((b) => ({ i, j, b })))));
        if (disposed || !kids.some((k) => k.b)) return null;
        const canvas = document.createElement("canvas");
        canvas.width = canvas.height = TILE_PX;
        const g = canvas.getContext("2d")!;
        g.imageSmoothingEnabled = true; g.imageSmoothingQuality = "high";
        const half = TILE_PX / 2;
        for (const k of kids) {
          if (!k.b) continue;
          const bmp = await createImageBitmap(k.b);
          g.drawImage(bmp, k.i * half, k.j * half, half, half);   // 2:1 downscale of the server's own tile
          bmp.close();
        }
        return new Promise((r) => canvas.toBlob((b) => r(b), "image/png"));
      };

      const src = new TileImage({ projection: proj, tileGrid: grid,
        tileUrlFunction: (c) => `/api/tiles/${c[0]}/${c[1]}/${c[2]}.png`,
        tileLoadFunction: (tile) => {
          const [z, x, y] = tile.getTileCoord();
          getTile(z, x, y).then((blob) => {
            if (disposed) return;
            if (!blob) { tile.setState(TileState.ERROR); return; }
            const img = (tile as ImageTile).getImage() as HTMLImageElement;
            const obj = URL.createObjectURL(blob);
            img.addEventListener("load", () => URL.revokeObjectURL(obj), { once: true });
            img.addEventListener("error", () => URL.revokeObjectURL(obj), { once: true });
            img.src = obj;
          });
        } });
      src.on("tileloadstart", () => { if (!disposed) setTiles((s) => ({ ...s, pending: s.pending + 1 })); });
      const done = () => { if (!disposed) setTiles((s) => ({ ...s, pending: Math.max(0, s.pending - 1) })); };
      // count only the composed, stalled or failed tiles that cover the current view at the current zoom
      const recount = () => {
        const v = map.getView(), size = map.getSize(), r = v.getResolution();
        if (disposed || !size || r == null) return;
        let cp = 0, st = 0, fl = 0;
        grid.forEachTileCoord(v.calculateExtent(size), grid.getZForResolution(r), (c) => {
          const k = c.join("/");
          if (composedTiles.has(k)) cp++; else if (stalled.has(k)) st++; else if (failedTiles.has(k)) fl++;
        });
        setTiles((s) => (s.composed === cp && s.stalled === st && s.failed === fl ? s : { ...s, composed: cp, stalled: st, failed: fl }));
      };
      src.on("tileloadend", () => { done(); recount(); });
      src.on("tileloaderror", () => { done(); recount(); });
      map.on("moveend", recount);
      if (withInstruments) map.on("moveend", updateScale);   // the bounded view replaced the first one
      map.getLayers().insertAt(0, new TileLayer({ source: src }));
      bounded.fit(meta.extent);
      const c = siteSrc.current.getFeatures()[0]?.getGeometry() as Point | undefined;
      if (c) { bounded.setCenter(c.getCoordinates()); bounded.setResolution(90); }
      setNote(meta.levels.some((l: any) => l.synthetic) ? S.map.syntheticTerrain : meta.note);
    }).catch(() => setNote(S.map.tilesUnavailable));
    return () => {
      disposed = true; inflight.forEach((c) => c.abort()); cancelAnimationFrame(ptrRaf);
      map.getViewport()?.removeEventListener("pointerleave", onLeave);
      map.setTarget(undefined); mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    candSrc.current.clear();
    for (const c of candidates) {
      if (!(c.lat <= LIMIT_LAT) || (lat === c.lat && lon === c.lon)) continue;
      candSrc.current.addFeature(new Feature(new Point(toXY(c.lon, c.lat))));
    }
  }, [candidates, lat, lon]);

  useEffect(() => {
    catSrc.current.clear();
    for (const c of catalog) {
      const pt = new Feature(new Point(toXY(c.lon, c.lat)));
      pt.set("name", c.name);
      catSrc.current.addFeature(pt);
      if (c.polygon_latlon) {
        catSrc.current.addFeature(new Feature(new Polygon([c.polygon_latlon.map(([la, lo]) => toXY(lo, la))])));
      }
    }
  }, [catalog, selectedId]);

  useEffect(() => {
    siteSrc.current.clear();
    if (lat == null || lon == null || !isFinite(lat) || !isFinite(lon) || lat > -60) return;
    const xy = toXY(lon, lat);
    siteSrc.current.addFeature(new Feature(new Point(xy)));
    const v = mapRef.current?.getView();
    if (v) v.animate({ center: xy, resolution: Math.min(v.getResolution() ?? 90, 90), duration: 300 });
  }, [lat, lon]);

  const siteOnMap = lat != null && lon != null && isFinite(lat) && isFinite(lon) && lat <= LIMIT_LAT;
  const resetView = () => mapRef.current?.getView().fit(extentRef.current, { duration: reducedMotion() ? 0 : 300 });
  const centreOnSite = () => {
    const v = mapRef.current?.getView();
    if (!v || !siteOnMap) return;
    v.animate({ center: toXY(lon as number, lat as number), resolution: Math.min(v.getResolution() ?? 90, 90), duration: reducedMotion() ? 0 : 300 });
  };
  const legend: LegendItem[] = [
    { swatch: "dot", color: "var(--terrain-edge)", text: S.map.legendHillshade },
    { swatch: "line", color: "var(--valid)", text: S.map.legendLimit },
    { swatch: "hatch", text: S.map.legendHatched },
    { swatch: "ring", color: "var(--sun)", text: S.map.legendSelected },
    ...(catalog.length ? [{ swatch: "dot", color: "var(--text)", text: S.map.legendCatalogue } as LegendItem] : []),
    ...(candidates.length ? [{ swatch: "ring", color: "var(--candidate)", text: S.stage.candidates } as LegendItem] : []),
  ];
  const readout = pointer ? (pointer.inside ? S.globe.pointer(fmtLatLon(pointer.lat, pointer.lon)) : S.map.pointerOutside)
    : siteOnMap ? S.globe.selectedReadout(fmtLatLon(lat as number, lon as number)) : null;

  return (
    <>
      <div className={instruments ? "pane-body map-stage" : "pane-body"}>
        <div className="map-host" ref={host} aria-label={S.map.label} role="region" tabIndex={0} />
        {instruments && (
          <>
            <div className="view-controls map-tools" role="group" aria-label={S.map.tools}>
              <button type="button" aria-label={S.map.resetView} title={S.map.resetView} onClick={resetView}><Icon name="fit" /></button>
              <button type="button" aria-label={S.map.centreOnSite} title={S.map.centreOnSite} onClick={centreOnSite}
                      disabled={!siteOnMap}><Icon name="target" /></button>
            </div>
            {/* compact tile status; the full explanation stays in the note under the map (read by screen readers there) */}
            {(tiles.pending > 0 || tiles.composed > 0 || tiles.stalled > 0 || tiles.failed > 0) && (
              <div className="map-status" aria-hidden>
                {tiles.pending > 0 && <span className="status-chip is-busy">{S.map.statusLoading(tiles.pending)}</span>}
                {tiles.composed > 0 && <span className="status-chip">{S.map.statusComposed(tiles.composed)}</span>}
                {tiles.stalled > 0 && <span className="status-chip is-warn">{S.map.statusStalled(tiles.stalled)}</span>}
                {tiles.failed > 0 && <span className="status-chip is-bad">{S.map.statusFailed(tiles.failed)}</span>}
              </div>
            )}
            <div className="stage-readout map-readout" aria-hidden>
              {readout && <span>{readout}</span>}
              {scale && <span className="scale-bar"><span className="scale-line" style={{ width: scale.px }} />{scale.label}</span>}
            </div>
            <StageLegend items={legend} className="map-legend" defaultOpen={legendOpen} />
          </>
        )}
      </div>
      <div className="pane-note">{S.map.note(note)}
        {outside && <>{" "}{S.map.outsideMap}</>}
        {tiles.pending > 0 && <>{" "}{S.map.tilesLoading(tiles.pending)}</>}
        {tiles.composed > 0 && <>{" "}{S.map.tilesComposed(tiles.composed)}</>}
        {tiles.stalled > 0 && <>{" "}{S.map.tilesStalled(tiles.stalled)}</>}
        {tiles.failed > 0 && <>{" "}{S.map.tilesFailed(tiles.failed)}</>}</div>
    </>
  );
}
