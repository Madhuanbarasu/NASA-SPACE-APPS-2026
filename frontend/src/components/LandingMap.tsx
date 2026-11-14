import { useEffect, useRef, useState } from "react";
import OlMap from "ol/Map";
import View from "ol/View";
import Feature from "ol/Feature";
import ImageLayer from "ol/layer/Image";
import TileLayer from "ol/layer/Tile";
import VectorLayer from "ol/layer/Vector";
import ImageStatic from "ol/source/ImageStatic";
import TileImage from "ol/source/TileImage";
import VectorSource from "ol/source/Vector";
import TileGrid from "ol/tilegrid/TileGrid";
import Collection from "ol/Collection";
import { Circle, Point, Polygon } from "ol/geom";
import { fromExtent } from "ol/geom/Polygon";
import { Fill, Stroke, Style, Circle as CircleStyle } from "ol/style";
import { get as getProjection } from "ol/proj";
import { register } from "ol/proj/proj4";
import { Zoom } from "ol/control";
import Translate from "ol/interaction/Translate";
import proj4 from "proj4";
import { api } from "../api/client";
import type { LandingAssessment, LandingCandidate, LandingPoint } from "../api/types";
import { S } from "../i18n";
import { fmtLatLon } from "../lib/format";
import { Icon } from "../ui/Icon";

// LUNA-OPS 2.0 Phase 5: landing hazard map. The same projection definition as the South Polar Map (MapView): spherical
// south polar stereographic on the 1737.4 km sphere, true scale at the pole. Raster layers are PNGs the server renders on
// the DEM window's own grid (one image pixel per DEM pixel, missing data transparent) and are placed on the window's
// projected pixel-edge bounds, so they align pixel for pixel with the terrain product. The server's hillshade tiles are
// the backdrop. OpenLayers' canvas renderer is used (no WebGL context).
const SPS = "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs";
proj4.defs("LUNAOPS:SPS", SPS);
proj4.defs("LUNAOPS:GEO", "+proj=longlat +R=1737400 +no_defs");
register(proj4);
const R_MOON = 1737400;
const toXY = (lon: number, lat: number) => proj4("LUNAOPS:GEO", "LUNAOPS:SPS", [lon > 180 ? lon - 360 : lon, lat]);
const toLonLat = (x: number, y: number) => proj4("LUNAOPS:SPS", "LUNAOPS:GEO", [x, y]);
/** point scale of the projection: map distance = k x distance on the sphere */
const pointScale = (x: number, y: number) => 1 + (x * x + y * y) / (4 * R_MOON * R_MOON);

export type RasterLayer = "elevation" | "slope" | "roughness" | "coverage" | "uncertainty" | "nasa_slope" | "slope_exceed";
export interface MapLayers { raster: RasterLayer | null; depressions: boolean; footprint: boolean; window: boolean; opacity: number }

interface Props {
  assessment: LandingAssessment;
  layers: MapLayers;
  slopeThreshold: number | null;
  footprint: { lat: number; lon: number; radius_m: number };
  onMoveFootprint: (lat: number, lon: number) => void;
  selected: number | null;
  onSelect: (id: number | null) => void;
  /** increases each time the screening was re-run on the server after the overlay image failed to load */
  rev: number;
  /** the overlay image of the selected layer could not be loaded (the base map and outlines stay on screen) */
  onLayerError: () => void;
  /** a message about the selected layer shown over the map (for example: no values in the analysed window) */
  notice: string | null;
}

const reducedMotion = () => !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
const QUALITY_STYLE: Record<LandingCandidate["quality"], { color: string; dash?: number[]; width: number }> = {
  defined: { color: "rgba(238,154,107,0.95)", width: 2 },
  weak: { color: "rgba(238,154,107,0.8)", dash: [6, 4], width: 1.6 },
  within_uncertainty: { color: "rgba(163,177,191,0.7)", dash: [2, 4], width: 1.2 },
  shape_only: { color: "rgba(238,154,107,0.8)", dash: [6, 4], width: 1.6 },
};

