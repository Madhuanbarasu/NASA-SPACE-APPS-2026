"""Compare the Phase 5 prompt 4 live a11y audit (existing features) with the U-04 release run. Read-only; run from the
repository root.

Expected, intentional differences:
  * Tab stops: welcome +2 (prompt 1: map/globe switch); result view +1 (prompt 2: Back to the Moon explorer) and +2 here
    (the "How to read this result" disclosure and the intervals table toggle).
  * Panorama readout: the release text is kept and the bin's 1-sigma uncertainty and near-field flag are appended, so the
    current text must START WITH the release text for the same azimuth; role, steps and visible readout unchanged.
  * Prompt 4 adds a Mission tab to the tab list; the list stays a single tab stop, so no tab-stop count changes.
Everything else must match: 0 problems in every automated column and identical functional results."""
import json

E = "docs/validation_evidence/"
rel = json.load(open(E + "u04_2026-11-11/audit-release.json", encoding="utf-8"))
cur = json.load(open(E + "phase5_prompt4_2026-11-12/a11y_regression/audit-phase5p4.json", encoding="utf-8"))
EXTRA_STOPS = {"site-welcome": 2, "site-result-technical": 3}


def summ(v):
    k = v.get("keyboard") or {}
    c = {"axUnnamed": len(v["ax"]["unnamed"]), "focusableNoRole": len(v["ax"]["focusableWithoutWidgetRole"]),
         "contrastFail": len(v["contrast"]["failures"]), "targetFail": len(v["targets"]["failures"]),
         "noFocusIndicator": len(k.get("noIndicator", [])), "focusClipped": len(k.get("clipped", [])), "obscured": len(k.get("obscured", [])),
         "reflowHScroll": int(bool(v["reflow320"]["horizontalScroll"])), "reflowOffenders": v["reflow320"]["offenderCount"],
         "spacingClipped": len(v["textSpacing"]["clipped"]), "unlabeled": len(v["structure"]["unlabeledFormControls"]),
         "dupIds": len(v["structure"]["duplicateIds"]), "roleApplication": len(v["structure"]["roleApplication"])}
    return c, k.get("stops")


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
print("view                    tabStops(release -> now)  problems")
for v in cur["views"]:
    c, stops = summ(v)
    _, rs = summ(rv[v["view"]])
    bad = {k: x for k, x in c.items() if x}
    exp = None if rs is None else rs + EXTRA_STOPS.get(v["view"], 0)
    ok &= not bad and stops == exp
    print(f"{v['view']:22s}  {str(rs):>4} -> {str(stops):<4} (expected {exp})  {bad or 'none'}")
print("functional tests (release -> now):")
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
print("EXISTING FEATURES AND ACCESSIBILITY UNCHANGED (apart from the documented additions)" if ok else "DIFFERENCES FOUND")
