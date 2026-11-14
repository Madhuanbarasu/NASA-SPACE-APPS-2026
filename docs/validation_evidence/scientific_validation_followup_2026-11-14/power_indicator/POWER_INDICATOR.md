# Estimated power indicator: definition, units, assumptions and verification (2026-11-14)

**Status: Pending validation** (kind: Estimated).
- **What is verified:** the implementation, exactly, against its definition.
- **What is not:** its usefulness as a power estimate. There are no measurement data.

## Equation (`backend/lunaops/engine/power.py`)
**P_rel(t) = f_sun(t) × (1 au / r_sun(t))² × k(t)**

| Symbol | Meaning | Unit |
|---|---|---|
| f_sun | Visible fraction of the solar disk's area, after terrain and Earth occultation (uniform disk) | dimensionless, 0–1, NaN when unknown |
| r_sun | Sun–observer distance | km; 1 au = 149,597,870.7 km (IAU 2012) |
| k | Cosine of incidence on a named reference panel: **vertical, tracking the Sun in azimuth** cos(el) (default); **horizontal** max(0, sin el); **vertical, fixed azimuth** cos(el) · max(0, cos(az − az_panel)) | dimensionless |
| P_rel | Relative solar availability: 1.0 = whole Sun at 1 au at normal incidence | **dimensionless** |

**Window metrics** (`window_metrics`, policy `known-intervals-only/v1`):
- **Mean:** the mean over known time.
- **Equivalent full-Sun hours:** ∫P_rel dt / 3600 s. A lower bound when any time is unknown.
- **Coverage:** known time / window.

**Companion:** a limb-darkened indicator `P_rel_LD` (extension D01) is reported beside it.

**Assumptions:**
- the disk is uniform (except in `P_rel_LD`);
- no atmosphere;
- a flat, ideal panel;
- no shading other than terrain and Earth;
- the observer height as configured.

**Excluded by design:** efficiency, temperature, degradation, storage and electrical load. There are **no hardware parameters**, so none is defaulted.

## This is not electrical power
- **P_rel is not watts.** Multiplying it by the solar constant (about 1361 W/m² at 1 au) gives incident irradiance on the reference panel, in W/m², not electrical output.
- **No RF quantity is involved.** Transmit power, EIRP and the other RF quantities belong to the Communication link budget (`lunaops_comms`).

**Terminology recommendation (not applied: renaming UI text needs approval):**
- **Label:** use "Solar availability indicator (relative, dimensionless)" or "Relative solar exposure" instead of "Power indicator".
- **Units:** keep "no unit; 1 = full Sun at 1 au, face-on".
- **Full-Sun time:** rename "Equivalent full-Sun" to "Equivalent full-Sun hours (face-on, 1 au)".
- **Why:** the current "Power indicator" wording invites reading it as electrical power. The UI does label it "Estimated" and shows no watt unit (E2E-06).

## Verification
- **Series and metrics:** all stored series and window metrics were recomputed independently (`../../scientific_validation_investigation_2026-11-14/power_indicator/`, 240 series). They match within the storage rounding (9.6e-6), and unknown samples are placed identically. Re-run here under the new engine fingerprint: `power_independent_after.json`, `../logs/04_power_after.log`.
- **Edge cases:** 14/14 as defined:
  - f = 0 gives 0, and NaN stays NaN;
  - full Sun at 1 au, face-on, gives 1;
  - distance scaling;
  - the Sun below the horizontal on a horizontal panel gives 0;
  - the Sun behind a fixed panel gives 0;
  - all samples unknown gives mean None;
  - an isolated known sample adds no time;
  - an unknown panel model is refused.
- **Browser (E2E-06, E2E-07):** see `../reports/FOLLOWUP_REPORT.md`.
- **Effect of the event correction:** none on the indicator. It uses per-sample visibility (NaN where unknown), not intervals.
