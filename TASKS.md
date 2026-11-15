# TASKS.md — SPHEREx SkyBlink Task Board

> **Current audit continuation (2026-11-14):** API 1.5 / policy v1.7 is archive-first with explicit saved mode, corrected archive target coordinates, source receipts, bounded partial/single-epoch output and stricter measurement eligibility. Existing-method independent controls pass within their tested scope; the proposed refinement fails and is not adopted. See [current report](docs/verification/phase4-online-verification.md). Historical checkpoints below do not certify current deployment or universal science.

**Audit Phase 1 (2026-11-14):** Real-only packaging and serving cleanup authorized and implemented; see `docs/guides/real-data-policy.md` and the audit plan. Repository policy v1.3; API 1.2.0 unchanged. The original task records below are historical; their fixture/comparator instructions are retired. Audit Phases 2-5 remain open.

**Pre-audit status (2026-11-14):** Code and data are complete. Contract **1.2.0**; golden cache **revision 3** 5/5 (DR1+QR3, no QR2); `pytest` **83/83**; five-target card **5/5**; `skyblink:final` **844 MB**, healthy at 105.7 MiB idle, health version 1.2.0, smoke-tested 5/5. B10/S7/D2/F10/B12/F11 are done; I3 is in Help/README; B11 is closed as NO-GO. Normal operation uses **real data only** — no automatic development-fixture fallback. Remaining: **I1** public deployment and **I2** demo/submission, plus public-repo access and the final November 13 guide check. **B9** is optional/deferred.
**Owners:** `backend`, `frontend`, `science`, `orchestrator` (see `AGENTS.md` §2).  
**Rule:** one task per agent at a time. Do not start a task whose dependency is open.

## Final state at a glance

| Area | Result |
|---|---|
| Contract | **1.2.0** (DR1/QR3 release values; schema unchanged); `openapi.json`, models, docs, development fixtures updated |
| Golden cache | **revision 3, 5/5 (DR1+QR3, no QR2)**; real SkyView DSS2/WISE + Gaia DR3; 17 telemetry sidecars; 12,870,733 bytes / 442 files |
| Spectra | dense tier, 24–72 channels/epoch; revision-3 counts in README/validation report |
| UI | F4 workstation + F5 telemetry/curtain/comparator + F6 trial-motion/LVF/sonification/triage |
| Tests | **83/83** backend; frontend typecheck/build; five-target card 5/5 |
| Live arbitrary | **real data only**; TAP 60 s, sky 120 s, frontend 130 s, cutout 20 s; Field B 200 in 39.6 s, warm 0.014 s |
| Container | `skyblink:final` 844 MB, 2 GB limit, 105.7 MiB idle, health 1.2.0, five-target smoke 5/5 |
| Repository | **private** <https://github.com/tureisD/SkyBlink>; make public or grant judge access before judging if required |
| Public URL | **none yet (P0)** |
| Remaining | I1 deployment, I2 video/submission, public-repo access, final November 13 guide check; I3 done, B11 NO-GO |

The original Phase 1 order below is historical. Phase 2 tasks (W0, O2, B8, B9, S4, F5, F6, S5) are in the task table.

---

## Initial order of work

1. **O1** — Freeze API contract and create explicit development fixtures (Orchestrator) — blocks F1.
2. **B1** — IRSA client + one-target cutout pipeline (Backend) — unblocks F1 integration.
3. **F1** — Blink canvas with development-fixture frames (Frontend) — can start immediately after O1.
4. **S1** — Golden cache builder for one target (Science) — can start immediately after O1.
5. **B2** — Six-band coadds + difference mode (Backend) — after B1.
6. **F2** — Timeline, band pills, URL state (Frontend) — after F1.
7. **S2** — Golden cache for all five targets + tests (Science) — after S1.
8. **B3** — Spectrum endpoint + live arbitrary-coordinate hardening (Backend) — after B2.
9. **F3** — Spectrum drawer, Artifact Shield, cross-mission curtain (Frontend) — after F2.
10. **F4** — Scientific-workstation visual refactor (Frontend) — after F3.
11. **S3** — Docker, CI, validation report, README (Science) — after S2.
12. **I1** — Integration, deployment, five-target smoke test (Orchestrator) — continuous.
13. **I2** — Demo video, submission checklist (Orchestrator + Science) — H+42.

---

## Task table

