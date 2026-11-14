#!/usr/bin/env bash
# Phase 7 Part H, run only after the external chain (no CPU contention): U-06 browser performance (3 profiles, Phase 5
# supplement), the D3 evaluation, then backend timings and server memory. Existing server on port 8000 (PID $1).
set -u
cd /e/LUNA-OPS
P=docs/validation_evidence/phase7_final_validation_2026-11-14
L=$P/logs
mkdir -p $P/performance/u06_perf/raw
export TEMP='E:\Temp\LUNA-OPS' TMP='E:\Temp\LUNA-OPS' PYTHONUTF8=1
n=30
for prof in native cpu4x cpu4x-net10mbps; do
  t0=$(date +%s)
  node frontend/scripts/perf-audit.mjs --base http://127.0.0.1:8000 --out $P/performance/u06_perf/raw --label final \
    --profile $prof --phase5 1 > $L/${n}_perf_${prof}.log 2>&1
  echo "U-06 $prof exit $? $(( $(date +%s) - t0 )) s" | tee -a $P/performance/progress.txt
  n=$((n+1))
done
(cd $P/performance && /e/LUNA-OPS/backend/.venv/Scripts/python.exe -I u06_evaluate.py > /e/LUNA-OPS/$L/33_u06_evaluate.log 2>&1)
echo "U-06 evaluate exit $?" | tee -a $P/performance/progress.txt
t0=$(date +%s)
backend/.venv/Scripts/python.exe -I $P/scripts/backend_perf.py $1 $P/performance/backend_perf.json > $L/34_backend_perf.log 2>&1
echo "backend perf exit $? $(( $(date +%s) - t0 )) s" | tee -a $P/performance/progress.txt
echo "post-chain done $(date -u +%H:%M:%SZ)" | tee -a $P/performance/progress.txt
