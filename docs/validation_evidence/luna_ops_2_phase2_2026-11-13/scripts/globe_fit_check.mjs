// LUNA-OPS 2.0 Phase 2: the whole-disc framing (MoonGlobe fitDistance) checked with three.js's own camera projection.
// For each stage size, the camera is placed at fitDistance on the +z axis looking at the globe; the silhouette (tangent)
// points are projected to NDC and the disc's on-screen diameter compared with the target: 90 % of the stage height, or
// 92 % of its width when that is smaller. Run from frontend/: node <this file>
import * as THREE from "three";
import ts from "typescript";
import fs from "node:fs";
const src = fs.readFileSync("src/components/MoonGlobe.tsx", "utf8");
const body = src.slice(src.indexOf("export function fitDistance"), src.indexOf("/** The 60 S line"));
const consts = ["FOV_DEG", "FIT_HEIGHT", "FIT_WIDTH", "DEFAULT_DIST", "MIN_DIST", "MAX_DIST"].map((k) => src.match(new RegExp(`const ${k} = [^;]+;`))[0]).join("\n");
const js = ts.transpileModule(consts + "\n" + body, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { fitDistance } = await import("data:text/javascript;base64," + Buffer.from(js).toString("base64"));
let worst = 0;
for (const [w, h] of [[764, 769], [1092, 769], [1784, 949], [698, 636], [358, 523], [320, 300], [1200, 420]]) {
  const d = fitDistance(w, h);
  const cam = new THREE.PerspectiveCamera(35, w / h, 0.01, 200);
  cam.position.set(0, 0, d); cam.lookAt(0, 0, 0); cam.updateMatrixWorld(); cam.updateProjectionMatrix();
  const rt = Math.sqrt(1 - 1 / (d * d)), zt = 1 / d;               // tangent circle of the sphere seen from the camera
  const top = new THREE.Vector3(0, rt, zt).project(cam), side = new THREE.Vector3(rt, 0, zt).project(cam);
  const fracH = top.y;                                              // disc diameter / stage height (NDC spans 2)
  const fracW = side.x;                                             // disc diameter / stage width
  const target = Math.min(0.9, 0.92 * w / h);
  const err = Math.abs(fracH - target);
  worst = Math.max(worst, err);
  console.log(`${w}x${h}: distance ${d.toFixed(4)}, disc ${(fracH * h).toFixed(1)} px = ${(100 * fracH).toFixed(3)} % of height, ${(100 * fracW).toFixed(3)} % of width (target ${(100 * target).toFixed(3)} % of height)`);
}
console.log("worst |fraction - target|", worst.toExponential(2), worst < 1e-9 ? "OK" : "FAIL");
process.exit(worst < 1e-9 ? 0 : 1);