| ID | Owner | Task | Acceptance criteria | Depends on | Status |
|---|---|---|---|---|---|
| **O1** | orchestrator | Freeze API contract; write Pydantic models; generate `openapi.json`; create explicit development-fixture manifests/frames in `frontend/public/mock/` | Frontend can render a fixture blink without the backend; contract matches `AGENTS.md` §3; the 12 contract questions in `docs/decisions/o1-contract-decisions.md` are resolved | — | done |
| **B1** | backend | IRSA client: TAP primary, SIA2 fallback; cutout download; parse `IMAGE/FLAGS/VARIANCE/ZODI/PSF/WCS-WAVE`; subtract ZODI + local background; reproject to 240×240 @ 3.075″/px | One real SPHEREx frame for WISE 0855; no `hdul[0].data`; `BIT_SOURCE` preserved; `spectral_wcs.sip = None`; per-band HALO counts exposed for S2 | O1 | done |
| **B2** | backend | Six-detector inverse-variance coadds; shared cross-epoch normalization; difference frames; `/api/v1/sky` manifest | All six bands + `all`/`thermal` frames; difference dipole; manifest contract | B1 | done |
| **B3** | backend | Spectrum endpoint; live arbitrary RA/Dec hardening; caching; error envelope | Dense spectrum for five targets; bounded live search; §3.7 errors | B2 | done |
| **B4** | backend | Golden-cache-first `/sky` for catalog targets; HALO display-only mode; optional PSF-matched differences | Catalog `/sky` serves golden manifest/assets without IRSA; HALO mode recorded and rendered; optional PSF differences | B2, S1 | done |
| **B5** | backend | Live-query performance: cap visits/epoch for arbitrary `/sky`, shorten retry/deadline, preserve 503 envelope; optional PSF-matched differences | Arbitrary `/sky` cold path <15 s or documented; 503 within ~20 s; differences PSF-matched if time | B4 | done |
| **B6** | backend | Golden-cache-first `/spectrum` for catalog targets using `golden_cache/{target}/spectrum.json`; preserve target/epoch filters | Catalog spectra served without IRSA; contract unchanged; live path available | B3, S2 | done |
| **B7** | backend | Apply the B5 live budget to arbitrary `/spectrum`: 1 epoch/1 visit/band, TAP-only, 503 envelope; golden/catalog unchanged. **Live sky/spectrum budgets were later superseded by B12 (60 s TAP / 120 s sky / 130 s frontend).** | Arbitrary spectrum 503 within the live budget; catalog golden unchanged; tests pass | B6 | done |
| **F1** | frontend | `BlinkCanvas.tsx`: ImageBitmap ring, RAF loop, LUT colormaps, contrast/bias, reticle | 60 FPS; no React re-mount per tick; renders the explicit development fixture | O1 | done |
| **F2** | frontend | `TimelineDock.tsx`: play/pause, 1–8 FPS, loop, difference, six band pills, presets; `useUrlState.ts` | URL round-trips; missing bands disabled; photosensitivity cap | F1 | done |
| **F3** | frontend | `SpectrumDrawer.tsx`, `ArtifactShield.tsx`, `CrossMissionCurtain.tsx` | Spectrum with error bars/features; flag badge; optical/IR curtain or hidden unavailable side | F2 | done |
| **F4** | frontend | Scientific-workstation refactor: canvas-first layout, HUD chips, unified left/right rails, precision media deck, bespoke sliders/swatches, 120ms motion; see `agents/prompts/frontend.md` design contract | No raw text over pixels; palette `#08090b`/`#0e1015`/1px hairlines; strict mono telemetry; no default checkboxes; typecheck/build pass; before/after screenshots at 1600×1000 and mobile | F3 | done |
| **S1** | science | `scripts/build_golden_cache.py` for one target; optional `scripts/generate_fallback_fixtures.py`; manifest schema | Real data cached; any development fixture is explicit opt-in and labeled `is_simulated_fallback: true` | O1 | done |
| **S2** | science | Golden cache for all five targets; pytest suites for astrometry, bitmasks, API contract, spectra | Five manifests; `pytest` green; five-target test card passes; R Draconis and WISE 0855 HALO decisions recorded | S1 | done |
| **S3** | science | Dockerfile, docker-compose, README, attribution, SI disclosure, validation report | One container serves API + frontend; README complete; limitations stated | S2 | done |
| **W0** | science + backend | **Read-only feasibility spike.** Measure PSF-wing recovery on Barnard/R Dra, LVF visit counts/timing, R Dra MJD clusters, telemetry sidecar size, live multi-epoch timing, and `hips2fits` availability. No product code, contract change, or golden rebuild. | `docs/research/w0-feasibility-report.md` with measured pass/fail numbers; `STATUS.md` updated; no code/model/cache changes | S3, F4 | done |
| **O2** | orchestrator | Additive contract 1.1.0: `epochs[].telemetry` (outside `frames`), `epochs[].lvf_geometry`, optional `epochs[].candidates`, `channels[].photometry_method`/`aperture_mode`, display-only `core_inpainted`; regenerate `openapi.json` and docs | Existing 40 tests pass; new fields optional; both workers confirm | W0 | done |
| **B8** | backend | Dense spectra (12 visits/band/epoch where available, 9/6 fallback), telemetry sidecar writer, IVW multi-band coadds, PSF-matched differences, exact LVF WCS gradient, optional display-only core inpainting. **PSF-wing photometry is dropped (W0 NO-GO).** | Dense spectra measured; telemetry parity; differences validated; tests/guardrails green | O2 | done |
| **B9** | backend | Optional **Deep blink** for arbitrary `/sky`: band subset parameter, 2 epochs of B5+B6 (or B6), ~30 s budget with progress; **no `<15 s` cold claim** | A documented, bounded deep-blink path; catalog/golden path unchanged | O2, B8 | todo (deferred) |
| **B10** | backend | **DR1 support:** recognize `/dr1/` in `_detect_release`; accept `DR1`/`QR3`/`DR1+QR3` in `collection`/`release`; update `source_label`, mixed labels, error details, and SIA fallback collections (`spherex_dr1`, `spherex_dr1_deep`, `spherex_qr3`, `spherex_qr3_deep`); update tests and bump contract to **1.2.0** | Live DR1 response shows `release="DR1"`, `collection="spherex_dr1"`; mixed epochs show `DR1+QR3`; no `release="unknown"` for DR1; tests pass | O2 | done (`3c642ef`; 79 tests) |
| **S7** | science | **Golden cache revision 3:** rebuild from **DR1+QR3** after B10; re-measure spectra/telemetry; regenerate overlays only if the WCS changed; run verify, five-target card, and container smoke; keep revision 2 as rollback | 5/5 targets load with DR1/QR3 labels; counts re-measured and committed; no fabricated epochs; rollback documented | B10 | done (`664977e`; 5/5, 17/17, 12,870,733 bytes) |
| **D2** | orchestrator | Update README, STATUS, TASKS, ROADMAP, AGENTS, pre-event verification, the resource-review doc, and the frontend Help/credits text (`HelpDialog.tsx`) with revision-3 counts and DR1/QR3 labels | Docs and user-facing help match committed manifests; no stale "QR2-only" or "PSF cube" claims | S7 | done |
| **I3** | orchestrator | Optional: add CSA/CADC/NEOSSat as related-archive links/credits; no ingestion | Links and licence credit present; no runtime dependency | D2 | done |
| **B11** | backend | Optional/timeboxed: evaluate the DR1 102-channel all-sky cube for a spectrum endpoint | Only ship if measured and honest; otherwise record a NO-GO | B10 | done (**NO-GO**; `docs/research/102-channel-cube-feasibility.md`) |
| **B12** | backend | **Live arbitrary budget:** raise TAP timeout to 60 s and the sky deadline to 120 s; keep one epoch and one visit per band. Align frontend arbitrary request timeout at 130 s and cutout request at 20 s. | Real random field returns 200 within the budget; one real epoch; catalog path unchanged; **83 tests pass** | B10 | done (2026-11-14; Field B 200 in 39.6 s, warm 0.014 s) |
| **F11** | frontend | **Remove automatic fixture fallback:** live failure shows a clean retry/benchmark error; no fixture request and no automatic fallback text. Keep `VITE_DATA_SOURCE=mock` / `VITE_SPECTRUM_SOURCE=mock` as explicit development opt-ins only. | Clean error UI verified with no fixture request; labeled development fixture when explicitly selected; typecheck/build pass | B12 | done (2026-11-14) |
| **S4** | science | Real SkyView DSS2 Red + WISE 3.4 overlays (retry), Gaia DR3 G≤16 pins, telemetry sidecars, 12-visit golden cache v2 rebuild. **R Dra NEP clustering is dropped (W0 NO-GO); keep current epochs.** | Real overlays for 5 targets; measured spectra; five-target card; no fabricated epochs | B8, W0 | done |
| **F5** | frontend | Physical MJy/sr loupe + decoded Table 16 flag names, real curtain + Gaia pins, dense-spectrum view, forward T1+T6 comparator (no inverse fit) | Sidecar decode correct; real flags; curtain on 5 targets; typecheck/build/Playwright | O2, S4 | done |
| **F6** | frontend | Shift-and-stack/parallax sandbox, LVF visualizer, Web Audio sonification, dynamic-channel triage card export | F4 design contract; reduced motion; no fake data; typecheck/build/Playwright | F5 | done |
| **F7** | frontend | Judge-facing traps: RA/Dec search with 5′ catalog snapping, target URL normalization, WISE W2 4.6 curtain default, single-epoch live banner | Search WISE 2010/J2000 coords loads golden cache; WISE curtain uses W2; arbitrary 1-epoch shows clear banner; typecheck/build/Playwright | F6 | done |
| **F8** | frontend | Layout polish: move Search to left target rail, move Triage/Copy to right rail bottom, add top-right `?` Help modal covering all features/shortcuts/caveats | Actions in requested rails; Help accessible/scrollable; no behavior regression; typecheck/build/Playwright | F7 | done |
| **F9** | frontend | Beginner Help pass: plain language, section icons, quick-tour cards, annotated UI/screen map, glossary, caveats | Help readable by a newcomer; no AI-sounding repetition; images/icons render; mobile scroll; typecheck/build/Playwright | F8 | done |
| **F10** | frontend | **Spectrum hover fix:** replace per-point `pointerenter/leave` + native `<title>` with nearest-point SVG hit testing (`getScreenCTM`), a custom non-interactive tooltip, and a fixed-height LVF status area; refresh the four primary screenshots | No hover jitter or chart shift; tooltip stable inside the plot at desktop and mobile; LVF sync works; typecheck/build pass | F9 | done |
| **S6** | science | Beginner README pass: Start here, annotated UI/flow figures, plain-language intro/feature tour, glossary, contributor link | Newcomer can understand/try the app; links valid; tests/build pass | D1 | done |
| **S5** | science | Rebuild `skyblink:final`, README v2, F6 screenshots, final validation | Image <900 MB; five-target container smoke 5/5; README accurate | S4, F6 | done |
| **D1** | orchestrator + science | Documentation finalization: README/setup, contract, roadmap, status, W0 report, deployment guide | All docs match revision 2; links/paths valid; no stale feature or test claims | S5 | done |
| **I1** | orchestrator | Integrate, deploy, run five-target smoke test at H+12/24/32/38 | Public HTTPS URL; all five targets; arbitrary RA/Dec; no console errors | B8, F6, S5 | doing |
| **I2** | orchestrator + science | Demo video, submission checklist, final QA | 2-minute video; repo/video/URL; SI disclosure; submitted by H+46 | I1 | todo |

