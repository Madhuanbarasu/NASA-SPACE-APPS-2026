# Methods: geometry, link budget, relay, timelines, planner (comms 0.1.0)

## 1. Direct-to-Earth geometry (engine values, not recomputed)
- **Source.** Everything comes from a completed engine analysis result (algorithm 1.5.0):
  - Earth azimuth, elevation and distance;
  - light time, `dist / c`;
  - clearance `c = elevation − H(azimuth)`, where H is the 0.1° terrain-horizon profile;
  - visible disk fraction.
- **How the engine computes them.** Topocentric apparent geometry: SPICE `spkcpo`, observer at the site, converged light time and stellar aberration (CN+S). It uses the lunar body-fixed frame of the loaded kernels, east longitudes and the engine's leap-second and time handling.
- **Windows** are the engine's Earth-visibility intervals for the result's rule (centre, any or full disk). They come from adaptive event detection (about 1 s) and keep their `uncertain` flags and reasons.
- **Distance** is to the Earth's **centre**. A ground station could be up to about 6,371 km nearer or farther, which changes the free-space path loss by less than 0.15 dB at Earth–Moon distance. Ground stations are not modelled.
- **"Terrain-blocked" row** (display): the Earth's centre is above 0° elevation but its clearance is ≤ 0. It is drawn from the analysis series, with boundaries interpolated linearly between samples.
- **Labels:** the result's own engine labels, verbatim (see the README).

## 2. RF link budget (`linkbudget.py`), free space, single hop
| Term | Equation | Unit |
|---|---|---|
| Wavelength | λ = c / f, c = 299 792 458 m/s (exact) | m |
| Free-space path loss | FSPL = 20 log10(4πR/λ), R in m | dB |
| Transmit power | Pt = 10 log10(P[W]) when given in W | dBW |
| EIRP | Pt + Gt − Ltx | dBW |
| Received carrier power | Pr = EIRP − FSPL − Lother + Gr − Lrx (= Pt + Gt + Gr − Ltx − Lrx − Lother − FSPL) | dBW |
| Carrier-to-noise density | C/N0 = Pr − 10 log10(k) − 10 log10(Ts), k = 1.380649e−23 J/K (exact); 10 log10(k) = −228.599 | dB-Hz |
| Energy per bit to noise density | Eb/N0 = C/N0 − 10 log10(Rb) | dB |
| Link margin | Eb/N0 − (Eb/N0)required | dB |
| C/N (only if B given) | C/N0 − 10 log10(B) | dB |

- **No defaults.** All 12 inputs are optional and **none has a default**. A term is evaluated only if every input it needs is present and valid; otherwise it, and every later term, is "not evaluated", with the missing or invalid inputs named.
- **Rules:**
  - power > 0 W (or a dBW value);
  - frequency 1 kHz to 3 THz;
  - noise temperature > 0 K;
  - data rate > 0 bit/s;
  - bandwidth > 0 Hz;
  - losses ≥ 0 dB;
  - gains −50 to 100 dBi;
  - finite numbers only;
  - W and dBW given together must agree.
- **Source tag.** Each parameter set is tagged "Illustrative scenario (user-entered values, not hardware specifications)" or "Values the user attributes to a hardware specification", with a reference text.
- **Over time.** The margin is evaluated at each sample's distance. "RF-feasible" = geometric path open **and** margin > 0 dB, with the margin's zero crossings interpolated linearly between samples. A complete link budget does not guarantee a data rate: modulation, coding, the receiver implementation and scheduling are outside it.
- **Not modelled:** atmosphere, rain, polarisation mismatch, multipath, diffraction, lunar-surface propagation (NASA Glenn Lunar Surface Propagation research), interference and Doppler.

