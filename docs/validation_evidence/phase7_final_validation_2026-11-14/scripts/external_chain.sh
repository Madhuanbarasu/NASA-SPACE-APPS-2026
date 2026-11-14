#!/usr/bin/env bash
# Phase 7: external validations, one after another (memory), then the full pytest suite and the validation report.
# Run from backend/. Each step logs its command, start time, fingerprints, output and wall time.
set -u
P=../docs/validation_evidence/phase7_final_validation_2026-11-14
X=$P/engine_regression/external
mkdir -p "$X"
export PYTHONUTF8=1 TEMP='E:\Temp\LUNA-OPS' TMP='E:\Temp\LUNA-OPS'
PY=./.venv/Scripts/python.exe
FP=$($PY -c "import sys; sys.path.insert(0,'.'); from lunaops.fingerprint import code_fingerprint as c, suite_fingerprint as s; print(c(), s())")
step() {   # name, logfile, command...
  local name=$1 log=$2; shift 2
  local t0=$(date +%s)
  echo "# $* (start $(date -u +%Y-%m-%dT%H:%M:%SZ); fingerprints $FP)" > "$log"
  "$@" >> "$log" 2>&1
  local rc=$?
  echo "# exit $rc; wall time $(( $(date +%s) - t0 )) s (end $(date -u +%Y-%m-%dT%H:%M:%SZ))" >> "$log"
  echo "$name exit $rc $(( $(date +%s) - t0 )) s" >> "$X/chain_progress.txt"
}
: > "$X/chain_progress.txt"
R=../data/reference_validation
step "V-09/V-10 holdout" "$X/v09_v10_holdout.log" $PY -m validation.v09_v10_avgvisib \
  --sun-img $R/AVGVISIB_85S_060M_201608.IMG --earth-img $R/AVGVISIB_85S_060M_201608_EARTH.IMG \
  --use-points V-09=$P/V09_holdout/points_frozen.json --use-points V-10=$P/V10_holdout/points_frozen.json \
  --expect-sha256 V-09=792f7914ec66dfd0ef334c0a8b02cc39d5292bc0f0ab31afbdfcad3b71701923 \
  --expect-sha256 V-10=d3905078eddb2524906c4a4ab4b1990d6e330c73fe3d748e91cb496d95d4e680 \
  --out "$X/v09_v10_holdout.json"
step "V-13" "$X/v13.log" $PY -m validation.v13_eclipse --reference validation/reference/gsfc_lunar_eclipses_2025_2026.json --out "$X/v13.json"
step "V-14" "$X/v14.log" $PY -m validation.v14_month --out "$X/v14.json"
step "V-04/V-05" "$X/v04.log" $PY -m validation.horizons_compare --out "$X/horizons.json" --raw-dir "$X/horizons_raw"
step "V-11" "$X/v11.log" $PY -m validation.v11_psr --lpsr $R/LPSR_80S_20MPP_ADJ.TIF --out "$X/v11.json"
step "V-12" "$X/v12.log" $PY -m validation.v12_lroc --twi-img $R/WAC_POLE_ILL_TWI_SOUTH_100M.IMG \
  --pct-img $R/WAC_POLE_ILL_PCT_SOUTH_100M.IMG --avgvisib-img $R/AVGVISIB_85S_060M_201608.IMG --out "$X/v12.json"
echo "chain done $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$X/chain_progress.txt"
