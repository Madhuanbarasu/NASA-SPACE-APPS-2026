// LUNA-OPS 2.0 Phase 4: the south polar locator's orientation and radius checked against the map's projection.
// The locator places a site at angle lon (0 deg E up, clockwise on screen to 90 deg E on the right) and radius
// proportional to its angular distance from the pole (azimuthal equidistant). The south polar map (MapView) uses
// proj4 "+proj=stere +lat_0=-90 ... +lon_0=0". Both must put every site in the same direction from the pole (bearing on
// screen, with screen y downward), so the locator reads like the map. Run from frontend/: node <this file>
import proj4 from "proj4";
proj4.defs("SPS", "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs");
proj4.defs("GEO", "+proj=longlat +R=1737400 +no_defs");
// the locator's formula (MissionLocator.tsx): x = cx + r sin(lon), y = cy - r cos(lon), r = R (90 + lat) / 30
const locator = (lat, lon) => { const r = (90 + lat) / 30, a = lon * Math.PI / 180; return [r * Math.sin(a), -r * Math.cos(a)]; };
let worst = 0;
for (const [lat, lon] of [[-89.463163, 222.510447], [-89.2, 200], [-85, 0], [-85, 90], [-80, 180], [-75, 270], [-62, 45], [-70, 315.5]]) {
  const [mx, my] = proj4("GEO", "SPS", [lon > 180 ? lon - 360 : lon, lat]);           // map metres, y up
  const mapBearing = Math.atan2(mx, my) * 180 / Math.PI;                               // clockwise from screen-up
  const [lx, ly] = locator(lat, lon);                                                   // screen units, y down
  const locBearing = Math.atan2(lx, -ly) * 180 / Math.PI;
  const d = Math.abs(((mapBearing - locBearing + 540) % 360) - 180);
  worst = Math.max(worst, d);
  console.log(`lat ${lat} lon ${lon}: map bearing ${mapBearing.toFixed(6)} deg, locator bearing ${locBearing.toFixed(6)} deg, diff ${d.toExponential(2)}; locator radius ${(Math.hypot(lx, ly)).toFixed(5)} of the 60 S ring`);
}
console.log("worst bearing difference (deg)", worst.toExponential(2), worst < 1e-6 ? "OK" : "FAIL");
process.exit(worst < 1e-6 ? 0 : 1);
