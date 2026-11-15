# Phase 5 polish verification

Verified locally on 2026-11-15 against API 1.5.0. This checkpoint improves the interface and verifies browser behavior; it does not certify all-sky coverage, astrophysical variability, or the historical revision-3 measurements. The five saved datasets remain unchanged.

## What changed

The workspace uses a consistent sans-serif hierarchy, selective tabular numbers, quieter slate surfaces and a shared epoch palette. The comparison controls, explicit recovery actions and successful-field history remain accessible on narrow screens. History is collapsed by default, can be reopened deliberately, and can be cleared. `/` opens coordinate search.

Spectrum geometry follows its actual rendered width through `ResizeObserver`. Axes and tooltips remain **13 CSS pixels** at 320px and 390px viewport widths instead of scaling down a desktop SVG. Narrow plots stagger detector labels; optional molecular references use numbered markers with a complete textual key. Reference wavelengths remain off by default and are not identified as detections. The sticky drawer header now covers the entire scrollport without leaking scrolled text above it.

Selected samples retain a crosshair and their recorded measurement details. Table-only filters select eligible, finite excluded or unavailable samples, and an epoch; sorting supports wavelength and signed flux, with unavailable values last. The table states both the shown and total counts. Filtering never changes the chart, eligibility flags or complete CSV export. “Copy sample metadata” preserves actual values, units, reasons and identifiers, and explicitly reports unavailable extraction coordinates rather than substituting the query center. Clipboard denial produces a useful failure message. Small finite values use significant digits/scientific notation rather than rounding to a false zero.

Signed flux, complete approximate error bounds, sparse unconnected points, excluded measurements, all-null states and lineage remain intact. A real single-epoch result cannot blink; unavailable observation B is disabled and labeled. Partial-download recovery retries the same archive query and never silently switches to saved observations. A smaller-field suggestion is limited to the specific bounded wavelength-match reason; it is not presented as a remedy for incomplete downloads. Exported selected-epoch reports preserve the full spectrum's epoch-color identities.

## Automated browser evidence

Browsers: Chromium **159.0.8154.6**, Firefox **159.0**, WebKit **27.2**. Each matrix used desktop **1440×1000**, mobile **390×844**, and narrow mobile **320×844** CSS viewports. Headless desktop engines emulate those viewport sizes; these are not physical-phone tests.

| Check group | Result | Data and measured behavior |
|---|---|---|
| Core interface and accessibility | **9/9 passed** | Real saved WISE API products. Paused startup; no page overflow; dialog focus containment, Escape and focus restoration; coordinate validation; distinct A/B selection and paired canvas; keyboard/touch spectrum selection; reduced-motion playback disabled. Actual SVG text measured at 13 CSS px with approximately 1:1 SVG/CSS geometry. Table filters/counts and signed sorting checked. |
| Single-epoch recovery and history | **9/9 passed** | Unchanged retained real WISE response with `PARTIAL_DOWNLOAD_NO_MATCHED_PAIR`. Playback disabled, reason explained, B explicitly unavailable, identical archive request on Retry, no automatic saved fallback or inappropriate smaller-field suggestion. Successful-field history explicitly reopened and cleared. |
| Newly retrieved matched pair | **9/9 passed** | Exact fresh Barnard's Star `matched_image_comparison/12` API response, replayed locally with its actual immutable assets. Play/Pause, distinct A/B options, side-by-side and Difference enabled. The two A/B asset byte hashes differ. |
| Spectrum geometry and export | **9/9 passed** | Real saved Epsilon Indi B: 246 recorded channels, 245 finite, one negative flux. No connecting SVG path. Tooltips fit inside the SVG and remain 13 CSS px. Filtering to its one unavailable channel still exports all **246** data rows. Chromium clipboard round-trip verifies copied metadata; other engines exercise honest clipboard-unavailable handling. |
| Later-pair report export | **1/1 passed** | Real saved Epsilon Indi B, selected `2025_E2`/`2026_E1`. PNG and Markdown download successfully. Instrumented canvas swatches retain original full-spectrum colors `#a4c6ee` and `#d2b5e2`, rather than restarting the palette after filtering. |
| Final partial-discovery response | **1/1 passed** | Exact fresh Epsilon Indi B response at 390px in Chromium: one epoch, three unavailable collections, null comparison reason. The interface explains “Archive search incomplete”, disables blinking, and retries the same archive query without an automatic fallback or inappropriate smaller-field suggestion. |

