#!/usr/bin/env bash
# LUNA-OPS 2.0 Phase 1: every live browser check, one at a time (memory), against the running app. Run from frontend/.
set -u
EV=../docs/validation_evidence/luna_ops_2_phase1_2026-11-13
B=${1:-http://127.0.0.1:8000}
n=10
for c in shell mission viz explorer globe globe-target map e2e; do
  log="$EV/logs/${n}_${c}_live_check.log"
  (node scripts/$c-live-check.mjs --base "$B" --out "$EV/checks/${c}"; echo "exit $?") > "$log" 2>&1
  echo "$c: $(grep -h 'checks passed' "$log" | tail -1) [$(tail -n 1 "$log")]"
  n=$((n + 1))
done
