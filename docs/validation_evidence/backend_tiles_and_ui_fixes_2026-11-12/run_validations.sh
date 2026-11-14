#!/usr/bin/env bash
# Re-run every external validation on the new code fingerprint (lunaops/api/tiles.py changed), with the same commands
# and parameters as the accepted runs (refresh_v04_v05_v13_v14_2026-11-11, v09_v10/v11/v12_final_2026-11-10).
# Run from backend/. Each step logs its command, start/end time, wall time and exit code. Nothing is merged here.
set -u
EV=../docs/validation_evidence/backend_tiles_and_ui_fixes_2026-11-12/validation
REF=../data/reference_validation
mkdir -p "$EV/v04_horizons/horizons_raw" "$EV/logs"
export TEMP='E:\Temp\LUNA-OPS' TMP='E:\Temp\LUNA-OPS' PYTHONUTF8=1
PY=./.venv/Scripts/python.exe
step() {
  local name="$1"; shift
  local log="$EV/logs/$name.log" s=$(date +%s)
  echo "# $* (start $(date -u +%Y-%m-%dT%H:%M:%SZ); code fingerprint $($PY -c 'from lunaops.fingerprint import code_fingerprint; print(code_fingerprint())'))" > "$log"
  "$@" >> "$log" 2>&1; local rc=$?
  echo "# exit $rc; wall time $(( $(date +%s) - s )) s (end $(date -u +%Y-%m-%dT%H:%M:%SZ))" >> "$log"
  echo "$name exit $rc ($(( $(date +%s) - s )) s)"
}
step v13_eclipse $PY -m validation.v13_eclipse --reference validation/reference/gsfc_lunar_eclipses_2025_2026.json --out "$EV/v13.json"
step v04_horizons $PY -m validation.horizons_compare --out "$EV/v04_horizons/horizons.json" --raw-dir "$EV/v04_horizons/horizons_raw"
step v14_month $PY -m validation.v14_month --out "$EV/v14.json"
step v11_psr $PY -m validation.v11_psr --lpsr "$REF/LPSR_80S_20MPP_ADJ.TIF" --out "$EV/v11.json"
step v12_lroc $PY -m validation.v12_lroc --twi-img "$REF/WAC_POLE_ILL_TWI_SOUTH_100M.IMG" --pct-img "$REF/WAC_POLE_ILL_PCT_SOUTH_100M.IMG" --avgvisib-img "$REF/AVGVISIB_85S_060M_201608.IMG" --out "$EV/v12.json"
step v09_v10_avgvisib $PY -m validation.v09_v10_avgvisib --sun-img "$REF/AVGVISIB_85S_060M_201608.IMG" --earth-img "$REF/AVGVISIB_85S_060M_201608_EARTH.IMG" --out "$EV/v09_v10.json"
echo "all validation steps finished"
