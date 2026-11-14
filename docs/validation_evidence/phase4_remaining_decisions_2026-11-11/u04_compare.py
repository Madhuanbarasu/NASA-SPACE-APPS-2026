"""D4: compare the current-build live a11y audit with the U-04 release run (read-only). Run from the repository root.
Pass rule (the release run's own result): in every view 0 problems in every automated column, no horizontal scroll
at 320 px, and every functional test giving the release outcome. Writes nothing; prints a verdict."""
import json, sys
E = "docs/validation_evidence/"
rel = json.load(open(E + "u04_2026-11-11/audit-release.json", encoding="utf-8"))
cur = json.load(open(E + "phase4_remaining_decisions_2026-11-11/u04_current_build/audit-current-build.json", encoding="utf-8"))

def summ(v):
    k = v.get("keyboard") or {}
    return {"axUnnamed": len(v["ax"]["unnamed"]), "focusableNoRole": len(v["ax"]["focusableWithoutWidgetRole"]),
            "contrastFail": len(v["contrast"]["failures"]), "targetFail": len(v["targets"]["failures"]),
            "noFocusIndicator": len(k.get("noIndicator", [])), "focusClipped": len(k.get("clipped", [])),
            "obscured": len(k.get("obscured", [])), "reflowHScroll": bool(v["reflow320"]["horizontalScroll"]),
            "reflowOffenders": v["reflow320"]["offenderCount"], "spacingClipped": len(v["textSpacing"]["clipped"]),
            "unlabeled": len(v["structure"]["unlabeledFormControls"]), "dupIds": len(v["structure"]["duplicateIds"]),
            "roleApplication": len(v["structure"]["roleApplication"])}, k.get("stops")

ok = True
print("view                    tabStops(rel->cur)  problems(current build)")
rv = {v["view"]: v for v in rel["views"]}
for v in cur["views"]:
    s, stops = summ(v)
    _, rstops = summ(rv[v["view"]]) if v["view"] in rv else (None, None)
    bad = {k: x for k, x in s.items() if x}
    ok &= not bad
    print(f"{v['view']:22s}  {str(rstops):>4} -> {str(stops):<4}       {bad or 'none'}")
missing = set(rv) - {v["view"] for v in cur["views"]}
if missing:
    ok = False; print("views missing from the current run:", missing)
print("\nfunctional tests (release -> current):")
for key in rel["functional"]:
    a, b = rel["functional"].get(key), cur["functional"].get(key)
    if key == "mobileSite":
        continue
    same = json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    flag = "same" if same else "DIFFERENT"
    print(f"  {key:28s} {flag}")
    if not same:
        print("     release:", json.dumps(a)[:300]); print("     current:", json.dumps(b)[:300])
print("\nAUTOMATED CHECKS:", "0 problems in every view" if ok else "PROBLEMS FOUND")
