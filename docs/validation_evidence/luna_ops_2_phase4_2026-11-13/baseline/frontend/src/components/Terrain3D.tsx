import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { api } from "../api/client";
import type { Result, TerrainGrid } from "../api/types";
import { S } from "../i18n";
import { gridMesh, gridStats } from "../lib/terrainStats";
import { Icon } from "../ui/Icon";
import { Metric } from "../ui/Metric";
import { StageLegend } from "../ui/StageLegend";

interface Props { result: Result; cursor: number }

const dot = (a: number[], b: number[]) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const RADIUS_KM = 8;
const CAMERA_START: [number, number, number] = [-9000, -11000, 7000];
const V = S.terrain3d;
const P = S.terrainPreview;
const A = S.analysis;

// The scene frame is the projection grid (x, y) plus local up. Served body-fixed unit vectors are placed in it with dot
// products against served grid axes (C09). LUNA-OPS 2.0 Phase 3: cells without data are no longer filled with the
// window's lowest height; like the explorer's local terrain, only cells whose four corners have data are drawn, so a gap
// in the registered terrain shows as a gap. Heights are coloured with the same grey ramp, and the WebGL context is
// released on unmount.
export function Terrain3D({ result, cursor }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const [grid, setGrid] = useState<TerrainGrid | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [exag, setExag] = useState(2);
  const three = useRef<{ renderer: THREE.WebGLRenderer; scene: THREE.Scene; camera: THREE.PerspectiveCamera;
    sun: THREE.DirectionalLight; earth: THREE.Mesh; sunMarker: THREE.Mesh; site: THREE.Mesh; mesh?: THREE.Mesh; controls: OrbitControls;
    render: () => void } | null>(null);
  const stats = useMemo(() => (grid ? gridStats(grid) : null), [grid]);

  useEffect(() => {
    let live = true;
    setGrid(null); setErr(null);
    api.terrain(result.site.lat, result.site.lon, RADIUS_KM).then((g) => { if (live) setGrid(g); })
      .catch((e) => { if (live) setErr(String(e.message || e)); });
    return () => { live = false; };
  }, [result.site.lat, result.site.lon]);

  useEffect(() => {
    if (!host.current) return;
    const el = host.current;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setErr(V.noWebGL);
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
    scene.add(new THREE.AmbientLight(0x6f84a0, 0.35));
    const sun = new THREE.DirectionalLight(0xfff1d6, 2.4);
    scene.add(sun);
    const earth = new THREE.Mesh(new THREE.SphereGeometry(260, 24, 16), new THREE.MeshBasicMaterial({ color: 0x5fa8e8 }));
    const sunMarker = new THREE.Mesh(new THREE.SphereGeometry(200, 24, 16), new THREE.MeshBasicMaterial({ color: 0xf2b544 }));
    scene.add(earth, sunMarker);
    const site = new THREE.Mesh(new THREE.ConeGeometry(70, 260, 12), new THREE.MeshBasicMaterial({ color: 0xffd98a }));
    site.rotation.x = Math.PI / 2;
    site.position.set(0, 0, 130);
    scene.add(site);
    // nothing is drawn until terrain and the Sun/Earth directions are loaded
    earth.visible = sunMarker.visible = site.visible = false;
    // render on demand; a frame still queued at unmount is cancelled (it must never run after forceContextLoss)
    let raf = 0, disposed = false;
    const render = () => {
      if (raf || disposed) return;
      raf = requestAnimationFrame(() => { raf = 0; if (!disposed) renderer.render(scene, camera); });
    };
    controls.addEventListener("change", render);
    // U-04 (2.1.1): arrows pan, Shift/Ctrl + arrows rotate (OrbitControls), + and - zoom toward the site
    controls.listenToKeyEvents(el);
    const onZoomKey = (e: KeyboardEvent) => {
      const f = e.key === "+" || e.key === "=" ? 0.85 : e.key === "-" || e.key === "_" ? 1 / 0.85 : 0;
      if (!f) return;
      e.preventDefault();
      camera.position.sub(controls.target).multiplyScalar(f).add(controls.target);
      controls.update();
      render();
    };
    el.addEventListener("keydown", onZoomKey);
    three.current = { renderer, scene, camera, sun, earth, sunMarker, site, controls, render };
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

  // terrain mesh: only cells whose four corners have data are drawn; heights relative to the site's ground height
  useEffect(() => {
    const t = three.current;
    if (!t) return;
    if (t.mesh) { t.scene.remove(t.mesh); t.mesh.geometry.dispose(); (t.mesh.material as THREE.Material).dispose(); t.mesh = undefined; }
    if (!grid || !stats) { t.render(); return; }
    const n = grid.n, size = 2 * grid.radius_m;
    const ground = result.site.ground_h_m;
    const geo = new THREE.PlaneGeometry(size, size, n - 1, n - 1);
    const pos = geo.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < pos.count; i++) {
      const h = grid.heights[i];
      pos.setZ(i, h != null && Number.isFinite(h) ? (h - ground) * exag : 0);   // a no-data vertex is never used by a triangle
    }
    const { index, colors } = gridMesh(grid, stats);
    geo.setIndex(index);
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    geo.computeVertexNormals();
    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.95, metalness: 0, side: THREE.DoubleSide }));
    t.scene.add(mesh);
    t.mesh = mesh;
    t.site.visible = true;
    t.render();
  }, [grid, stats, exag, result.site.ground_h_m]);

  // light and markers from served unit vectors at the cursor
  const sunU = result.series.sun.unit[cursor];
  const earthU = result.series.earth.unit[cursor];
  useEffect(() => {
    const t = three.current;
    if (!t || !grid || !sunU || !earthU) return;
    const b = grid.grid_basis_bodyfixed;
    const toScene = (u: number[]) => new THREE.Vector3(dot(u, b.x), dot(u, b.y), dot(u, b.up));
    const s = toScene(sunU), e = toScene(earthU);
    const R = 14000;
    t.sun.position.copy(s.clone().multiplyScalar(R));
    t.sun.intensity = s.z > -0.01 ? 2.4 : 0.0;
    t.sunMarker.position.copy(s.clone().multiplyScalar(R));
    t.earth.position.copy(e.clone().multiplyScalar(R));
    t.earth.visible = t.sunMarker.visible = true;
    t.render();
  }, [sunU, earthU, grid]);

  // U-04 (2.5.7): the same view changes as dragging, from buttons
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
  const resetView = () => {
    const t = three.current;
    if (!t) return;
    t.controls.target.set(0, 0, 0);
    t.camera.position.set(...CAMERA_START);
    t.controls.update();
    t.render();
  };
  const heights = grid ? (/SYNTHETIC/i.test(grid.product ?? "") ? V.syntheticHeights(grid.level) : V.lolaHeights(grid.level)) : null;

  return (
    <>
      <div className="pane-body terrain-stage">
        <div className="view-controls terrain-nav" role="group" aria-label={V.viewControls}>
          <button type="button" aria-label={P.resetView} title={P.resetView} onClick={resetView}><Icon name="reset" /></button>
          <button type="button" aria-label={V.rotateLeft} title={V.rotateLeft} onClick={() => nudge("left")}><Icon name="rotateLeft" /></button>
          <button type="button" aria-label={V.rotateRight} title={V.rotateRight} onClick={() => nudge("right")}><Icon name="rotateRight" /></button>
          <button type="button" aria-label={V.zoomIn} title={V.zoomIn} onClick={() => nudge("in")}><Icon name="plus" /></button>
          <button type="button" aria-label={V.zoomOut} title={V.zoomOut} onClick={() => nudge("out")}><Icon name="minus" /></button>
        </div>
        <div className="three-host" ref={host} aria-label={V.label} role="region" tabIndex={0} />
        <div className="terrain-options">
          <label className="terrain-exag">{V.exaggeration}{" "}
            <select value={exag} onChange={(e) => setExag(Number(e.target.value))} aria-label={V.exaggerationLabel}>
              {[1, 2, 4].map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </label>
        </div>
        {grid && stats && (
          <StageLegend className="terrain-legend" items={[
            { swatch: "dot", color: "var(--sun)", text: A.t3dSun },
            { swatch: "dot", color: "var(--earth)", text: A.t3dEarth },
            { swatch: "pin", color: "var(--focus)", text: A.t3dSite },
            { swatch: "hatch", text: P.legendGaps },
          ]}>
            <div className="height-key">
              <span className="height-key-title">{P.legendHeights}</span>
              <span className="height-ramp" aria-hidden />
              <span className="height-key-ends"><span>{P.legendMin(stats.min.toFixed(0))}</span><span>{P.legendMax(stats.max.toFixed(0))}</span></span>
            </div>
          </StageLegend>
        )}
        {(err || !grid) && <div className={err ? "pane-empty pane-message" : "pane-empty pane-message is-loading"} role="status">{err ?? V.loading}</div>}
        {grid && !stats && !err && <div className="pane-empty pane-message" role="status">{P.notCovered}</div>}
      </div>
      <div className="pane-note">{heights ? V.note(heights, RADIUS_KM) : " "}</div>
      {grid && stats && (
        <dl className="metrics terrain-figures" aria-label={P.statsHeading}>
          <Metric label={A.tfProduct} value={grid.level} note={grid.product} />
          <Metric label={A.tfHeights} value={A.tfRange(stats.min.toFixed(0), stats.max.toFixed(0))} note={A.tfMean(stats.mean.toFixed(0))} />
          <Metric label={A.tfCentre} value={stats.centre != null ? A.metres(stats.centre.toFixed(1)) : S.common.na}
                  state={stats.centre != null ? undefined : "unknown"} />
          <Metric label={A.tfGround} value={A.metres(result.site.ground_h_m.toFixed(1))} note={A.tfGroundNote(result.site.terrain_level_at_site)} />
          <Metric label={A.tfGrid} value={A.tfGridValue(grid.n, stats.cellM.toFixed(0))} note={A.tfRadius(RADIUS_KM)} />
          <Metric label={A.tfData} value={A.percent(((100 * stats.valid) / stats.total).toFixed(1))}
                  note={stats.valid < stats.total ? A.tfGaps(stats.total - stats.valid) : A.tfNoGaps}
                  state={stats.valid < stats.total ? "flag" : undefined} />
        </dl>
      )}
    </>
  );
}
