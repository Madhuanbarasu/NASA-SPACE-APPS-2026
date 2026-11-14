import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { api } from "../api/client";
import type { TerrainGrid } from "../api/types";
import { S } from "../i18n";
import { gridMesh, gridStats } from "../lib/terrainStats";
import { Icon } from "../ui/Icon";
import { StageLegend } from "../ui/StageLegend";

// Phase 5: local terrain around a selected site BEFORE an analysis, from GET /api/terrain (the registered LOLA DEM,
// display-averaged by the backend). Unlike the result view's Terrain3D, cells without data stay empty: no triangle is
// drawn for them and no height is filled in, so nothing outside the registered coverage is shown as terrain.
// Loaded on demand (shares the three.js chunk with the globe and Terrain3D).

interface Props {
  lat: number; lon: number;
  /** finest registered level at the point itself (GET /api/coverage), to explain a coarser 3D window */
  finest?: string | null;
}
const RADII_KM = [2, 4, 8, 16];
const CAMERA_START: [number, number, number] = [-9000, -11000, 7000];

const P = S.terrainPreview;
const V = S.terrain3d;
// Phase 3: the grid statistics and gap-preserving mesh are shared with the analysis terrain (lib/terrainStats)

export function TerrainPreview({ lat, lon, finest = null }: Props) {
  const [radiusKm, setRadiusKm] = useState(8);
  const host = useRef<HTMLDivElement>(null);
  const [grid, setGrid] = useState<TerrainGrid | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [noWebGL, setNoWebGL] = useState(false);
  const [exag, setExag] = useState(2);
  const three = useRef<{ renderer: THREE.WebGLRenderer; scene: THREE.Scene; camera: THREE.PerspectiveCamera;
    controls: OrbitControls; mesh?: THREE.Mesh; site?: THREE.Mesh; render: () => void } | null>(null);
  const stats = useMemo(() => (grid ? gridStats(grid) : null), [grid]);

  useEffect(() => {
    let live = true;
    setGrid(null); setErr(null);
    api.terrain(lat, lon, radiusKm).then((g) => { if (live) setGrid(g); }).catch((e) => { if (live) setErr(String(e.message || e)); });
    return () => { live = false; };
  }, [lat, lon, radiusKm]);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setNoWebGL(true);
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, 1, 10, 200000);
    camera.up.set(0, 0, 1);
    camera.position.set(...CAMERA_START);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 0, 0);
    scene.add(new THREE.AmbientLight(0x8fa3bd, 0.55));
    const light = new THREE.DirectionalLight(0xfff1d6, 2.2);   // illustrative, fixed (not a Sun direction)
    light.position.set(-6000, 8000, 9000);
    scene.add(light);
    // render on demand; a frame still queued at unmount is cancelled (it must never run after forceContextLoss)
    let raf = 0, disposed = false;
    const render = () => {
      if (raf || disposed) return;
      raf = requestAnimationFrame(() => { raf = 0; if (!disposed) renderer.render(scene, camera); });
    };
    controls.addEventListener("change", render);
    controls.listenToKeyEvents(el);                        // arrows pan, Shift/Ctrl + arrows rotate (U-04 2.1.1)
    const onZoomKey = (e: KeyboardEvent) => {
      const f = e.key === "+" || e.key === "=" ? 0.85 : e.key === "-" || e.key === "_" ? 1 / 0.85 : 0;
      if (!f) return;
      e.preventDefault();
      camera.position.sub(controls.target).multiplyScalar(f).add(controls.target);
      controls.update();
      render();
    };
    el.addEventListener("keydown", onZoomKey);
    three.current = { renderer, scene, camera, controls, render };
    const resize = () => {
      const w = el.clientWidth, h = el.clientHeight;
      renderer.setSize(w, h, false);
      renderer.domElement.style.width = "100%";
      renderer.domElement.style.height = "100%";
      camera.aspect = w / Math.max(h, 1);
      camera.updateProjectionMatrix();
      render();
    };
    const ro = new ResizeObserver(resize);
    ro.observe(el);
    resize();
    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      controls.removeEventListener("change", render);
      el.removeEventListener("keydown", onZoomKey);
      ro.disconnect();
      controls.stopListenToKeyEvents();
      controls.dispose();
      scene.traverse((o) => {
        const m = o as THREE.Mesh;
        m.geometry?.dispose();
        (Array.isArray(m.material) ? m.material : m.material ? [m.material] : []).forEach((x) => x.dispose());
      });
      renderer.dispose();
      renderer.forceContextLoss();
      if (renderer.domElement.parentNode === el) el.removeChild(renderer.domElement);
      three.current = null;
    };
  }, []);

  // terrain mesh: only cells whose four corners have data are drawn; heights relative to the site's surroundings
  useEffect(() => {
    const t = three.current;
    if (!t) return;
    if (t.mesh) { t.scene.remove(t.mesh); t.mesh.geometry.dispose(); (t.mesh.material as THREE.Material).dispose(); t.mesh = undefined; }
    if (t.site) { t.scene.remove(t.site); t.site.geometry.dispose(); (t.site.material as THREE.Material).dispose(); t.site = undefined; }
    if (!grid || !stats) { t.render(); return; }
    const n = grid.n, size = 2 * grid.radius_m;
    const ref = stats.centre ?? stats.mean;
    const geo = new THREE.PlaneGeometry(size, size, n - 1, n - 1);
    const pos = geo.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < pos.count; i++) {
      const h = grid.heights[i];
      const ok = h != null && Number.isFinite(h);
      pos.setZ(i, ok ? ((h as number) - ref) * exag : 0);   // z of a no-data vertex is never drawn (no triangle uses it)
    }
    const { index, colors } = gridMesh(grid, stats);
    geo.setIndex(index);
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    geo.computeVertexNormals();
    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.95, metalness: 0, side: THREE.DoubleSide }));
    t.scene.add(mesh);
    t.mesh = mesh;
    const site = new THREE.Mesh(new THREE.ConeGeometry(70, 260, 12), new THREE.MeshBasicMaterial({ color: 0xffd98a }));
    site.rotation.x = Math.PI / 2;
    site.position.set(0, 0, 130);                         // cone tip at the reference height (window centre)
    t.scene.add(site);
    t.site = site;
    t.render();
  }, [grid, stats, exag]);

  const resetView = () => {
    const t = three.current;
    if (!t) return;
    t.controls.target.set(0, 0, 0);
    t.camera.position.set(...CAMERA_START);
    t.controls.update();
    t.render();
  };
  const nudge = (kind: "left" | "right" | "in" | "out") => {
    const t = three.current;
    if (!t) return;
    const off = t.camera.position.clone().sub(t.controls.target);
    if (kind === "left" || kind === "right") off.applyAxisAngle(new THREE.Vector3(0, 0, 1), (kind === "left" ? 1 : -1) * Math.PI / 12);
    else off.multiplyScalar(kind === "in" ? 0.85 : 1 / 0.85);
    t.camera.position.copy(t.controls.target).add(off);
    t.controls.update();
    t.render();
  };

  const loading = !noWebGL && !err && !grid;
  const message = noWebGL ? S.globe.noWebGL : err ? P.error(err) : !grid ? P.loadingWindow(radiusKm) : !stats ? P.notCovered : null;
  const levelInfo = grid ? P.product(grid.level, grid.product) : null;

  return (
    <div className="terrain-preview">
      <div className="pane-body terrain-preview-stage">
        <div className="view-controls terrain-nav" role="group" aria-label={V.viewControls}>
          <button type="button" aria-label={P.resetView} title={P.resetView} onClick={resetView}><Icon name="reset" /></button>
          <button type="button" aria-label={V.rotateLeft} title={V.rotateLeft} onClick={() => nudge("left")}><Icon name="rotateLeft" /></button>
          <button type="button" aria-label={V.rotateRight} title={V.rotateRight} onClick={() => nudge("right")}><Icon name="rotateRight" /></button>
          <button type="button" aria-label={V.zoomIn} title={V.zoomIn} onClick={() => nudge("in")}><Icon name="plus" /></button>
          <button type="button" aria-label={V.zoomOut} title={V.zoomOut} onClick={() => nudge("out")}><Icon name="minus" /></button>
        </div>
        <div className="three-host" ref={host} aria-label={P.label} role="region" tabIndex={0} />
        {/* Phase 2: window and exaggeration float over the stage; the full statistics stay under it */}
        <div className="terrain-options">
          <label className="terrain-exag">{P.radius}{" "}
            <select value={radiusKm} onChange={(e) => setRadiusKm(Number(e.target.value))} aria-label={P.radiusLabel}>
              {RADII_KM.map((v) => <option key={v} value={v}>{P.radiusOption(v)}</option>)}
            </select>
          </label>
          <label className="terrain-exag">{V.exaggeration}{" "}
            <select value={exag} onChange={(e) => setExag(Number(e.target.value))} aria-label={V.exaggerationLabel}>
              {[1, 2, 4].map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </label>
        </div>
        {grid && stats && (
          <StageLegend className="terrain-legend" items={[
            { swatch: "dot", color: "var(--valid)", text: P.product(grid.level, grid.product) },
            { swatch: "hatch", text: P.legendGaps },
          ]}>
            <div className="height-key">
              <span className="height-key-title">{P.legendHeights}</span>
              <span className="height-ramp" aria-hidden />
              <span className="height-key-ends"><span>{P.legendMin(stats.min.toFixed(0))}</span><span>{P.legendMax(stats.max.toFixed(0))}</span></span>
            </div>
          </StageLegend>
        )}
        {message && <div className={loading ? "pane-empty is-loading" : "pane-empty"} role="status">{message}</div>}
      </div>
      <div className="terrain-stats" aria-label={P.statsHeading}>
        <h4>{P.statsHeading}</h4>
        {grid && stats ? (
          <ul>
            <li>{levelInfo}</li>
            <li>{P.grid(grid.n, stats.cellM.toFixed(0), radiusKm)}</li>
            <li>{P.heights(stats.min.toFixed(0), stats.mean.toFixed(0), stats.max.toFixed(0))}</li>
            <li>{stats.centre != null ? P.centre(stats.centre.toFixed(1)) : P.centreNone}</li>
            <li>{P.dataShare(((100 * stats.valid) / stats.total).toFixed(1))}</li>
            <li>{P.legend(stats.min.toFixed(0), stats.max.toFixed(0))}</li>
          </ul>
        ) : <p className="hint">{err ? P.error(err) : P.loading}</p>}
        <p className="hint">{P.lighting}</p>
        {grid && finest && grid.level !== finest && <p className="hint">{P.coarserWindow(grid.level, finest, radiusKm)}</p>}
      </div>
    </div>
  );
}
