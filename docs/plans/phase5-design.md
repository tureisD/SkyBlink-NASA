# Phase 5 design decision and implementation record

**User-directed layout revision (2026-11-15, policy v1.10):** the current
composition places field navigation on the left, the primary observing stage
in the center, and interpretation/tools on the right. Collapsible rails and a
focus mode reclaim image space. The refinements below still govern readable
typography, evidence meaning and progressive disclosure; the original default
shell is historical. See [centered workspace verification](../verification/phase5-centered-workspace-verification.md)
for the measured layout and interaction outcomes. This layout changes no
scientific processing or source policy.

2026-11-15. U0 studies precede the product CSS changes. Policy v1.8 approval comes from the Orchestrator; API 1.5 and all science processing remain unchanged.

## Two concrete studies

Renderable, self-contained studies and Chrome captures are in the ignored local directory `backend/.cache/phase5/design/`: `notebook.html`, `charcoal.html`, and each name with `-desktop.png` (1440×1000) and `-mobile.png` (390×844). Run `node backend/.cache/phase5/design/capture.cjs` to recapture. These are review artifacts, never product data or fallback pages.

Both studies embed the exact saved WISE 0855 ALL WebP bytes and actual mean dates (2025-06-14 and 2025-12-03). Both show the real R Draconis 240 recorded samples / zero finite flux result and the same clearly labeled recoverable failure scenario. Neither represents the historical comparison as validated. No scientific samples or imagery were generated. Prototype buttons are layout studies, not working application controls.

**A — Field notebook:** light neutral surroundings, large title, paired dark images, full-width caption and evidence below. It makes prose easy to read and gives the comparison maximum width. On a phone, simultaneous small images lose useful spatial detail; broad light surroundings compete with faint image detail. Long prose pushes evidence down.

**B — Calm charcoal workspace (chosen):** restrained dark surfaces, observation centered with a dedicated evidence column on desktop, stacked images and ordinary vertical scrolling on mobile. This retains the useful dark image adaptation of the current instrument while removing microtype and competing control rails. Its working explanation can stay adjacent to the image on desktop. Mobile must collapse optional detail, not shrink the desktop sidebar. Choice is a design judgment from rendered artifacts, not a user-study finding; independent novice comprehension remains untested.

## Content inventory and disclosure

| Content | Audience/task | Consequence | Placement |
|---|---|---|---|
| Search, target, source, Help | Everyone / choose field | Prevent wrong field or silent saved fallback | Always available, including failures |
| Actual dates, selected bands, comparison limit | Everyone / interpret pixels | Prevent date-bucket and variability claims | Image caption and primary controls |
| Step, pause, A/B, side-by-side | Everyone / compare | Motion alternative and explicit pair | Compare controls, wrapping on mobile |
| Origin, comparison, measurement, validation | Everyone / assess evidence | Four distinct dimensions, no trust score | Evidence summary; consequential limit always visible |
| Spectrum samples, null/excluded reasons, table | Measurement inspection | Null is not zero; eligibility is not isolation | Spectrum inspector and accessible table |
| Colormap/stretch/bias, catalog overlays | Advanced / inspect display | Display values are not native flux | Advanced display disclosure |
| Trial motion, parallax, audio | Advanced exploration | Assumed parameters are not measured motion | Advanced tools disclosure |
| Flag bits, WCS, source lineage, replay | Expert / audit | Unknown stays unknown | Technical evidence disclosure |
| Report and share | Review / reproduce | Selected pair and expected identity must match | Evidence actions; drift notices |

## Implementation tokens and states

Body 15–16px, secondary 13–14px, title 26–32px, aligned numeric monospace only where useful. Charcoal background `#171b1d`, panels `#202628`, text `#edf0ed`, secondary `#b7c1c0`, muted teal interaction accent `#b2d7cb`; amber limits carry words as well as color. Control target 44px, visible 2px focus outline, no glow or glass effects. Use spacing and separators rather than nested cards. Dark image well remains `#08090b`.

Initial entry is paused; unavailable/failed/cancelled states retain search, source selection, Help, and explicit saved-example recovery. Loading reports elapsed time and a bounded wait, never a fabricated stage/percentage. Cancel stops browser waiting; backend shared work may continue. One epoch permits observation but no temporal claim. Saved comparisons are explicitly legacy/unvalidated. Archive visual compatibility does not imply calibrated variability. Measurement availability is evaluated independently in the spectrum; selected-field scientific validation is not established by origin or replay.

No new schema is needed. Existing API fields support origin, comparison, discovery and measurement facts. Missing validation metadata remains unknown/not established. Expected analysis IDs detect changed results; links do not force the server to restore old analysis bytes. Full source/environment replay remains a separate scientific workflow.

## Review boundaries

The first implementation slice is real saved field → actual A/B selection → visible limitation → Evidence/report. It preserves the persistent canvas RAF and rejects simulated observations. Accessibility/browser and interaction results belong in the Phase 5 acceptance report. Screenshot inspection is not a screen-reader, flash-threshold or novice-user validation claim.

## Implemented slice and observed checks

The chosen design now runs in the application: persistent search/source/Help during loading, typed failures and cancellation; explicit saved-example recovery; paused task navigation; actual-date captions; A/B selection, manual steps and synchronized side-by-side; four separate evidence dimensions; advanced display/trial disclosures; source-record/report/share actions. The historical catalog assets remain unchanged. Archive requests retain their existing acquisition behavior.

Both side-by-side canvases use the same normalized camera, display transfer and selected observation pair. The primary canvas is not remounted on playback ticks. The second persistent renderer exists only while paired inspection is selected. Touch scrolls the document; zoom/reset buttons and focused-image Shift-arrow panning provide alternatives to mouse drag/Control-wheel. Search and the spectrum table provide non-hover coordinate/measurement access. Raw telemetry HUD detail is disclosed with advanced inspection rather than covering the initial image.

The modal portal makes the application inert, contains forward/backward Tab including initial shell focus, handles Escape and restores its opener. Chrome checks passed initial Shift-Tab, twelve forward tabs, inert background and restoration to Help. WebKit testing exposed its different click-focus behavior; focusing buttons in the application click-capture phase addresses the opener before the modal mounts. The browser matrix preserves failed attempts and the final rerun separately.

Local baseline captures: `backend/.cache/phase5/browser-baseline/` (science agent, real saved WISE at 1440/390/320px with spectrum). Intermediate and final shell captures/checks: `backend/.cache/phase5/workspace-*.png`, `compare-desktop.png`, `search-desktop.png`, and `shell-checks.json`. Initial Chrome layout measurements found no document overflow at 1440 or 320px and no visible button below 24px. `shell-checks.json` recorded two comparison canvases, shared zoom 1.5, explicit A/B URL identities and no page errors.

Frontend build/typecheck and real-only packaging gates passed. Existing real-data, exact TAN (1458 points), Phase 4 semantics and new `test:views` regression commands passed. Final cross-engine, failure/cancellation, unavailable-spectrum and accessibility results are reported by the independent QA agent and integrated into Phase 5 verification. No manual screen-reader, measured flash-threshold or independent novice comprehension result is claimed. These remain release-review limits, not inferred passes from automated checks.
