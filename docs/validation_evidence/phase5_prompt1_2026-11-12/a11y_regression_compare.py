"""Compare the Phase 5 live a11y audit (existing features) with the U-04 release run. Read-only; run from the repo root.
Expected difference: the welcome view gains two Tab stops (the new map/globe switch buttons). Everything else must match."""
import json
E = "docs/validation_evidence/"
rel = json.load(open(E + "u04_2026-11-11/audit-release.json", encoding="utf-8"))
cur = json.load(open(E + "phase5_prompt1_2026-11-12/a11y_regression/audit-phase5.json", encoding="utf-8"))
def summ(v):
    k = v.get("keyboard") or {}
    c = {"axUnnamed": len(v["ax"]["unnamed"]), "focusableNoRole": len(v["ax"]["focusableWithoutWidgetRole"]),
         "contrastFail": len(v["contrast"]["failures"]), "targetFail": len(v["targets"]["failures"]),
         "noFocusIndicator": len(k.get("noIndicator", [])), "focusClipped": len(k.get("clipped", [])), "obscured": len(k.get("obscured", [])),
         "reflowHScroll": int(bool(v["reflow320"]["horizontalScroll"])), "reflowOffenders": v["reflow320"]["offenderCount"],
         "spacingClipped": len(v["textSpacing"]["clipped"]), "unlabeled": len(v["structure"]["unlabeledFormControls"]),
         "dupIds": len(v["structure"]["duplicateIds"]), "roleApplication": len(v["structure"]["roleApplication"])}
    return c, k.get("stops")
ok = True
rv = {v["view"]: v for v in rel["views"]}
print("view                    tabStops(release -> phase5)  problems")
for v in cur["views"]:
    c, stops = summ(v); _, rs = summ(rv[v["view"]])
    bad = {k: x for k, x in c.items() if x}
    expected_stops = (rs + 2) if v["view"] == "site-welcome" else rs
    ok &= not bad and stops == expected_stops
    print(f"{v['view']:22s}  {str(rs):>4} -> {str(stops):<4} (expected {expected_stops})  {bad or 'none'}")
print("functional tests (release -> phase5):")
def panorama_equivalent(r, p):
    """The slider's start azimuth comes from the audit's preceding mouse-hover position, so compare behaviour instead:
    same role and readout, same step sizes (Arrow +1, Page Up +10), and identical horizon text wherever both runs read
    the same azimuth."""
    seq = ("onFocus", "afterArrowRight", "afterPageUp")
    steps = lambda f: [int(f[b]["now"]) - int(f[a]["now"]) for a, b in zip(seq, seq[1:])]
    texts = {}
    for f in (r, p):
        for k in seq: texts.setdefault(f[k]["now"], set()).add(f[k]["text"])
    return (all(r[k]["role"] == p[k]["role"] == "slider" and r[k]["visibleReadout"] == p[k]["visibleReadout"] for k in seq)
            and steps(r) == steps(p) and all(len(v) == 1 for v in texts.values()) and p["afterBlur"] == r["afterBlur"])
for key, val in rel["functional"].items():
    if key == "mobileSite": continue
    same = json.dumps(cur["functional"].get(key), sort_keys=True) == json.dumps(val, sort_keys=True)
    if not same and key == "panoramaKeyboard" and panorama_equivalent(val, cur["functional"][key]):
        print(f"  {key:28s} equivalent (start azimuth differs by the hover position; same steps; identical horizon at shared azimuths)")
        continue
    ok &= same
    print(f"  {key:28s} {'same' if same else 'DIFFERENT'}")
    if not same: print("     release:", json.dumps(val)[:200]); print("     phase5: ", json.dumps(cur["functional"].get(key))[:200])
print("EXISTING FEATURES AND ACCESSIBILITY UNCHANGED" if ok else "DIFFERENCES FOUND")
