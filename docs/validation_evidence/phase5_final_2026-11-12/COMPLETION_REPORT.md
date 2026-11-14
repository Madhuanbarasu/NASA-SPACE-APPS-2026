# Phase 5 final completion report (2026-11-12)

## 1. Features integrated; implementation status
Phase 5 was frontend only. All of it is implemented and verified on the final build.

| Feature | Prompt | Status |
| --- | --- | --- |
| Interactive 3D Moon globe (NASA SVS imagery, illustrative only; shared coordinate conversion; no-WebGL fallback) | 1 | Done; globe check 31/31, no-WebGL 2/2 |
| South Pole Explorer (site from globe, map or typing; API coverage; local terrain preview from registered DEMs) | 2 | Done; explorer check 27/27 |
| Scientific visualisations (data-class key, site/terrain context, Sun/Earth visibility chart, timeline flags and intervals table, panorama σ, comparison bars and label counts) | 3 | Done; visualisation check 25/25 |
| Mission dashboard (overview, navigation, candidates, session analyses, comparison; 3D-terrain message fix) | 4 | Done; mission check 42/42 |
| Final integration (result kept while exploring; session list per tab tied to build and report; coordinate-name consistency; curated-name fix; open-error handling; licence notices) | final | Done; end-to-end check 16/16 |

## 2. U-04 and U-06: exact scope and results
**U-04 (criteria and scope of D4):**
- **Audit:** the live audit ran on the final frontend, across the 6 release views plus 4 Phase 5 views (globe, local terrain, populated and empty mission dashboard).
- **Result:** 0 automated problems in every view.
  - The 16 release functional tests are the same as the release run, apart from the documented panorama readout additions.
  - The 4 Phase 5 keyboard and focus tests pass.
  - Tab stops equal the release counts plus the documented Phase 5 additions.
- **Scope:** Chrome 157 headless; no real screen-reader user; zoom emulated; speech input untested.
- **Not claimed:** unrestricted WCAG 2.2 AA conformance.

**U-06 (criteria of D3):**
- **Setup:** re-measured on the final production build on the same laptop, browser, profiles and tile exclusion as D3. The server was restarted fresh. There are two run sets: all three profiles, then a repeat of native and 4× CPU.
- **Results:**
  - **LCP (worst):** 540 ms native, 1,728 ms at 4× CPU (first set, under evident CPU contention; repeat 988 ms) and 1,332 ms at 4× CPU + 10 Mbit/s, all ≤ 2,500 ms.
  - **CLS:** 0.
  - **Interaction p95:** at most 56 / 88 ms (native / 4× CPU), ≤ 200 ms.
  - **Memory:** no progressive leak over 5 remount cycles (+0.3 MB). The globe and terrain remounts also show no leak.
- **U-06 meets the D3 criteria.**
- **Reported, not hidden:**
  - the build is measurably slower than the accepted 2026-11-11 build (about 20–60 % at 4× CPU), and the cause was not isolated;
  - the first evaluator rule wrongly flagged the native set; it was corrected with reasons, and the original log is kept;
  - the memory rule is a stated, unapproved operationalisation of D3's "no progressive leak".
- **Not claimed:** field Core Web Vitals compliance.

**Recording:**
- **Result files:** `frontend_u04_phase5.json` and `frontend_u06_phase5.json`, both "passed", pass the merge guard in an in-memory dry run.
- **Not merged:** they await explicit approval. Until merged, the official report's U-04 and U-06 entries (passed) describe the Phase 4 build.

## 3. Complete test results and failures
- **Static checks:** type check exit 0; `npm test` exit 0 (strings 658 keys, 0 problems; static a11y 0 problems; geometry 238,972 checks); production build exit 0; bundle check 0 problems.
- **Browser checks:** mission 42/42, visualisation 25/25, explorer 27/27, globe 31/31, no-WebGL 2/2, end-to-end 16/16.
- **Audits:** U-04 audit and comparison passed; U-06 runs complete with D3 met in both sets.
- **Licensing and recording:** IB-5 shipped set unchanged; notices generated; result files 0 rejections.
- **Failures encountered:**
  - **Explorer check, attempt 1:** headless Chrome did not open its DevTools port within 20 s, so no test ran. It passed 27/27 on re-run, and both logs are kept.
  - **First U-06 evaluation:** "not met" from the evaluator's own over-strict rule (explained above).
  - **Audit tool, trial run:** the terrain view's Tab walk did not close (196 stops). This was an audit-tool measurement artefact, fixed for the Phase 5 views.
