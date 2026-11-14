"""Read-only projection: which labels the engine's own rule (provenance.compute_labels) would give if decisions
changed the official report's statuses. Hypothetical, in memory; report.json is only read. Run from backend/."""
import copy, json, sys
sys.path.insert(0, ".")
import validation  # noqa: F401
from lunaops.engine.provenance import compute_labels, label_blockers
from lunaops.engine.horizon import l_corr_label
rep = json.load(open("validation/report.json"))
print("report-level blockers:", label_blockers(rep))
cases = [("current report", {}),
         ("D4 only: U-04 passed", {"U-04": "passed"}),
         ("D3 + D4: U-04, U-06 passed", {"U-04": "passed", "U-06": "passed"}),
         ("D1 merged + D3 + D4", {"U-04": "passed", "U-06": "passed", "V-05": "passed"}),
         ("D1 + D2 (both pass) + D3 + D4", {"U-04": "passed", "U-06": "passed", "V-05": "passed", "V-09": "passed", "V-10": "passed"}),
         ("D1 + D2 (V-09 failed, V-10 passed) + D3 + D4", {"U-04": "passed", "U-06": "passed", "V-05": "passed", "V-09": "failed", "V-10": "passed"})]
for name, upd in cases:
    t = copy.deepcopy(rep["tests"])
    for k, v in upd.items():
        t[k] = {"status": v}
    a = compute_labels(t, [], False)
    b = compute_labels(t, [], False, l_corr_label())
    print(f"\n{name}")
    for q in a:
        print(f"   {q:16s} status page: {a[q]['validation']:20s} analysis result with horizon sigma (L_corr): {b[q]['validation']}")