---

## Remaining submission work

| Item | Owner | Notes |
|---|---|---|
| Public HTTPS host + URL | Orchestrator + user | No host/credentials yet; see `docs/guides/deployment.md`. |
| Public code repository | Orchestrator + user | **Private** repo exists at <https://github.com/tureisD/SkyBlink> (account `tureisD`); make it public or grant judge access before judging if the submission requires a public repo. |
| ~2-minute demo video | User + Orchestrator | Script updated to dense spectra/real overlays; public hosting. |
| Submission form | User | Description, team roles, URL, repo, video, screenshots, SI disclosure, limitations. |
| Nov 13 rechecks | Orchestrator | **Resources tab and DR1+QR3 refresh done** (2026-11-13; see `docs/reference/resource-release-2026-11-13.md`). Still recheck the Project Submission / Judging guides, local rules, venue internet. |
| Final screenshots | Orchestrator | **Done:** the four primary screenshots are current revision-3 captures; supplementary feature captures remain revision 2. |
| Optional I3 / B11 | Orchestrator / backend | I3 CSA/CADC links are in Help/README; B11 evaluated as **NO-GO** for a live endpoint (`docs/research/102-channel-cube-feasibility.md`). |

---

## Status codes

- `todo` — not started.
- `doing` — claimed and in progress.
- `blocked` — waiting on a dependency or decision; add a note in `STATUS.md`.
- `review` — PR open or ready for Orchestrator review.
- `done` — merged and verified.

---

## Claiming a task

1. Pick the top unblocked task for your role.
2. Message the Orchestrator to claim it; the Orchestrator updates `Status` to `doing`.
3. Work only in your owned paths.
4. When done, report: files changed, commands run, tests passed, blockers.
5. The Orchestrator changes the status to `review`, merges, and marks it `done`.

**Do not edit `TASKS.md` or `STATUS.md` from a worker worktree.** They are owned by the Orchestrator in the main worktree; editing them in parallel causes merge conflicts.

---

## Do not start

- Auth, accounts, or a database.
- Full-sky HiPS/HEALPix/Zarr.
- ZOGY or optimal subtraction.
- ML models or fake confidence scores.
- 3D volumetric flythroughs.
- Any feature outside the P0/P1 scope in `ROADMAP.md` §5.