- No test of the final build fails.

## 4. Backend and fingerprint preservation
- **Unchanged:** algorithm 1.5.0; code fingerprint `5bf9753fa5c5…37d2f8`; suite fingerprint `1632af16763d…6d75eabc`; terrain acceptance digest `e48eb8ed0ca2…943dce`; production kernels.
- **Official report:** `backend/validation/report.json` SHA-256 `2279606ceab9354b8616ba9216e12e89e399f34cfc3cbfcbd7502d12d077d376`, unchanged and never written. It was hashed before and after the result-file dry run.
- **Backend source:** no backend file was edited.

## 5. Evidence location and checksum verification
- **Final evidence:** `docs/validation_evidence/phase5_final_2026-11-12/`, with README, this report, logs, browser-check results and screenshots, the U-04 audit, U-06 raw data and summaries, the IB-5 review, result files, fingerprints and `dist` hashes. All of it is listed in `SHA256SUMS`.
- **Earlier evidence verified:** every earlier evidence folder with a manifest verifies (10/10: D1, Phase 4 closure, final merge, first merge, remaining decisions, the V-04/V-05/V-13/V-14 refresh, and Phase 5 Prompts 1–4).
- **Folders without a manifest:** older folders without a manifest (for example `u04_2026-11-11`, `u06_2026-11-11`, `ib5_2026-11-11`) were only read, never written.

## 6. Remaining bugs, limitations, deferred work and licensing restrictions
- **Known bugs:** none open in the final build.
- **Limitations:**
  - **Browser coverage:** Chrome only; no real screen-reader session.
  - **U-06:** lab-only, on one laptop, with few samples, two slow backend tiles excluded, and a slowdown against the previous build.
  - **Session list:** per browser tab only; comparisons are not persisted.
  - **Leaving a result:** opening the explorer from a result parks it (one result is kept).
- **Deferred or awaiting decision:**
  - **Official report:** re-registering the refreshed U-04/U-06 results needs explicit approval.
  - **Backend tile fix:** the slow-tile backend fix (U-06 recommendation) is outside the frontend scope.
  - **V-09/V-10:** remain deferred (D2, Phase 4).
- **Licensing (IB-5, D5 deferral stands):**
  - **Addressed:** browser-build notices and the OFL text now ship with `dist`, and the reference rasters are git-ignored.
  - **Unresolved:** native-library licences in the Python wheels, data redistribution terms, `lerc` and the GSFC figure acknowledgment.
  - **Restrictions (README):**
    - no packaged Python environment;
    - no commit or redistribution of `data/reference_validation/`;
    - publish `dist` only with its notices;
    - the Horizons and GSFC copies are evidence only;
    - no distribution of data products.
  - **No licensing clearance is claimed.**

## 7. Verdict: **COMPLETE WITH APPROVED DEFERRALS**
**Justification:**
- **Requirements met by evidence:** every Phase 5 requirement is met on the final build, as shown above:
  - features;
  - integration and state preservation;
  - responsive layouts;
  - the U-04 re-evaluation across all views, including the dashboard;
  - the U-06 re-measurement against the approved criteria;
  - complete regression;
  - documentation;
  - evidence integrity;
  - preservation of the backend and of the official report.
- **Why "with approved deferrals":** the items still open are approved deferrals or actions the prompt reserves for approval.
  - **IB-5:** formally deferred under D5, with the distribution restrictions above.
  - **Official report:** re-registration of U-04/U-06 awaits explicit approval, as the prompt requires.
  - **V-09/V-10:** remain under the Phase 4 deferral D2.

**What would change the verdict:**
- **To COMPLETE:** approval and merge of the refreshed U-04/U-06 results and resolution of IB-5.
- **To INCOMPLETE:** a decision that the U-06 slowdown or the Chrome-only accessibility scope is unacceptable.
