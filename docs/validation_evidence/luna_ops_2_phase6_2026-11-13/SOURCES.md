# Sources, references and scenario provenance

## Data used
| Item | Source | Verification |
|---|---|---|
| Earth geometry, Earth-visibility intervals, terrain horizon, engine labels | Completed engine analysis results (`data/cache/result_<id>.json`), algorithm 1.5.0, code fingerprint `84cbd4ea…` | Read only. Every result records its own provenance: kernels with SHA-256, terrain products, rules. |
| SPICE kernels (frames and the Earth's position for the relay) | The engine's production kernel set (`data/kernels/lock.json`): naif0012.tls, pck00011.tpc, de440s.bsp, moon_pa_de440_200625.bpc, moon_de440_250416.tf, and DE421 lunar frame files | Unchanged; `lock.json` hash equals the baseline. |
| Lunar GM | NAIF generic kernel `gm_de440.tpc` (https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/gm_de440.tpc), 12,406 bytes, server Last-Modified 14 Dec 2022, SHA-256 `924ddf4fb9ead9fe8a1aa55780bcabde40b09d00065d58226e24b68d8092f140` | Downloaded to `E:\Temp\LUNA-OPS\downloads\naif\`, copied to `data/comms/` and recorded in `data/comms/manifest.json`. `BODY301_GM = ( 4.9028001184575496D+03 )` is parsed as text, never furnished into the SPICE pool. The file's sources section cites DE440 (Park, Folkner, Williams and Boggs 2021, AJ 161:105, doi:10.3847/1538-3881/abd414). |

## NASA references (concepts and scope, not data)
- **Lunar Surface Propagation,** NASA Glenn Research Center: https://www.nasa.gov/glenn/glenn-expertise-space-exploration/scan/lunar-surface-propagation/. It covers reflection, diffraction and multipath near the lunar surface, which **are not modelled** here. This simulation is geometric line of sight plus a free-space link budget.
- **Delay/Disruption Tolerant Networking,** NASA: https://www.nasa.gov/communicating-with-missions/delay-disruption-tolerant-networking/. Only the store-and-forward *concept* inspired the planner; no DTN protocol is implemented, and no LunaNet compatibility is claimed.
- **NAIF generic kernels:** the GM file above.

## Scenarios in this evidence (illustrative; `scripts/real_examples.py`, `scripts/comms_preview_body.mjs`)
**RF parameters are illustrative demonstration values, not hardware specifications.** Each set is tagged "illustrative" in its request.

| Set | Pt | Gt | Ltx | Gr | Lrx | Lother | Ts | f | Rb | Req. Eb/N0 | B |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Direct to Earth | 20 W | 20 dBi | 1 dB | 60 dBi | 1 dB | 3 dB | 50 K | 8450 MHz | 1 Mbit/s | 2.5 dB | 2 MHz |
| Lander → relay | 5 W | 3 dBi | 1 dB | 20 dBi | 1 dB | 2 dB | 400 K | 2250 MHz | 1 Mbit/s | 2.5 dB | – |
| Relay → Earth | 50 W | 30 dBi | 1 dB | 60 dBi | 1 dB | 3 dB | 50 K | 8450 MHz | 1 Mbit/s | 2.5 dB | – |

**Hypothetical relay orbits** were chosen for illustration and resemble no specific mission; the epoch is the analysis window start.

| Name | a [km] | e | i [°] | RAAN [°] | ω [°] | M0 [°] | Frame | Step | Notes |
|---|---|---|---|---|---|---|---|---|---|
| H1 | 6000 | 0.6 | 60 | 0 | 90 | 0 | LME_EPOCH | 60 s | period 11.58 h; periapsis 663 km over the lunar north, apoapsis 7863 km over the lunar south |
| H2 | 1837.4 | 0 | 90 | 0 | 0 | 0 | LME_EPOCH | 30 s | 100 km circular lunar-polar orbit, period 1.96 h |
| H3 | as H2 | | | | | | **J2000** | 30 s | frame demonstration: polar to the Earth's equator, about 24° from lunar-polar |

**Store-and-forward input:** 20,000 Mbit at 1,000 kbit/s over "any path meeting its link budget".
