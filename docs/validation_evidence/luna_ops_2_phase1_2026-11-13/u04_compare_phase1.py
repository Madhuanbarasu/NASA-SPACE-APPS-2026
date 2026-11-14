"""LUNA-OPS 2.0 Phase 1 accessibility regression (rules of the Phase 5 final U-04 re-evaluation): compare the live audit of the final frontend with the U-04 release run and check
the Phase 5 views. Read-only; run from the repository root.

Release views (site-welcome, site-result-technical, site-result-public, compare-matrix, data, guide) must have 0 problems
in every automated column, the release tab-stop counts plus the documented Phase 5 additions, and the release functional
results, with these intentional differences:
  * tab stops: welcome +2 (prompt 1: map/globe/terrain switch); result view +3 (prompt 2: Back to the Moon explorer;
    prompt 3: the "How to read this result" disclosure and the intervals table toggle); the Mission tab adds none
    (the tab list is one tab stop);
  * panorama readout: the release text is kept and the bin's 1-sigma and near-field flag are appended.
Phase 5 views (site-explorer-globe, site-explorer-terrain, mission, mission-empty) have no release baseline: they must
have 0 problems in every automated column, a Tab walk that cycled (no trap), and the Phase 5 functional tests must pass
(keyboard operation of the globe and the terrain preview, the explorer's Return to the result, deep-link focus)."""
import json
import sys

E = "docs/validation_evidence/"
rel = json.load(open(E + "u04_2026-11-11/audit-release.json", encoding="utf-8"))
cur = json.load(open(E + "luna_ops_2_phase1_2026-11-13/u04_audit/audit-phase1.json", encoding="utf-8"))
p5 = json.load(open(E + "phase5_final_2026-11-12/u04_audit/audit-phase5final.json", encoding="utf-8"))
# Phase 5 additions as before, plus LUNA-OPS 2.0 Phase 1: one more stop in every view (the Mission Parameters toggle in
# the command bar; the compact menu button and the drawer close button are hidden on wide screens)
EXTRA_STOPS = {"site-welcome": 2 + 1, "site-result-technical": 3 + 1, "compare-matrix": 1, "data": 1, "guide": 1}
PHASE5_VIEWS = ["site-explorer-globe", "site-explorer-terrain", "mission", "mission-empty"]


def summ(v):
    k = v.get("keyboard") or {}
    c = {"axUnnamed": len(v["ax"]["unnamed"]), "focusableNoRole": len(v["ax"]["focusableWithoutWidgetRole"]),
         "contrastFail": len(v["contrast"]["failures"]), "targetFail": len(v["targets"]["failures"]),
         "noFocusIndicator": len(k.get("noIndicator", [])), "focusClipped": len(k.get("clipped", [])), "obscured": len(k.get("obscured", [])),
         "reflowHScroll": int(bool(v["reflow320"]["horizontalScroll"])), "reflowOffenders": v["reflow320"]["offenderCount"],
         "spacingClipped": len(v["textSpacing"]["clipped"]), "unlabeled": len(v["structure"]["unlabeledFormControls"]),
         "dupIds": len(v["structure"]["duplicateIds"]), "roleApplication": len(v["structure"]["roleApplication"])}
    return c, k.get("stops"), k.get("cycled")


def panorama_ok(r, p):
    seq = ("onFocus", "afterArrowRight", "afterPageUp")
    steps = lambda f: [int(f[b]["now"]) - int(f[a]["now"]) for a, b in zip(seq, seq[1:])]
    if steps(r) != steps(p) or p["afterBlur"] != r["afterBlur"]:
        return False
    if not all(p[k]["role"] == "slider" and p[k]["visibleReadout"] == r[k]["visibleReadout"] for k in seq):
        return False
    rel_text = {r[k]["now"]: r[k]["text"] for k in seq}
    return all(p[k]["text"].startswith(rel_text[p[k]["now"]]) for k in seq if p[k]["now"] in rel_text)


ok = True
rv = {v["view"]: v for v in rel["views"]}
cv = {v["view"]: v for v in cur["views"]}
print(f"browser: {cur.get('browserVersion')}")
print("RELEASE VIEWS            tabStops(release -> now)  problems")
for name in rv:
    if name not in cv:
        ok = False; print(f"{name:22s}  MISSING"); continue
    c, stops, _ = summ(cv[name])
    _, rs, _ = summ(rv[name])
    bad = {k: x for k, x in c.items() if x}
    exp = None if rs is None else rs + EXTRA_STOPS.get(name, 0)
    ok &= not bad and stops == exp
    print(f"{name:22s}  {str(rs):>4} -> {str(stops):<4} (expected {exp})  {bad or 'none'}")
print("PHASE 5 VIEWS            tabStops  cycled  problems")
for name in PHASE5_VIEWS:
    if name not in cv:
        ok = False; print(f"{name:22s}  MISSING"); continue
    c, stops, cyc = summ(cv[name])
    bad = {k: x for k, x in c.items() if x}
    p5stops = next((summ(v)[1] for v in p5["views"] if v["view"] == name), None)
    exp5 = None if p5stops is None else p5stops + 1
    ok &= not bad and bool(cyc) and stops == exp5
    print(f"{name:22s}  {str(stops):>8}  {str(cyc):6s}  (Phase 5 final {p5stops} + 1 = {exp5})  {bad or 'none'}")
print("RELEASE FUNCTIONAL TESTS (release -> now):")
for key, val in rel["functional"].items():
    if key == "mobileSite":
        continue
    now = cur["functional"].get(key)
    same = json.dumps(now, sort_keys=True) == json.dumps(val, sort_keys=True)
    if not same and key == "panoramaKeyboard" and panorama_ok(val, now):
        print(f"  {key:28s} equivalent (release readout kept; sigma/near-field appended: {now['onFocus']['text']!r})")
        continue
    ok &= same
    print(f"  {key:28s} {'same' if same else 'DIFFERENT'}")
    if not same:
        print("     release:", json.dumps(val)[:200]); print("     now:    ", json.dumps(now)[:200])
f = cur["functional"]
p5 = {
    "globeKeyboard (rotate, zoom: focused and view changed)": all(x["focused"] and x["changed"] for x in f.get("globeKeyboard", {}).values()) and len(f.get("globeKeyboard", {})) == 2,
    "terrainPreviewKeyboard (pan, rotate, zoom)": all(x["focused"] and x["changed"] for x in f.get("terrainPreviewKeyboard", {}).values()) and len(f.get("terrainPreviewKeyboard", {})) == 3,
    "returnToResult (explorer offers the kept result)": f.get("returnToResult") is True,
    "missionDeepLinkFocus (focus on the visibility section)": f.get("missionDeepLinkFocus") == "result-visibility",
}
print("PHASE 5 FUNCTIONAL TESTS:")
for k, v in p5.items():
    ok &= v
    print(f"  {k:58s} {'pass' if v else 'FAIL'}")
print("U-04 RE-EVALUATION: NO AUTOMATED PROBLEM IN ANY VIEW; RELEASE BEHAVIOUR KEPT (documented additions only)" if ok else "DIFFERENCES OR PROBLEMS FOUND")
sys.exit(0 if ok else 1)
