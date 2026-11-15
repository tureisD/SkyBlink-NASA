# Centered observing workspace verification

This follow-up checks the image-centered workspace requested on 2026-11-15. It changes presentation and navigation, not observation data, scientific eligibility or API 1.5.0. Human usability and screen-reader acceptance remain separate from automated browser verification.

## Baseline

Before the layout change, actual saved WISE data produced these canvas-element bounds. Desktop height was 1080 CSS pixels; the phone viewport was 390×844. The element includes the image's display area and any letterboxing, not a new scientific footprint measurement.

| Viewport width | Canvas left | Canvas top | Canvas width | Canvas height | Horizontal center relative to viewport center |
|---:|---:|---:|---:|---:|---:|
| 1440 | 37 | 545.55 | 1036 | 538 | −165 px |
| 1920 | 177 | 545.55 | 1236 | 538 | −165 px |
| 390 | 17 | 1041.73 | 356 | 348 | 0 px |

The phone image started below the first screen. Before screenshots and frontend source hashes are retained locally under `backend/.cache/phase5-centered/before/`; the previous published [polish screenshots](../screenshots/polish/origins.json) remain unchanged.

## Resulting workspace

Wide desktops place field/source navigation on the left, the persistent image and observation controls in the center, and the evidence/display inspector on the right. Each sidebar can be closed independently. Focus mode hides both without remounting the canvas, while retaining source and comparison limitations. Closing a sidebar returns keyboard focus to its opening control. The inspector keeps origin, visual comparison, native measurement availability and validation scope separate.

At tablet width, the inspector is initially open and the fields panel is initially closed. Phone layouts initially close both secondary panels; an explicit toggle opens one. On phones, focus mode gains actual image width rather than adding a tall letterbox. Recent fields retain query coordinates, source mode and display-field size, never observation images or spectra. Reopening an archive entry remains an explicit new request. “View width” describes the displayed field; it does not falsely claim that a saved client-side crop changed the saved API product.

The compact image caption shows the actual painted observation date or explicitly unavailable date information. The external warning and source labels remain. The larger controls and full wordmark avoid the earlier narrow-header clipping.

## Measured geometry

The following Chromium measurements use the same initial real saved WISE view. Desktop/tablet height is 1080px; phone height is 844px. Browser coordinates describe the canvas element, including letterboxing, not the scientific coverage of its pixels.

| Viewport width | Canvas left | Canvas top | Canvas width | Canvas height | Center offset from viewport |
|---:|---:|---:|---:|---:|---:|
| 1440 | 287 | 429.42 | 866 | 528 | 0 px |
| 1920 | 311 | 367.42 | 1298 | 608 | 0 px |
| 1024 | 19 | 429.42 | 724 | 528 | −131 px |
| 390 | 17 | 521.06 | 356 | 338 | 0 px |
| 320 | 17 | 581.70 | 286 | 338 | 0 px |

The tablet image is centered within the stage beside its initially open right inspector; it is not centered on the full viewport until the inspector is closed or focus mode is used. At both wide desktop sizes, the central stage is wider than either sidebar, and the image is centered between the sidebars. At every checked size it is centered within its own stage within 2px and begins in the first screen. The 390px phone canvas starts about **521px earlier** than the baseline. This does not mean the entire image and every control fit simultaneously on every phone screen.

Focus mode increases canvas width from **866 to 1294px** at 1440px, **356 to 388px** at 390px, and **286 to 318px** at 320px. The 1440×900 targeted checks separately confirm that the Play button fits in the initial viewport in both normal and focus modes. The image has moved earlier and is centered; it has not increased in every dimension at every viewport.

## Browser and behavior evidence

Chromium **159.0.8154.6**, Firefox **159.0** and WebKit **27.2** exercised all five widths: 1440, 1920, 1024, 390 and 320px. These are headless desktop engines with those viewport sizes, not physical-device testing.

| Group | Outcome | Scope |
|---|---|---|
| Centered workspace | 15 configurations verified; 14 passed on the first run, one passed a targeted follow-up | Geometry, no horizontal page overflow, wider central stage on desktop, source/warnings retained in focus, independent sidebar close/focus restoration, inspector quality labels, keyboard dialogs, spectrum selection, reduced-motion playback disabled, query-only history. |
| Canvas persistence | Passed in all 15 configurations | The identical DOM canvas survives sidebar collapse, focus changes and blink playback. Sampling the real canvas during playback observes multiple distinct painted images. Switching to paired mode intentionally creates its second viewport. |
| Retained real product states | **9/9 passed** | Each engine exercises a genuine matched Barnard pair, a real WISE partial-download single epoch, and a real Epsilon Indi partial-discovery single epoch. Actual immutable assets are used. Play/Pause, distinct A/B asset hashes, paired view and Difference work for the matched pair. Single-epoch recovery retains its specific reason, disabled B and exact archive-query retry without an automatic saved fallback. |
| Pending/error and short desktop | **9/9 passed** | Each engine checks 320px/390px pending and failed-request navigation, visible source selection and no automatic fallback, plus initial/focused Play visibility at 1440×900. Only transport failure is injected; no observation values are fabricated. |
| Final header typography | **6/6 passed** | Each engine measures the actual source-label text bounds in focused 1440×900 and pending 320×844 views. The final label is 13px, its text and select stay inside the header/viewport, no page overflow appears, and focused desktop Play still fits within 900px. |