The core matrix ran **36 axe scans** across Observe, invalid coordinate Search, Spectrum and Help. They reported **zero violations at all severities**. Axe still marked some color-contrast and `aria-prohibited-attr` checks incomplete; zero automated violations is not comprehensive accessibility certification. Later targeted checks covered the narrow header/label fixes, collapsed history, unavailable B, clipboard success and report-color preservation.

Final frontend build and real-data packaging gates passed. The final output is `index-BtPqlhFi.js` and `index-4_RUdz0T.css`. Type checking passed. Final integration reran `test:real-data`, `test:wcs`, `test:semantics` and `test:views`; all passed. TAN coordinates match Astropy at 1,458 points across 18 fields, including RA zero and both poles. The real-only distribution gate preserves all 288 approved saved-asset hashes. This follow-up does not repeat or extend the earlier performance measurements.

## Reproduction and provenance

QA scripts are in `frontend/qa/phase5/`:

- `browser-polish.mjs`: core 3-engine/3-viewport matrix and axe scans.
- `browser-polish-recovery.mjs`: unchanged retained real single-epoch response, history and exact-query retry.
- `browser-polish-matched.mjs`: unchanged fresh Barnard matched-pair response and real asset byte checks.
- `browser-polish-spectrum.mjs`: signed spectrum, tooltip geometry, clipboard and complete CSV.
- `browser-polish-export.mjs`: later-pair PNG/Markdown and epoch-color identity.
- `browser-polish-partial.mjs`: exact final real Epsilon Indi B partial-discovery result with a null comparison reason.
- `browser-polish-captures.mjs`: final actual-saved-data screenshots and source hashes.

These scripts use the ignored Playwright/axe tool installation under `backend/.cache/phase5/browser-tools`, the owned local UI/API on ports 5176/8176, and, for the matched-pair run only, actual assets served by the backend verification process on 8185. Pre-existing servers on 5173/8000 were not changed. Replaying API bodies is isolated QA routing, not a shipped fixture or a new archive acquisition.

Detailed local outputs are under `backend/.cache/phase5-polish/{browser-matrix,recovery,matched,spectrum,export,partial}`. Retained-response inputs and SHA-256 hashes appear in the recovery/matched/partial result files. The matched input is `backend/.cache/phase5/comparison-first/evidence/barnards_star-response.json`; the final partial input is `backend/.cache/phase5/comparison-first/evidence/final/eps_indi_b-response.json`. Their upstream retrieval was performed separately by the backend investigation. Browser tests did not repeat those retrievals. Early test attempts are retained separately; corrected exact-label, Firefox option-text and test-file encoding assertions do not replace observation data.

Eight final screenshots and their SHA-256 hashes, URLs, viewport dimensions, real source-file hashes, frontend source hashes and API version are in [the screenshot origins manifest](../screenshots/polish/origins.json). These are documentation artifacts, not runtime observations:

- [Desktop workspace](../screenshots/polish/workspace-desktop.png) and [paired comparison](../screenshots/polish/comparison-desktop.png).
- [390px workspace](../screenshots/polish/workspace-mobile-390.png) and [320px workspace](../screenshots/polish/workspace-mobile-320.png).
- [390px spectrum](../screenshots/polish/spectrum-mobile-390.png) and [320px spectrum](../screenshots/polish/spectrum-mobile-320.png).
- [Signed Epsilon Indi B spectrum](../screenshots/polish/spectrum-signed.png) and [all-unavailable R Draconis spectrum](../screenshots/polish/spectrum-unavailable.png).

The mobile spectrum images intentionally show a scrolled drawer. Content remains available by scrolling; the screenshots do not imply that all metadata and the full chart fit on one phone screen simultaneously.

## Limits

No human user study, screen-reader evaluation, physical-device test, native-browser 400% zoom certification, or complete photosensitive-flash analysis was performed in this follow-up. The inherited reduced-motion and paused-start protections were exercised. The latest all-target upstream retrieval results belong to the separate backend acceptance record; the successful Barnard browser replay alone does not establish reliable archive comparison for every target or coordinate. Saved spectra retain their historical eligibility and coordinate semantics.