/** the candidate's moment ellipse (full axes from the API, orientation measured from the grid's columns towards its rows,
 *  i.e. from +x towards -y in map coordinates) */
function ellipse(c: LandingCandidate): Polygon {
  const k = pointScale(c.x, c.y);
  const a = (c.axes_m[0] / 2) * k, b = (c.axes_m[1] / 2) * k;
  const th = -(c.orientation_deg * Math.PI) / 180;
  const ring: number[][] = [];
  for (let i = 0; i <= 48; i++) {
    const t = (i / 48) * 2 * Math.PI;
    const u = a * Math.cos(t), v = b * Math.sin(t);
    ring.push([c.x + u * Math.cos(th) - v * Math.sin(th), c.y + u * Math.sin(th) + v * Math.cos(th)]);
  }
  return new Polygon([ring]);
}

export function LandingMap({ assessment, layers, slopeThreshold, footprint, onMoveFootprint, selected, onSelect, rev, onLayerError, notice }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const mapRef = useRef<OlMap | null>(null);
  const rasterRef = useRef<ImageLayer<ImageStatic> | null>(null);
  const candSrc = useRef(new VectorSource());
  const fpSrc = useRef(new VectorSource());
  const winSrc = useRef(new VectorSource());
  const fpFeature = useRef(new Feature());
  const [pointer, setPointer] = useState<{ lat: number; lon: number; v: LandingPoint | null } | null>(null);
  const [tileNote, setTileNote] = useState<string | null>(null);
  const [overlayFailed, setOverlayFailed] = useState(false);
  const layerErrorRef = useRef(onLayerError);
  layerErrorRef.current = onLayerError;
  const moveRef = useRef(onMoveFootprint);
  moveRef.current = onMoveFootprint;
  const selectRef = useRef(onSelect);
  selectRef.current = onSelect;
  const idRef = useRef(assessment.id);
  idRef.current = assessment.id;
  const extent = assessment.extent_xy_m;

  // map, backdrop and interactions (once)
  useEffect(() => {
    if (!host.current) return;
    const proj = getProjection("LUNAOPS:SPS")!;
    const pad = Math.max(extent[2] - extent[0], extent[3] - extent[1]) * 0.6;
    const viewExtent = [extent[0] - pad, extent[1] - pad, extent[2] + pad, extent[3] + pad];
    const view = new View({ projection: proj, extent: viewExtent, constrainOnlyCenter: false, showFullExtent: true });
    const raster = new ImageLayer<ImageStatic>({ opacity: layers.opacity });
    rasterRef.current = raster;
    const winStyle = new Style({ stroke: new Stroke({ color: "rgba(76,201,214,0.9)", width: 1.5, lineDash: [8, 5] }) });
    const fpStyle = [new Style({ stroke: new Stroke({ color: "rgba(7,11,17,0.85)", width: 4 }) }),
      new Style({ stroke: new Stroke({ color: "rgba(242,181,68,1)", width: 2 }), fill: new Fill({ color: "rgba(242,181,68,0.08)" }) }),
      new Style({ image: new CircleStyle({ radius: 3, fill: new Fill({ color: "rgba(242,181,68,1)" }) }),
        geometry: (f) => new Point((f.getGeometry() as Circle).getCenter()) })];
    const map = new OlMap({
      target: host.current,
      layers: [raster,
        new VectorLayer({ source: winSrc.current, style: winStyle }),
        new VectorLayer({ source: candSrc.current }),
        new VectorLayer({ source: fpSrc.current, style: fpStyle })],
      view, controls: [new Zoom({ zoomInLabel: "+", zoomOutLabel: "−", zoomInTipLabel: S.landing.map.zoomIn, zoomOutTipLabel: S.landing.map.zoomOut })],
    });
    mapRef.current = map;
    view.fit(extent, { padding: [16, 16, 16, 16] });
    fpSrc.current.addFeature(fpFeature.current);
    const translate = new Translate({ features: new Collection([fpFeature.current]) });
    translate.on("translateend", () => {
      const g = fpFeature.current.getGeometry() as Circle | undefined;
      if (!g) return;
      const [cx, cy] = g.getCenter();
      const [lo, la] = toLonLat(cx, cy);
      moveRef.current(la, ((lo % 360) + 360) % 360);
    });
    map.addInteraction(translate);
    map.on("singleclick", (e) => {
      let hit: number | null = null;
      map.forEachFeatureAtPixel(e.pixel, (f) => { const id = f.get("cid"); if (id != null) { hit = id; return true; } return false; },
        { hitTolerance: 4, layerFilter: (l) => l.getSource() === candSrc.current });
      selectRef.current(hit);
    });
    // pointer readout: one request per pause in pointer movement (values read from the server's arrays, never computed here)
    let timer = 0, seq = 0;
    map.on("pointermove", (e) => {
      if (e.dragging) return;
      const [lo, la] = toLonLat(e.coordinate[0], e.coordinate[1]);
      const lat = la, lon = ((lo % 360) + 360) % 360;
      setPointer({ lat, lon, v: null });
      window.clearTimeout(timer);
      const my = ++seq;
      timer = window.setTimeout(() => {
        api.landingPoint(idRef.current, lat, lon).then((v) => { if (my === seq) setPointer({ lat, lon, v }); }).catch(() => undefined);
      }, 160);
    });
    const onLeave = () => { window.clearTimeout(timer); seq++; setPointer(null); };
    map.getViewport()?.addEventListener("pointerleave", onLeave);
    // hillshade backdrop from the server's tile service (fine zoom levels only near the window)
    let disposed = false;
    api.tilesMeta().then((meta) => {
      if (disposed || !meta.available) { setTileNote(S.landing.map.noBackdrop); return; }
      const grid = new TileGrid({ origin: meta.origin, resolutions: meta.resolutions, tileSize: meta.tile_size, extent: meta.extent });
      const src = new TileImage({ projection: proj, tileGrid: grid, transition: 0,
        tileUrlFunction: (c) => (c ? `/api/display/tiles/${c[0]}/${c[1]}/${c[2]}.png` : undefined) });
      // only fine tiles are requested: coarse tiles that contain the 5 m product render slowly on the server (MapView notes)
      map.getLayers().insertAt(0, new TileLayer({ source: src, maxResolution: 300, opacity: 0.9 }));
    }).catch(() => setTileNote(S.landing.map.noBackdrop));
    return () => {
      disposed = true; window.clearTimeout(timer);
      map.getViewport()?.removeEventListener("pointerleave", onLeave);
      map.setTarget(undefined); mapRef.current = null;
    };
    // the map is rebuilt for each assessment (LandingView keys it by assessment id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // raster overlay
  useEffect(() => {
    const L = rasterRef.current;
    if (!L) return;
    setOverlayFailed(false);
    if (!layers.raster || (layers.raster === "slope_exceed" && slopeThreshold == null)) { L.setSource(null); return; }
    const src = new ImageStatic({
      url: api.landingLayerUrl(assessment.id, layers.raster, layers.raster === "slope_exceed" ? slopeThreshold : null, rev),
      imageExtent: extent, projection: "LUNAOPS:SPS", interpolate: false,
    });
    // A failed overlay image (for example a screening the server no longer holds) is removed, so no image of another
    // layer stays under this layer's legend; the backdrop, outlines and footprint stay, and LandingView is told.
    let live = true;
    src.on("imageloaderror", () => {
      if (!live) return;
      L.setSource(null);
      setOverlayFailed(true);
      layerErrorRef.current();
    });
    L.setSource(src);
    return () => { live = false; };
  }, [assessment.id, layers.raster, slopeThreshold, extent, rev]);
  useEffect(() => { rasterRef.current?.setOpacity(layers.opacity); }, [layers.opacity]);

  // analysis window outline
  useEffect(() => {
    winSrc.current.clear();
    if (layers.window) winSrc.current.addFeature(new Feature(fromExtent(extent)));
  }, [layers.window, extent]);

  // depression candidates (unconfirmed): moment ellipses styled by quality class
  useEffect(() => {
    candSrc.current.clear();
    if (!layers.depressions) return;
    for (const c of assessment.candidates) {
      const q = QUALITY_STYLE[c.quality];
      const sel = c.id === selected;
      const f = new Feature(ellipse(c));
      f.set("cid", c.id);
      f.setStyle([
        ...(sel ? [new Style({ stroke: new Stroke({ color: "rgba(255,255,255,0.95)", width: q.width + 3 }) })] : []),
        new Style({ stroke: new Stroke({ color: q.color, width: q.width, lineDash: q.dash }), fill: new Fill({ color: "rgba(0,0,0,0.001)" }) }),
      ]);
      candSrc.current.addFeature(f);
    }
  }, [assessment.candidates, layers.depressions, selected]);

  // footprint circle (radius on the sphere x point scale = map radius)
  useEffect(() => {
    const [x, y] = toXY(footprint.lon, footprint.lat);
    fpFeature.current.setGeometry(new Circle([x, y], footprint.radius_m * pointScale(x, y)));
    fpSrc.current.changed();
    const show = layers.footprint;
    mapRef.current?.getLayers().forEach((l) => { if ((l as VectorLayer<VectorSource>).getSource?.() === fpSrc.current) l.setVisible(show); });
  }, [footprint.lat, footprint.lon, footprint.radius_m, layers.footprint]);

  // centre on a selected candidate
  useEffect(() => {
    const c = assessment.candidates.find((x) => x.id === selected);
    const v = mapRef.current?.getView();
    if (!c || !v) return;
    v.animate({ center: [c.x, c.y], duration: reducedMotion() ? 0 : 250 });
  }, [selected, assessment.candidates]);

  const reset = () => mapRef.current?.getView().fit(extent, { padding: [16, 16, 16, 16], duration: reducedMotion() ? 0 : 250 });
  const toFootprint = () => {
    const [x, y] = toXY(footprint.lon, footprint.lat);
    mapRef.current?.getView().animate({ center: [x, y], duration: reducedMotion() ? 0 : 250 });
  };
  const P = S.landing.point;
  const v = pointer?.v;
  return (
    <>
      <div className="pane-body map-stage landing-map">
        <div className="map-host" ref={host} aria-label={S.landing.map.label} role="region" tabIndex={0} />
        <div className="view-controls map-tools" role="group" aria-label={S.landing.map.tools}>
          <button type="button" aria-label={S.landing.map.reset} title={S.landing.map.reset} onClick={reset}><Icon name="fit" /></button>
          <button type="button" aria-label={S.landing.map.toFootprint} title={S.landing.map.toFootprint} onClick={toFootprint}><Icon name="target" /></button>
        </div>
        {(overlayFailed || notice) && (
          <p className="landing-map-status" role="status">{overlayFailed ? S.landing.layerFailed : notice}</p>
        )}
        <div className="stage-readout map-readout landing-readout" aria-hidden>
          {pointer ? (
            <>
              <span>{S.globe.pointer(fmtLatLon(pointer.lat, pointer.lon))}</span>
              {v && !v.inside && <span>{P.outside}</span>}
              {v && v.inside && v.missing && <span className="bad">{P.missing}</span>}
              {v && v.inside && !v.missing && (
                <span className="mono">
                  {P.values(fmt(v.elevation_m, 1), fmt(v.slope_deg, 1), fmt(v.roughness_m, 2))}
                  {v.height_sigma_m != null && <>{" "}{P.sigma(fmt(v.height_sigma_m, 2))}</>}
                  {v.lola_returns != null && <>{" "}{P.returns(String(v.lola_returns))}</>}
                  {v.depression_id != null && <>{" "}{P.depression(v.depression_id, fmt(v.depression_depth_m, 2))}</>}
                </span>
              )}
            </>
          ) : <span>{S.landing.map.hint}</span>}
        </div>
      </div>
      {tileNote && <div className="pane-note">{tileNote}</div>}
    </>
  );
}

const fmt = (v: number | null | undefined, d: number) => (v == null || !isFinite(v) ? S.common.na : v.toFixed(d));
