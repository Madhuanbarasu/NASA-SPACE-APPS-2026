import { useCallback, useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { S } from "../i18n";
import { fmtLatLon } from "../lib/format";
import { latLonToUnit, raySphere, unitToLatLon, type GlobeLocation } from "../lib/moonGeo";

export type { GlobeLocation } from "../lib/moonGeo";

// Phase 5: interactive 3D Moon globe. Display only: the imagery (NASA SVS CGI Moon Kit, see ATTRIBUTION.md and
// public/moon/ATTRIBUTION.txt) is never turned into elevation, illumination or any other scientific value. The globe
// frame and the latitude/longitude convention live in lib/moonGeo.ts and are tested against three.js by
// scripts/check-moon-geo.mjs. Loaded on demand (React.lazy), so three.js stays out of the initial bundle.

export interface MoonGlobeProps {
  /** Location to mark (controlled). When omitted the globe keeps its own selection. */
  selected?: GlobeLocation | null;
  /** Called with the picked location: latitude degrees +north, longitude degrees east in [0, 360). */
  onSelect?: (location: GlobeLocation) => void;
  /** Terrain coverage of `selected` from the coverage API: colours the marker (true covered, false not, null unknown). */
  selectedCovered?: boolean | null;
  /** Show the globe's own "Selected location" panel and announcement (default). Off when the host shows the selection. */
  selectionPanel?: boolean;
  /** Where the camera starts (centred, at the selection distance) when the globe opens; the default viewpoint otherwise. */
  startAt?: GlobeLocation | null;
}

const G = S.globe;
const COLOR_URL = "/moon/lroc_color_2k.jpg";
const RELIEF_URL = "/moon/ldem_3_8bit.jpg";
const DEFAULT_DIST = 3.4;
const MIN_DIST = 1.32;
const MAX_DIST = 9;
const STEP_DEG = 10;
const MAX_LAT = 89.9;              // keeps the orbit off the exact pole (OrbitControls singularity)
const SELECTION_DIST = 2.2;        // camera distance when centring on a selected site
const FOLLOW_MS = 450;             // a selection typed elsewhere is followed once it has been stable this long
const PICK_SLOP_PX = 6;
const POLE_HIDE_LAT = 50;          // view latitude beyond which that pole's label and axis stub are hidden
const AMBIENT = 0.2, KEY = 3.0;    // illustrative oblique light; "even light" values below
const AMBIENT_EVEN = 2.1, KEY_EVEN = 0.35;
type Viewpoint = "nearside" | "farside" | "north" | "south";
const VIEWPOINTS: Record<Viewpoint, GlobeLocation> = {
  nearside: { lat: 0, lon: 0 }, farside: { lat: 0, lon: 180 }, north: { lat: MAX_LAT, lon: 0 }, south: { lat: -MAX_LAT, lon: 0 } };
const COLORS = { marker: 0xf2b544, covered: 0x7fc8a9, uncovered: 0xee9a6b, grid: 0x8fb3d1, gridMain: 0xffd98a, axis: 0xcfd8e0,
  limit: 0x7fc8a9, poleInk: "#ffd98a" };
// backend dem.coverage_check refuses every point north of 60 S; the globe draws that limit (coverage south of it is still
// checked point by point by the coverage API)
const TERRAIN_LIMIT_LAT = -60;
const FLY_MS = 650;
// internal state tokens (never displayed)
const PHASE = { loading: "loading", ready: "ready", imageryError: "imageryError", noWebGL: "noWebGL", contextLost: "contextLost" } as const;
type Phase = (typeof PHASE)[keyof typeof PHASE];

const fmt = (v: number, d = 3) => v.toFixed(d);
const formatLocation = (loc: GlobeLocation) => fmtLatLon(loc.lat, loc.lon);

/** The 60 S line: northern limit of the registered terrain. */
function terrainLimit(): THREE.Line {
  const pts: THREE.Vector3[] = [];
  for (let k = 0; k <= 360; k += 1) { const u = latLonToUnit(TERRAIN_LIMIT_LAT, k); pts.push(new THREE.Vector3(u[0], u[1], u[2]).multiplyScalar(1.0025)); }
  return new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
    new THREE.LineBasicMaterial({ color: COLORS.limit, transparent: true, opacity: 0.9, depthWrite: false }));
}

