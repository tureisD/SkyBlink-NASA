# Phase 5 interface verification

This is the first Phase 5 implementation checkpoint. The subsequent visual,
chart, recovery and live-comparison work is documented in
[Phase 5 polish verification](phase5-polish-verification.md) and
[the comparison retrieval decision](../decisions/comparison-retrieval-decision.md).
The measurements below remain historical evidence for their recorded sources.

The observing workspace and spectrum inspector are implemented. Automated checks passed in **Chromium, Firefox and WebKit at 1440, 390 and 320 CSS pixels**. This establishes the tested behavior below; it is not a human usability study, screen-reader audit, flash-safety certification, public deployment test or scientific certification of the observations.

The application remains API **1.5.0**. Real saved observations were requested explicitly from a local FastAPI service. Additional isolated UI checks replayed retained real Phase 4 archive products through the current response serializers. No new observation discovery or cutout acquisition was performed, no science values were invented, and the five revision-3 datasets were not changed. Reading `/health` for screenshot version metadata did issue the endpoint's small IRSA availability probe; this was not an observation retrieval.

## Delivered behavior

- Observe, Compare, Spectrum and Evidence separate ordinary inspection from deeper interpretation. Entry and restored links start paused; search, cancellation and explicit saved recovery remain available during request failures.
- Compare exposes A/B observation selection, actual recorded dates or explicitly labeled historical mean dates, manual inspection, shared-camera side-by-side views and the recorded subtraction order. A bounded unmatched single epoch cannot enable temporal comparison.
- Source origin, comparison status, measurement availability and validation scope are presented separately. Real origin and reproducible arithmetic are not presented as proof of variability.
- The spectrum uses a signed linear flux domain containing every finite value and both approximate error endpoints. Samples have no connecting line. Missing flux is never plotted as zero, and missing uncertainty is not displayed as a zero error bar.
- Molecular references start off and are explicitly reference positions, not detections. Recorded eligible, finite excluded and unavailable counts remain distinct. Historical eligibility flags are retained rather than silently replaced with current policy.
- Pointer/touch selection, plot arrow/Home/End keys, previous/next controls and table Inspect buttons expose persistent signed values, errors, reasons, clean fraction, flags, extraction position, input identity and analysis links where recorded. All-null data produces an explicit unavailable state without an empty successful chart; table and metadata export remain available.
- Modal focus is contained, the application beneath is inert, Escape closes the dialog and focus returns to its opener. Reduced motion disables playback. Touch scrolling remains available; technical detail and advanced controls are progressively disclosed.

The [observing guide](../guides/observing-guide.md) describes these flows. Details of the source/eligibility policy remain in [Phase 4 online verification](phase4-online-verification.md); the failed primary refinement study remains in [the scientific report](phase4-science-online-verification.md).

## Browser matrix

Tests used Playwright-managed engines on Windows, a local Vite development server at port 5176 and local FastAPI at port 8176. These were verification processes, not a deployed or newly tested container. The browsers are the installed test-engine versions recorded by their runtime APIs.

| Engine | Runtime version | 1440×1000 | 390×844 | 320×844 |
|---|---|---|---|---|
| Chromium | 159.0.8154.6 | Pass | Pass | Pass |
| Firefox | 159.0 | Pass | Pass | Pass |
| WebKit | 27.2 | Pass | Pass | Pass |

Every case checked paused entry, no document-wide horizontal overflow, search validation, modal inertness, immediate Shift+Tab and forward Tab containment, Escape and opener focus restoration, distinct A/B selection, two rendered side-by-side canvases, spectrum keyboard selection, off-default reference guides, Help and reduced-motion playback suppression. Narrow cases also cleared selection and selected an actual plotted sample with touch. No JavaScript page errors occurred. The 46 sampled enabled core buttons had a minimum measured dimension of 44 CSS pixels in these runs; this is not a claim that every element in every expanded state was measured.

The first matrix caught a real WebKit defect: mouse activation did not focus the Search opener, so restoration returned to the wrong element. Explicit trigger focus immediately before its click handler fixed it. The complete nine-case matrix was repeated successfully. Original failed results and screenshots remain in ignored `backend/.cache/phase5/browser-matrix-before-focus-fix/`, including the unsuccessful earlier pointerdown approach. Final results are in `backend/.cache/phase5/browser-matrix/results.json`.

After the full matrix, a narrow final check confirmed that a Difference view retains **both A/B dates when switching to Evidence**, and that the remaining technical search/switch labels use 14px type; the technical search control has a 44px minimum height. Final screenshot review also raised the important no-eligible-spectrum banner from inherited 10px to 14px type. All documentation screenshots were recaptured after that fix. These final caption/typography changes did not trigger another full matrix. The targeted measured output is `browser-matrix/final-targeted-checks.json`.

## Accessibility and display limits

**36 axe-core scans reported zero violations** across Observe, invalid-coordinate Search, Spectrum and Help in the nine browser/viewport cases. Axe also returned incomplete checks, principally contrast on complex/SVG/image content and an SVG ARIA check requiring review. Zero reported violations therefore does not establish complete WCAG conformance.

A separate calculation using actual computed colors and alpha-composited backgrounds measured 49 enabled button/select text combinations: the lowest sampled contrast ratio was **7.87:1**. This does not measure text over every sky image, every graph mark or every expanded state. Chart meaning also uses shape and text rather than color alone.