## 3. Hypothetical relay (`relay.py`)
- **Elements** (all required, no defaults): a [km], e (0 ≤ e < 1), i [0, 180]°, RAAN, argument of periapsis, mean anomaly at the epoch, epoch (ISO UTC, through the engine's SPICE time conversion), and frame.
- **Refused orbits:**
  - periapsis radius a(1 − e) ≤ 1737.4 km (the orbit hits the Moon);
  - a > 66,000 km (beyond the Moon's Hill sphere radius of about 60,000 km, where two-body motion is meaningless).
- **GM:** `BODY301_GM` = 4902.8001184575496 km³/s², parsed from NAIF `gm_de440.tpc`. The file's SHA-256 is `924ddf4f…`, checked against `data/comms/manifest.json`. Source: DE440, Park et al. 2021.
- **Propagation (analytic two-body):**
  - n = √(GM/a³) and M(t) = M0 + n(t − t_epoch);
  - E − e sin E = M is solved by Newton iteration to 1e−15 rad;
  - perifocal position (a(cos E − e), a√(1 − e²) sin E, 0) and velocity;
  - rotation R3(−Ω) R1(−i) R3(−ω) into the element frame.
- **Frames:**
  - **J2000:** Moon-centred, SPICE J2000 axes (inclination measured from the Earth's mean equator of J2000).
  - **LME_EPOCH:** Moon-centred inertial frame equal to the engine's lunar body-fixed frame at the epoch (`MOON_ME_DE440_ME421` in the installed kernel set). Inclination is measured from the lunar mean equator. r_J2000 = pxform(MOON_ME → J2000, epoch) · r.
  - At each sample: r_body = pxform(J2000 → MOON_ME, t) · r_J2000.
- **Leg 1, lander → relay:**
  - the site is the engine's `Site` (ground height plus observer height) with its east-north-up basis;
  - elevation = asin(d̂·up) and azimuth = atan2(d̂·east, d̂·north);
  - **open** when the clearance above the site's terrain horizon H(azimuth) (the engine's `HorizonProfile`, built from the result) is > 0 **and** the line does not cross the lunar sphere. That sphere is the 1737.4 km sphere, or one just below the site if the site lies lower.
  - **unknown** when either bracketing horizon bin is incomplete;
  - **uncertain** when |clearance| ≤ the horizon σ of the bin.
  - The horizon test is direction-based. It is exact when the blocking terrain is nearer than the relay, which is true for any relay above the terrain.
- **Leg 2, relay → Earth:**
  - The Earth's position relative to the Moon's centre is SPICE `spkpos(EARTH, t, J2000, CN+S, MOON)`.
  - **Open** when the Earth's centre is outside the lunar disk seen from the relay: the angle between Earth and Moon centre, minus asin((R + grazing altitude)/|r|), is > 0. The grazing altitude is user-set and defaults to 0 km.
  - Earth's own disk, atmosphere and ground stations are not modelled.
- **Relay-assisted** = leg 1 AND leg 2. **Relay RF-feasible** = (leg 1 AND margin of the uplink budget > 0) AND (leg 2 AND margin of the downlink budget > 0).
- **Effects of the two-body approximation:**
  - neglected: lunar gravity-field harmonics (mascons, J2, C22), Earth and Sun third-body perturbations, and radiation pressure;
  - low lunar orbits change noticeably within days, and many decay or crash within weeks to months;
  - high and elliptical orbits are strongly perturbed by the Earth over weeks;
  - so the simulated geometry is an idealised orbit with the given initial elements, not a prediction of a real spacecraft.

## 4. Timelines (`windows.py`)
- **Segments.** Each path is a list of segments with state open, closed or unknown, covering the whole window. Gaps in a source become unknown.
- **Logic is three-valued:**
  - AND is closed if any input is closed, unknown if any input is unknown (and none is closed), otherwise open;
  - OR is open if any input is open, unknown if any input is unknown (and none is open), otherwise closed.
  
  Unknown is never counted as open or closed.
- **Sample-based boundaries** (relay legs, margins) come from linear interpolation of the clearance or margin between the two samples with opposite signs. A segment touching an unknown sample is unknown from the midpoint. Contacts shorter than one sampling step can be missed.
- **Statistics:** open time, number of windows, uncertain windows, longest window, gaps between windows (count, mean, longest, counting closed or unknown time), and unknown time. There are no reliability figures.
- **Next change:** the state at a reference time, the next boundary, and the current or next open window.

## 5. Store-and-forward planner (conceptual)
- **Model.** A volume V (Mbit) is ready at time t0 and sent at rate r (kbit/s) during the open segments of the chosen path. The transmission time needed is V/r.
- **Outputs:** the contacts used, the completion time (or "not within the window") and the volume still queued.
- **Not modelled:** protocol overhead, acknowledgements, light time, handover, priorities and ground scheduling. This is a high-level contact-planning simulation inspired by DTN, **not** a Bundle Protocol implementation and **not** LunaNet interoperability.