The initial layout run performed **30 axe scans**, covering the workspace and opened fields panel at all browser/viewport combinations. They reported **zero violations at all severities**. The targeted WebKit follow-up added two scans, also with zero violations. Incomplete color-contrast and `aria-prohibited-attr` checks still require human review; these results are not full accessibility certification.

### Preserved WebKit assertion failure

The first WebKit 1440px run found zero selected markers in an immediate DOM count after pressing Home on the spectrum. The original result and screenshot remain under `backend/.cache/phase5-centered/matrix/`. It was not overwritten or called a confirmed production regression.

The targeted follow-up uses one Home keypress, a bounded 2-second wait for the selected marker, and a `MutationObserver` across subsequent animation frames. It passed: the immediate count was 1, the keypress/assertion sequence took 147ms, and the observed selection count remained 1 without a reset. No second keypress, arbitrary sleep or product-code change was used to obtain that result. The original zero was not reproduced; its precise cause is therefore unresolved. The test now waits for the expected state rather than assuming a synchronous render.

### Final header inspection

Review of the focus screenshot prompted a narrow clipping check. Before-change Chromium bounds showed the controls at y=18.59–62.59 inside an 82.19px header, with no clipping observed. The source label was nevertheless only 12px. A header-specific correction sets it to the shared 13px size and 1.4 line height. The six targeted checks above verify actual text-node bounds in all three engines; they do not imply that a clipping defect was demonstrated. The full layout matrix was not repeated for this typography-only correction. Earlier screenshots and hashes are retained locally under `before-header-correction/`.

## Data and reproducibility

Behavioral checks use real explicit-saved API products and unchanged retained real matched/single-epoch/partial-discovery API responses with their actual assets. No new archive discovery, cutout acquisition, synthetic observation data, golden rebuild, or backend scientific change is part of this layout verification.

The matched/partial acquisition run retained assets in its own `backend/.cache/phase5/comparison-first/live` directory. The first product-test attempt incorrectly requested those from the normal runtime cache and received missing-asset errors. That attempt is preserved as `products-wrong-cache-attempt.json`. The corrected isolated test serves the exact retained bytes, records their SHA-256 hashes and leaves the normal application cache unchanged. The WISE retained single-epoch case uses its real assets from the ordinary live cache. This distinction matters when reproducing the tests.

Scripts under `frontend/qa/phase5/`:

- `browser-centered-baseline.mjs`: before screenshots, source hashes and canvas bounds.
- `browser-centered.mjs`: three-engine/five-width matrix, geometry, axe, persistent rendering and keyboard/state checks. `QA_ENGINES`, `QA_WIDTHS` and `QA_OUTPUT` support a bounded targeted follow-up.
- `browser-centered-products.mjs`: unchanged real product responses and immutable asset bytes, with hashes.
- `browser-centered-targeted.mjs`: loading/error source navigation and 900px-high desktop transport visibility.
- `browser-centered-header.mjs`: final source-label text geometry and typography in focus/loading headers.
- `browser-centered-captures.mjs`: final screenshots and frontend/build/observation hashes.

The ignored Playwright/axe installation is under `backend/.cache/phase5/browser-tools`. Local evidence is under `backend/.cache/phase5-centered/{before,matrix,targeted-webkit,products,targeted,header}`. The tests used owned hidden local processes on API port 8176 and Vite port 5176, with file logs under `backend/.cache/phase5-centered/`. Pre-existing servers on 8000 and 5173 were not altered. New QA scripts and documentation images are isolated from runtime product assets.

## Final artifacts and limits

The final frontend build passed type checking and the real-only packaging gates, producing `index-y2xB213k.js` and `index-BUAdjTnK.css`. After the layout changes, the frontend agent also ran `test:real-data`, `test:wcs` (**1458 checks**), `test:semantics` and `test:views`; all passed. The subsequent header typography correction received a fresh build and the six targeted checks above. No backend test suite or new upstream scientific acceptance matrix was required for this presentation-only change.

Eight screenshots, actual source-observation hashes, all frontend source-file hashes, build hashes, capture-script hash and API version are recorded in [the origins manifest](../screenshots/centered/origins.json):

- [1920px workspace](../screenshots/centered/workspace-1920.png) and [1440px workspace](../screenshots/centered/workspace-1440.png).
- [Focused image](../screenshots/centered/focus-1440.png) and [paired comparison](../screenshots/centered/comparison-1440.png).
- [1024px tablet layout](../screenshots/centered/workspace-1024.png).
- [390px phone](../screenshots/centered/workspace-390.png), [320px phone](../screenshots/centered/workspace-320.png), and [phone inspector](../screenshots/centered/inspector-390.png).

Published images use real saved observations; the same legacy limitations remain visible. The inspector screenshot is intentionally scrolled to the opened panel. Source/build hashes were verified against the final files after capture. Owned verification services were stopped after final checks; logs remain in the ignored evidence directory.

No human user study, screen-reader evaluation, physical-phone/tablet test, full native-browser zoom certification or complete photosensitive-flash analysis was performed. Automated source/quality labels and keyboard behavior do not establish that users understand the scientific caveats. Scoped scientific and upstream-availability findings from previous phases remain unchanged.
