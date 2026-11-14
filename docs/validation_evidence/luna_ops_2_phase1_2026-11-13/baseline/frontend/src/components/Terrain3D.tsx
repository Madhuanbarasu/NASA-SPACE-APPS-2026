import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { api } from "../api/client";
import type { Result, TerrainGrid } from "../api/types";
import { S } from "../i18n";

interface Props { result: Result; cursor: number }

const dot = (a: number[], b: number[]) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];

// The scene frame is the projection grid (x, y) plus local up. Served body-fixed unit
// vectors are placed in it with dot products against served grid axes (C09).
export function Terrain3D({ result, cursor }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const [grid, setGrid] = useState<TerrainGrid | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [exag, setExag] = useState(2);
  const three = useRef<{ renderer: THREE.WebGLRenderer; scene: THREE.Scene; camera: THREE.PerspectiveCamera;
    sun: THREE.DirectionalLight; earth: THREE.Mesh; sunMarker: THREE.Mesh; site: THREE.Mesh; mesh?: THREE.Mesh; controls: OrbitControls;
    render: () => void } | null>(null);
  const radiusKm = 8;

  useEffect(() => {
    setGrid(null); setErr(null);
    api.terrain(result.site.lat, result.site.lon, radiusKm).then(setGrid).catch((e) => setErr(String(e.message || e)));
  }, [result.site.lat, result.site.lon]);

  useEffect(() => {
    if (!host.current) return;
    const el = host.current;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setErr(S.terrain3d.noWebGL);
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, 1, 10, 200000);
    camera.up.set(0, 0, 1);
    camera.position.set(-9000, -11000, 7000);
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
    scene.add(site);
    // Phase 5 prompt 4: nothing is drawn until terrain and the Sun/Earth directions are loaded (before, the markers sat at
    // the origin and showed through the "no terrain" message)
    earth.visible = sunMarker.visible = site.visible = false;
    // Render on demand (camera moves, data changes, resizes) instead of every frame.
    let pending = false;
    const render = () => {
      if (pending) return;
      pending = true;
      requestAnimationFrame(() => { pending = false; renderer.render(scene, camera); });
    };
    controls.addEventListener("change", render);
    // U-04 (2.1.1): keyboard operation when the view has focus: arrows pan, Shift/Ctrl + arrows rotate (OrbitControls),
    // + and - zoom toward the site
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
    render();
    return () => { controls.removeEventListener("change", render); el.removeEventListener("keydown", onZoomKey); ro.disconnect();
                   controls.stopListenToKeyEvents(); controls.dispose(); renderer.dispose();
                   el.removeChild(renderer.domElement); three.current = null; };
  }, []);

  // terrain mesh
  useEffect(() => {
    const t = three.current;
    if (!t || !grid) return;
    if (t.mesh) { t.scene.remove(t.mesh); t.mesh.geometry.dispose(); }
    const n = grid.n, size = 2 * grid.radius_m;
    const geo = new THREE.PlaneGeometry(size, size, n - 1, n - 1);
    const ground = result.site.ground_h_m;
    const valid = grid.heights.filter((v): v is number => v != null);
    const fallback = valid.length ? Math.min(...valid) : ground;
    const pos = geo.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < pos.count; i++) pos.setZ(i, ((grid.heights[i] ?? fallback) - ground) * exag);
    geo.computeVertexNormals();
    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: 0x8c99a6, roughness: 0.95, metalness: 0 }));
    t.scene.add(mesh);
    t.mesh = mesh;
    t.site.visible = true;
    t.render();
  }, [grid, exag, result.site.ground_h_m]);

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
  const V = S.terrain3d;

  return (
    <>
      <div className="pane-body">
        <div className="view-controls" role="group" aria-label={V.viewControls}>
          <button type="button" aria-label={V.rotateLeft} title={V.rotateLeft} onClick={() => nudge("left")}>{V.rotateLeftIcon}</button>
          <button type="button" aria-label={V.rotateRight} title={V.rotateRight} onClick={() => nudge("right")}>{V.rotateRightIcon}</button>
          <button type="button" aria-label={V.zoomIn} title={V.zoomIn} onClick={() => nudge("in")}>{V.zoomInIcon}</button>
          <button type="button" aria-label={V.zoomOut} title={V.zoomOut} onClick={() => nudge("out")}>{V.zoomOutIcon}</button>
        </div>
        <div className="three-host" ref={host} aria-label={S.terrain3d.label} role="region" tabIndex={0} />
        {(err || !grid) && <div className="pane-empty pane-message" role="status">{err ?? S.terrain3d.loading}</div>}
      </div>
      <div className="pane-note" style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
        <span>{grid ? S.terrain3d.note(/SYNTHETIC/i.test(grid.product ?? "") ? S.terrain3d.syntheticHeights(grid.level)
          : S.terrain3d.lolaHeights(grid.level), radiusKm) : "\u00a0"}</span>
        <label>{S.terrain3d.exaggeration}{" "}
          <select value={exag} onChange={(e) => setExag(Number(e.target.value))} aria-label={S.terrain3d.exaggerationLabel}>
            {[1, 2, 4].map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </label>
      </div>
    </>
  );
}