A **320×256 CSS viewport**, equivalent in layout space to a 1280×1024 viewport at 400% zoom, retained a 320px document width and reachable modal actions through scrolling. This is a reflow-equivalent test, **not native browser zoom or OS magnification testing**. The table intentionally has its own horizontal scroll area.

Unperformed checks remain explicit: human novice/expert task sessions, assistive-technology/screen-reader testing, physical mobile hardware, native 400% browser zoom, formal flash-threshold analysis, vestibular comfort and an independent visual-accessibility audit. Paused entry, manual steps, side-by-side views, reduced-motion behavior and an eight-FPS ceiling do not constitute photosensitivity safety certification.

## Measurement and real-data cases

`browser-spectrum.mjs` checked actual saved API responses:

| Saved target | Recorded channels | Finite fluxes | Specific check |
|---|---:|---:|---|
| WISE 0855 | 164 | 162 | All uncertainty endpoints fit the domain; lower bounds below zero remain visible |
| Epsilon Indi B | 246 | 245 | One actual negative flux is retained; no connecting paths |
| R Draconis | 240 | 0 | Explicit no-usable state, no flux plot, selectable metadata rows and metadata CSV action |

Reference guides start absent and toggle explicitly. Keyboard Home/End selects recorded samples. These checks use the unchanged observations, not newly generated positive/negative test values.

For current lineage and exclusion semantics, `browser-retained.py` serialized actual retained Phase 4 products through `_build_response` and `_build_spectrum_response`, without calling discovery or acquisition. `browser-retained.mjs` then intercepted only the isolated test page's API responses with those exact serialized bodies. This is a **retained-data UI playback test**, not evidence of a new archive retrieval or production cache fallback.

| Retained archive target | Sky epochs | Channels | Finite | Recorded eligible | Result |
|---|---:|---:|---:|---:|---|
| Epsilon Indi B | 2 | 16 | 8 | 0 | Finite excluded values, reasons, input identity and record link remain inspectable |
| R Draconis | 2 | 18 | 0 | 0 | All-null current product displays its explicit unavailable state |
| WISE 0855 | 1 | 18 | 18 | 17 | Single-epoch playback disabled; current measurement eligibility and lineage displayed |

All three analysis links returned HTTP 200 from the local retained-asset service. The input paths and SHA256 values are recorded in `backend/.cache/phase5/browser-retained-data/sources.json`. Current partial-discovery wording was not independently browser-tested with an actual partial-discovery response in this phase; no partial scientific payload was fabricated to fill that gap.

## Failure, cancellation and stale responses

`browser-requests.mjs` passed in all three engines. It deliberately aborted transport for the archive-failure scenario and delayed **unchanged actual saved-response bytes** for timing scenarios. These are isolated network-state tests, not synthetic observations or upstream-availability measurements.

The checks established that an archive failure retains navigation and the archive source selection, never silently loads saved data, and allows explicit saved recovery; cancellation rejects late completion; Retry works; late WISE completion cannot replace a newly selected Epsilon Indi field; and spectrum cancellation/retry does not reveal a stale response. Exact delayed-body hashes are retained in the results. Browser cancellation does not claim to cancel already-running shared server work.

## Local performance observations

The separate Chromium observation used an Intel Core i5-10210U machine, Windows, local saved data, an unthrottled connection and the Vite development build. Initial load plus observed frame readiness took **923 ms** in that run. The nine matrix runs ranged from 776 to 3749 ms across engines. These are local observations, not release budgets or live-archive latency claims.

After 20 band switches and 20 manual observation steps, the same canvas element remained mounted. Instrumented bitmap counts stayed at 47 created/4 closed before and after those operations: the current predecoded pool was reused. After leaving the field, all 47 were closed. JavaScript heap after forced GC changed from 5,217,036 to 6,026,712 bytes. This short check does not prove absence of leaks and excludes GPU/process memory, long sessions and slower devices.

The detailed measurements, computed contrast samples and reflow screenshot are in `backend/.cache/phase5/browser-performance/`.

## Screenshots and reproduction

Approved documentation images are real explicit-saved views with **no response interception**:

- [Desktop workspace](../screenshots/phase5/workspace-desktop.png)
- [390px workspace](../screenshots/phase5/workspace-mobile-390.png)
- [320px workspace](../screenshots/phase5/workspace-mobile-320.png)
- [A/B comparison](../screenshots/phase5/comparison-desktop.png)
- [Signed spectrum](../screenshots/phase5/spectrum-signed.png)
- [Unavailable spectrum](../screenshots/phase5/spectrum-unavailable.png)

[The origins manifest](../screenshots/phase5/origins.json) records each screenshot hash, exact URL, viewport, source manifest/spectrum hashes, API/browser versions and relevant frontend source hashes. Baseline and intermediate captures remain in ignored research storage. No screenshot is shipped as an observation or runtime public asset.

Browser scripts are under `frontend/qa/phase5/browser-*.mjs`; the serializer helper is `browser-retained.py`. QA-only Playwright/axe packages were installed into ignored `backend/.cache/phase5/browser-tools`, without changing product dependencies. Start the local API on 8176 and a Vite server on 5176 with `/api` proxied to it, then run the scripts from repository root. Final captures are generated by `browser-final-captures.mjs`. Retained playback additionally needs the real Phase 4 cache files named by its source manifest; if those are absent, report that check unavailable rather than substitute generated data.

The existing semantics test also passed after the changes to recorded eligibility/counts. The Orchestrator coordinates full frontend build, shared-view/export tests and packaging verification. This report claims the checks actually performed here and leaves human comprehension and Phase 6 release/deployment verification open.