/** Deterministic star field (decorative backdrop, not a star catalogue). */
function starField(count: number): THREE.Points {
  let seed = 0x9e3779b9;
  const rnd = () => { seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  const pos = new Float32Array(count * 3), col = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    const z = 2 * rnd() - 1, a = 2 * Math.PI * rnd(), r = Math.sqrt(1 - z * z), R = 70 + 20 * rnd();
    pos.set([R * r * Math.cos(a), R * z, R * r * Math.sin(a)], 3 * i);
    const b = 0.35 + 0.65 * rnd() ** 3, warm = rnd() < 0.2 ? 0.9 : 1;
    col.set([b, b * warm, b * (warm < 1 ? 0.8 : 1)], 3 * i);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  g.setAttribute("color", new THREE.BufferAttribute(col, 3));
  return new THREE.Points(g, new THREE.PointsMaterial({ size: 1.6, sizeAttenuation: false, vertexColors: true, transparent: true, opacity: 0.9, depthWrite: false }));
}

/** Latitude/longitude lines every 30 degrees; the equator and the prime meridian are highlighted. */
function graticule(): THREE.Group {
  const minor: number[] = [], major: number[] = [];
  const r = 1.0015, seg = 180;
  const push = (arr: number[], a: number[], b: number[]) => arr.push(a[0] * r, a[1] * r, a[2] * r, b[0] * r, b[1] * r, b[2] * r);
  for (let lat = -60; lat <= 60; lat += 30) {
    for (let k = 0; k < seg; k++) push(lat === 0 ? major : minor, latLonToUnit(lat, (k * 360) / seg), latLonToUnit(lat, ((k + 1) * 360) / seg));
  }
  for (let lon = 0; lon < 360; lon += 30) {
    for (let k = 0; k < seg / 2; k++) push(lon === 0 ? major : minor, latLonToUnit(-90 + (k * 180) / (seg / 2), lon), latLonToUnit(-90 + ((k + 1) * 180) / (seg / 2), lon));
  }
  const mk = (arr: number[], color: number, opacity: number) => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(arr, 3));
    return new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color, transparent: true, opacity, depthWrite: false }));
  };
  const group = new THREE.Group();
  group.add(mk(minor, COLORS.grid, 0.28), mk(major, COLORS.gridMain, 0.5));
  return group;
}

/** Text sprite for the pole labels (text from the dictionary). */
function labelSprite(text: string): THREE.Sprite {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const ctx = c.getContext("2d");
  if (ctx) {
    const family = getComputedStyle(document.documentElement).getPropertyValue("--font").trim() || "sans-serif";
    ctx.font = `700 88px ${family}`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.lineWidth = 10;
    ctx.strokeStyle = "rgba(8, 12, 18, 0.85)";
    ctx.strokeText(text, 64, 68);
    ctx.fillStyle = COLORS.poleInk;
    ctx.fillText(text, 64, 68);
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: true, transparent: true }));
  s.scale.set(0.16, 0.16, 1);
  return s;
}

/** Selected-location marker: a ring on the surface and a short pin along the local vertical. */
function marker(): THREE.Group {
  const g = new THREE.Group();
  // depth-tested, so a marker on the far side is hidden by the globe instead of showing through it
  const ring = new THREE.Mesh(new THREE.RingGeometry(0.018, 0.028, 40),
    new THREE.MeshBasicMaterial({ color: COLORS.marker, side: THREE.DoubleSide, transparent: true, opacity: 0.95,
      polygonOffset: true, polygonOffsetFactor: -4 }));
  const pinGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 0, 0.12)]);
  const pin = new THREE.Line(pinGeo, new THREE.LineBasicMaterial({ color: COLORS.marker }));
  const tip = new THREE.Mesh(new THREE.SphereGeometry(0.009, 12, 8), new THREE.MeshBasicMaterial({ color: COLORS.marker }));
  tip.position.set(0, 0, 0.12);
  g.add(ring, pin, tip);
  g.renderOrder = 10;
  g.visible = false;
  return g;
}

function disposeTree(root: THREE.Object3D) {
  root.traverse((o) => {
    const m = o as THREE.Mesh;
    if (m.geometry) m.geometry.dispose();
    const mats = m.material ? (Array.isArray(m.material) ? m.material : [m.material]) : [];
    for (const mat of mats) {
      for (const v of Object.values(mat)) if (v instanceof THREE.Texture) v.dispose();
      mat.dispose();
    }
  });
}

interface Ctx {
  renderer: THREE.WebGLRenderer; scene: THREE.Scene; camera: THREE.PerspectiveCamera; controls: OrbitControls;
  moon: THREE.Mesh; grid: THREE.Group; marker: THREE.Group; key: THREE.DirectionalLight; ambient: THREE.AmbientLight;
  render: () => void;
  /** refresh readout, pole marks and frame after a programmatic view change (OrbitControls skips moves below its EPS) */
  sync: () => void;
}

export function MoonGlobe({ selected, onSelect, selectedCovered = null, selectionPanel = true, startAt = null }: MoonGlobeProps) {
  const host = useRef<HTMLDivElement>(null);
  const startRef = useRef(startAt);   // read once, when the scene is built
  const ctx = useRef<Ctx | null>(null);
  const [phase, setPhase] = useState<Phase>(PHASE.loading);
  const [own, setOwn] = useState<GlobeLocation | null>(selected ?? null);
  const [hover, setHover] = useState<GlobeLocation | null>(null);
  const [centre, setCentre] = useState<GlobeLocation>(VIEWPOINTS.nearside);
  const [grid, setGrid] = useState(true);
  const [even, setEven] = useState(false);
  const pick = selected === undefined ? own : selected;
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  // announced only for picks made on the globe itself (not for selections that arrive through `selected`, e.g. typing)
  const [announced, setAnnounced] = useState<GlobeLocation | null>(null);
  const choose = useCallback((loc: GlobeLocation) => {
    setOwn(loc);
    setAnnounced(loc);
    onSelectRef.current?.(loc);
  }, []);

  // scene set-up and teardown
  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setPhase(PHASE.noWebGL);
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    el.appendChild(renderer.domElement);
    renderer.domElement.setAttribute("aria-hidden", "true");

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(35, 1, 0.01, 200);
    scene.add(camera);
    const ambient = new THREE.AmbientLight(0xffffff, AMBIENT);
    // illustrative oblique light carried with the viewpoint (upper left), so relief reads on whatever face is shown;
    // it is not the Sun direction of any date
    const key = new THREE.DirectionalLight(0xfff3e2, KEY);
    key.position.set(-2.8, 1.3, 0.75);
    camera.add(key);
    scene.add(ambient, starField(2400));

    const moonMat = new THREE.MeshStandardMaterial({ color: 0x9a9a9a, roughness: 1, metalness: 0 });
    const moon = new THREE.Mesh(new THREE.SphereGeometry(1, 256, 128), moonMat);
    scene.add(moon);
    const gridGroup = graticule();
    scene.add(gridGroup, terrainLimit());
    // pole axis stubs and labels: north is +y in the globe frame. Each pole's label and stub hide when the view looks down
    // on that pole, so they never cover the polar surface itself.
    const stub = (y0: number, y1: number) => new THREE.LineSegments(
      new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, y0, 0), new THREE.Vector3(0, y1, 0)]),
      new THREE.LineBasicMaterial({ color: COLORS.axis, transparent: true, opacity: 0.8 }));
    const northAxis = stub(1.0, 1.22), southAxis = stub(-1.0, -1.22);
    const north = labelSprite(G.northMark), south = labelSprite(G.southMark);
    north.position.set(0, 1.32, 0);
    south.position.set(0, -1.32, 0);
    scene.add(northAxis, southAxis, north, south);
    const poleMarks = (viewLat: number) => {
      north.visible = northAxis.visible = viewLat < POLE_HIDE_LAT;
      south.visible = southAxis.visible = viewLat > -POLE_HIDE_LAT;
    };
    const mk = marker();
    scene.add(mk);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enablePan = false;
    controls.enableDamping = false;
    controls.minDistance = MIN_DIST;
    controls.maxDistance = MAX_DIST;
    controls.zoomSpeed = 0.8;
    // opens centred on the selected site when there is one (Show on the globe, the 3D Moon view), else on the nearside
    const s0 = startRef.current;
    const startDist = s0 ? SELECTION_DIST : DEFAULT_DIST;
    const start = s0 ? latLonToUnit(Math.max(-MAX_LAT, Math.min(MAX_LAT, s0.lat)), s0.lon) : latLonToUnit(VIEWPOINTS.nearside.lat, VIEWPOINTS.nearside.lon);
    camera.position.set(start[0] * startDist, start[1] * startDist, start[2] * startDist);
    camera.up.set(0, 1, 0);
    controls.target.set(0, 0, 0);
    controls.update();

    let raf = 0, disposed = false;
    const render = () => {           // on demand; never after teardown (forceContextLoss)
      if (raf || disposed) return;
      raf = requestAnimationFrame(() => { raf = 0; if (!disposed) renderer.render(scene, camera); });
    };
    const onChange = () => {
      const d = camera.position.length();
      controls.rotateSpeed = Math.max(0.08, 0.5 * (d - 1) / (DEFAULT_DIST - 1));   // slower turning when close
      const c = unitToLatLon(camera.position.x, camera.position.y, camera.position.z);
      poleMarks(c.lat);
      setCentre(c);
      render();
    };
    controls.addEventListener("change", onChange);
    onChange();   // centre readout and pole marks for the starting view
    const onStart = () => cancelAnimationFrame(flyRaf.current);   // a drag or wheel takes over from a flight
    controls.addEventListener("start", onStart);

    // picking: a press and release within a few pixels selects; a drag rotates
    const ray = new THREE.Raycaster();
    const ndc = new THREE.Vector2();
    const locate = (cx: number, cy: number): GlobeLocation | null => {
      const r = renderer.domElement.getBoundingClientRect();
      ndc.set(((cx - r.left) / r.width) * 2 - 1, -((cy - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(ndc, camera);
      const o = ray.ray.origin, d = ray.ray.direction;
      const hit = raySphere([o.x, o.y, o.z], [d.x, d.y, d.z]);
      return hit ? unitToLatLon(hit[0], hit[1], hit[2]) : null;
    };
    let down: { x: number; y: number; t: number; id: number } | null = null;
    const onDown = (e: PointerEvent) => { if (e.isPrimary) down = { x: e.clientX, y: e.clientY, t: performance.now(), id: e.pointerId }; };
    const onUp = (e: PointerEvent) => {
      const d = down;
      down = null;
      if (!d || d.id !== e.pointerId || e.button > 0) return;
      if (Math.hypot(e.clientX - d.x, e.clientY - d.y) > PICK_SLOP_PX || performance.now() - d.t > 700) return;
      const loc = locate(e.clientX, e.clientY);
      if (loc) choose(loc);
    };
    let hoverRaf = 0;
    const onMove = (e: PointerEvent) => {
      if (e.pointerType !== "mouse" || e.buttons) return;
      const x = e.clientX, y = e.clientY;
      if (hoverRaf) cancelAnimationFrame(hoverRaf);
      hoverRaf = requestAnimationFrame(() => { hoverRaf = 0; setHover(locate(x, y)); });
    };
    const onLeave = () => setHover(null);
    const cv = renderer.domElement;
    cv.addEventListener("pointerdown", onDown);
    cv.addEventListener("pointerup", onUp);
    cv.addEventListener("pointermove", onMove);
    cv.addEventListener("pointerleave", onLeave);
    const onLost = (e: Event) => { e.preventDefault(); setPhase(PHASE.contextLost); };
    cv.addEventListener("webglcontextlost", onLost);

    ctx.current = { renderer, scene, camera, controls, moon, grid: gridGroup, marker: mk, key, ambient, render, sync: onChange };

    // imagery: colour map plus relief (bump) shading; failures leave an untextured sphere and a visible note
    let alive = true;
    const loader = new THREE.TextureLoader();
    const maxAniso = renderer.capabilities.getMaxAnisotropy();
    Promise.all([loader.loadAsync(COLOR_URL), loader.loadAsync(RELIEF_URL).catch(() => null)]).then(([color, relief]) => {
      if (!alive) { color.dispose(); relief?.dispose(); return; }
      color.colorSpace = THREE.SRGBColorSpace;
      color.anisotropy = maxAniso;
      moonMat.map = color;
      moonMat.color.set(0xffffff);
      if (relief) {
        relief.colorSpace = THREE.NoColorSpace;
        moonMat.bumpMap = relief;
        moonMat.bumpScale = 3;
      }
      moonMat.needsUpdate = true;
      setPhase(PHASE.ready);
      render();
    }).catch(() => { if (alive) { setPhase(PHASE.imageryError); render(); } });

    const resize = () => {
      const w = el.clientWidth, h = el.clientHeight;
      renderer.setSize(w, h, false);
      cv.style.width = "100%";
      cv.style.height = "100%";
      camera.aspect = w / Math.max(h, 1);
      camera.updateProjectionMatrix();
      render();
    };
    const ro = new ResizeObserver(resize);
    ro.observe(el);
    resize();

    return () => {
      alive = false;
      disposed = true;
      if (raf) cancelAnimationFrame(raf);
      if (hoverRaf) cancelAnimationFrame(hoverRaf);
      ro.disconnect();
      controls.removeEventListener("change", onChange);
      controls.removeEventListener("start", onStart);
      cv.removeEventListener("pointerdown", onDown);
      cv.removeEventListener("pointerup", onUp);
      cv.removeEventListener("pointermove", onMove);
      cv.removeEventListener("pointerleave", onLeave);
      cv.removeEventListener("webglcontextlost", onLost);
      controls.dispose();
      disposeTree(scene);
      renderer.dispose();
      renderer.forceContextLoss();
      if (cv.parentNode === el) el.removeChild(cv);
      ctx.current = null;
    };
  }, [choose]);

  // marker follows the selection
  useEffect(() => {
    const c = ctx.current;
    if (!c) return;
    if (!pick) { c.marker.visible = false; c.render(); return; }
    const u = latLonToUnit(pick.lat, pick.lon);
    c.marker.position.set(u[0] * 1.001, u[1] * 1.001, u[2] * 1.001);
    c.marker.lookAt(u[0] * 2, u[1] * 2, u[2] * 2);
    c.marker.visible = true;
    const colour = selectedCovered === true ? COLORS.covered : selectedCovered === false ? COLORS.uncovered : COLORS.marker;
    c.marker.traverse((o) => { const m = (o as THREE.Mesh).material as THREE.MeshBasicMaterial | undefined; if (m?.color) m.color.setHex(colour); });
    c.render();
  }, [pick, phase, selectedCovered]);

  useEffect(() => { const c = ctx.current; if (c) { c.grid.visible = grid; c.render(); } }, [grid, phase]);
  useEffect(() => {
    const c = ctx.current;
    if (!c) return;
    c.ambient.intensity = even ? AMBIENT_EVEN : AMBIENT;
    c.key.intensity = even ? KEY_EVEN : KEY;
    c.render();
  }, [even, phase]);

  // view changes shared by the keys and the buttons
  const look = useCallback((loc: GlobeLocation, dist?: number) => {
    const c = ctx.current;
    if (!c) return;
    const d = Math.min(MAX_DIST, Math.max(MIN_DIST, dist ?? c.camera.position.length()));
    const lat = Math.max(-MAX_LAT, Math.min(MAX_LAT, loc.lat));
    const u = latLonToUnit(lat, loc.lon);
    c.camera.position.set(u[0] * d, u[1] * d, u[2] * d);
    c.camera.up.set(0, 1, 0);
    c.controls.update();
    c.sync();
  }, []);
  // smooth flight along the great circle (viewpoints, centre on selection); instant when reduced motion is requested
  const flyRaf = useRef(0);
  const fly = useCallback((loc: GlobeLocation, dist?: number) => {
    const c = ctx.current;
    if (!c) return;
    cancelAnimationFrame(flyRaf.current);
    const d0 = c.camera.position.length();
    const d1 = Math.min(MAX_DIST, Math.max(MIN_DIST, dist ?? d0));
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) { look(loc, d1); return; }
    const u = latLonToUnit(Math.max(-MAX_LAT, Math.min(MAX_LAT, loc.lat)), loc.lon);
    const a = c.camera.position.clone().normalize(), b = new THREE.Vector3(u[0], u[1], u[2]);
    const q = new THREE.Quaternion().setFromUnitVectors(a, b), qi = new THREE.Quaternion(), qk = new THREE.Quaternion();
    const t0 = performance.now();
    const step = (now: number) => {
      const k = Math.min(1, (now - t0) / FLY_MS);
      const e = k < 0.5 ? 2 * k * k : 1 - (-2 * k + 2) ** 2 / 2;
      qk.slerpQuaternions(qi, q, e);
      const v = a.clone().applyQuaternion(qk);
      const hit = unitToLatLon(v.x, v.y, v.z);
      look(hit, d0 + (d1 - d0) * e);
      if (k < 1) flyRaf.current = requestAnimationFrame(step);
      else look(loc, d1);
    };
    flyRaf.current = requestAnimationFrame(step);
  }, [look]);
  useEffect(() => () => cancelAnimationFrame(flyRaf.current), []);
  const centreOnSelection = useCallback(() => { if (pick) fly(pick, Math.min(ctx.current?.camera.position.length() ?? DEFAULT_DIST, SELECTION_DIST)); }, [pick, fly]);
  // a selection made elsewhere (typed, the map, the dashboard) while the globe is open is followed, so the view never stays
  // on a stale location; picks made on the globe itself do not move the camera
  const sLat = selected?.lat, sLon = selected?.lon;
  useEffect(() => {
    if (sLat == null || sLon == null || phase === PHASE.noWebGL) return;
    const own = announced;
    // the host rounds globe picks to 6 decimals (siteCoords), so compare with a tolerance
    if (own && Math.abs(own.lat - sLat) < 1e-5 && Math.abs(((own.lon - sLon + 540) % 360) - 180) < 1e-5) return;
    const p = ctx.current?.camera.position;
    if (p) { const c = unitToLatLon(p.x, p.y, p.z); if (Math.abs(c.lat - Math.max(-MAX_LAT, Math.min(MAX_LAT, sLat))) < 1e-6 && Math.abs(((c.lon - sLon + 540) % 360) - 180) < 1e-6) return; }
    const t = window.setTimeout(() => fly({ lat: sLat, lon: sLon }, Math.min(ctx.current?.camera.position.length() ?? DEFAULT_DIST, SELECTION_DIST)), FOLLOW_MS);
    return () => window.clearTimeout(t);
  }, [sLat, sLon, phase, fly]); // eslint-disable-line react-hooks/exhaustive-deps

  const turn = useCallback((dLat: number, dLon: number) => {
    const c = ctx.current;
    if (!c) return;
    const p = c.camera.position;
    const now = unitToLatLon(p.x, p.y, p.z);
    look({ lat: now.lat + dLat, lon: now.lon + dLon });
  }, [look]);
  const zoom = useCallback((f: number) => {
    const c = ctx.current;
    if (!c) return;
    const p = c.camera.position;
    look(unitToLatLon(p.x, p.y, p.z), p.length() * f);
  }, [look]);
  const selectCentre = useCallback(() => {
    const c = ctx.current;
    if (!c) return;
    const p = c.camera.position;
    choose(unitToLatLon(p.x, p.y, p.z));
  }, [choose]);

  // keyboard operation (U-04 2.1.1): the host is focusable; keys act only while it has focus
  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const onKey = (e: KeyboardEvent) => {
      const k = e.key;
      const step = e.shiftKey ? STEP_DEG / 5 : STEP_DEG;
      const act: Record<string, () => void> = {
        ArrowLeft: () => turn(0, -step), ArrowRight: () => turn(0, step), ArrowUp: () => turn(step, 0), ArrowDown: () => turn(-step, 0),
        "+": () => zoom(0.85), "=": () => zoom(0.85), "-": () => zoom(1 / 0.85), _: () => zoom(1 / 0.85),
        Enter: selectCentre, " ": selectCentre, Home: () => look(VIEWPOINTS.nearside, DEFAULT_DIST),
      };
      if (!act[k]) return;
      e.preventDefault();
      act[k]();
    };
    el.addEventListener("keydown", onKey);
    return () => el.removeEventListener("keydown", onKey);
  }, [turn, zoom, look, selectCentre]);

  const viewpoint = (v: Viewpoint) => fly(VIEWPOINTS[v], v === "nearside" || v === "farside" ? DEFAULT_DIST : 2.6);
  const message = phase === PHASE.noWebGL ? G.noWebGL : phase === PHASE.contextLost ? G.contextLost : phase === PHASE.loading ? G.loadingImagery : null;

  return (
    <div className="globe">
      <div className="globe-toolbar">
        <div className="view-controls globe-nav" role="group" aria-label={G.controls}>
          <button type="button" aria-label={G.turnWest} title={G.turnWest} onClick={() => turn(0, -STEP_DEG)}>{G.turnWestIcon}</button>
          <button type="button" aria-label={G.turnEast} title={G.turnEast} onClick={() => turn(0, STEP_DEG)}>{G.turnEastIcon}</button>
          <button type="button" aria-label={G.turnNorth} title={G.turnNorth} onClick={() => turn(STEP_DEG, 0)}>{G.turnNorthIcon}</button>
          <button type="button" aria-label={G.turnSouth} title={G.turnSouth} onClick={() => turn(-STEP_DEG, 0)}>{G.turnSouthIcon}</button>
          <button type="button" aria-label={G.zoomIn} title={G.zoomIn} onClick={() => zoom(0.85)}>{G.zoomInIcon}</button>
          <button type="button" aria-label={G.zoomOut} title={G.zoomOut} onClick={() => zoom(1 / 0.85)}>{G.zoomOutIcon}</button>
          <button type="button" aria-label={G.selectCentre} title={G.selectCentre} onClick={selectCentre}>{G.selectCentreIcon}</button>
          <button type="button" aria-label={G.centreOnSelection} title={G.centreOnSelection} onClick={centreOnSelection} disabled={!pick}>{G.centreOnSelectionIcon}</button>
        </div>
        <div className="globe-options">
          <div className="segmented-mini" role="group" aria-label={G.viewpoints}>
            <button type="button" onClick={() => viewpoint("nearside")}>{G.nearside}</button>
            <button type="button" onClick={() => viewpoint("farside")}>{G.farside}</button>
            <button type="button" onClick={() => viewpoint("north")}>{G.northPole}</button>
            <button type="button" onClick={() => viewpoint("south")}>{G.southPole}</button>
          </div>
          <div className="segmented-mini" role="group" aria-label={G.display}>
            <button type="button" aria-pressed={grid} title={G.gridTitle} onClick={() => setGrid(!grid)}>{G.grid}</button>
            <button type="button" aria-pressed={even} title={G.evenLightTitle} onClick={() => setEven(!even)}>{G.evenLight}</button>
          </div>
        </div>
      </div>
      <div className="globe-stage">
        <div className="globe-host" ref={host} role="region" tabIndex={0} aria-label={G.label} />
        {phase !== PHASE.noWebGL && phase !== PHASE.contextLost && <div className="globe-crosshair" aria-hidden />}
        <div className="globe-readout-mini" aria-hidden>
          <span>{G.centre(formatLocation(centre))}</span>
          {hover && <span>{G.pointer(formatLocation(hover))}</span>}
        </div>
        {message && <div className="pane-empty globe-message" role="status">{message}</div>}
      </div>
      {selectionPanel && <div className="globe-selection">
        <h4>{G.selectedHeading}</h4>
        <p className="globe-selected">{pick ? <strong>{formatLocation(pick)}</strong> : G.noneSelected}</p>
        {pick && <p className="hint">{G.signed(fmt(pick.lat), fmt(pick.lon))}</p>}
        {phase === PHASE.imageryError && <p className="hint bad" role="status">{G.imageryFailed}</p>}
      </div>}
      {!selectionPanel && phase === PHASE.imageryError && <p className="hint bad globe-inline-note" role="status">{G.imageryFailed}</p>}
      <p className="sr-only" aria-live="polite" aria-atomic="true">{announced ? G.announce(formatLocation(announced)) : ""}</p>
      <div className="pane-note globe-note">
        <p>{G.note}</p>
        <p>{G.limitNote}</p>
        <p>{G.integrity}</p>
        <p>{G.credit}</p>
      </div>
    </div>
  );
}
