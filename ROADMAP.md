# Planet X and SPHEREx — SPHEREx SkyBlink Roadmap

**Phase 6 local verification (2026-11-15, policy v1.13):** compact square-edged workspace and explicit spectrum-only recovery are implemented. Target title/task navigation are in the left rail; field settings retain source and position. All five fresh known-exposure spectra returned HTTP 200, with exclusions/nulls preserved; live discovery remains unavailable. Backend regression passed 316 tests, frontend suites/build passed, and local production serving verified all five saved sky/spectrum products plus 278 exact asset bytes. Final keyboard controls passed in Chromium, Firefox and WebKit. Busy/storage admission preserves retained lineage. See [Phase 6 verification](docs/verification/phase6-verification.md) for the measured scope, scientific/display limitations and original failed attempts. Docker build/Linux permissions/volume restart remain unverified because no usable engine exists here. Publishing/public access/submission are deferred at the user?s explicit request.

**Discovery outage follow-up (2026-11-15):** current TAP and all four SIA collection searches return upstream errors despite the corrected runtime. Earlier successful pairs remain historical evidence. Policy v1.12 / API 1.6.0 authorizes explicit catalog-only known-exposure recovery with fresh online image downloads and unchanged scientific gates. It does not silently replace a live search or claim current archive completeness. See [contract](docs/decisions/known-exposure-contract-decision.md) and [measured verification](docs/verification/phase5-discovery-outage-verification.md).

> **Latest development repair (2026-11-15):** policy v1.11 replaces the stale
> method-11 worker behind the UI, adds source-drift rejection and integrates
> sidebar menus/notifications around a larger image. All five final catalog
> requests on the corrected port-8000 backend returned matched two-epoch
> comparisons; transfer failures remain in lineage rather than being erased.
> API1.5, image method12 and scientific thresholds are unchanged. See
> [verification](docs/verification/phase5-catalog-reliability-and-viewer.md) and
> [source review](docs/research/catalog-acquisition-source-review.md).

> **Current non-release priorities (2026-11-15):** reviewed target interpretation sheets, broader measured live reliability, human comprehension/accessibility, and one coherent current technical guide. Broader calibrated photometry, uncertainty validation, deblending and measured motion are separately gated scientific extensions. See [limitations and acceptance proposals](docs/current-limitations-and-next-steps.md). Policy v1.10 centers the image between collapsible Fields/Inspector panels; API1.5 and image method12 remain unchanged.

> **Phase 5 refinement (2026-11-15):** policy v1.9 adds consistent typography/chart controls, responsive spectrum inspection, query-history settings and clearer comparison recovery. Image method 12 prioritizes balanced cross-epoch acquisition under the unchanged visual compatibility checks. See [UI verification](docs/verification/phase5-polish-verification.md) and [retrieval decision/results](docs/decisions/comparison-retrieval-decision.md). This does not expand the scientific validation scope or establish universal archive availability.

> **Phase 5 checkpoint (2026-11-15):** observing workspace implemented under policy v1.8 with API1.5 unchanged. See [verification](docs/verification/phase5-verification.md) and [observing guide](docs/guides/observing-guide.md). Browser checks do not establish participant comprehension, assistive-technology usability or quantitative flash safety; those gates remain explicit.

> **Current audit continuation (2026-11-14):** API 1.5 / policy v1.7 is archive-first with explicit saved mode, corrected archive target coordinates, source receipts, bounded partial/single-epoch output and stricter measurement eligibility. Existing-method independent controls pass within their tested scope; the proposed refinement fails and is not adopted. See [current report](docs/verification/phase4-online-verification.md). Historical checkpoints below do not certify current deployment or universal science.

**Document:** Roadmap v1.0 (consolidated)  
**Date:** 2026-11-08  
**Event:** NASA Space Apps Challenge 2026 — November 14–15, 2026  
**Challenge:** [Planet X and SPHEREx](https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/) — Category: **Advanced** — Skills: Astrophysics, Planets & Moons, Software  
**Working title:** **SPHEREx SkyBlink** — *the infrared time-domain blink comparator*  
**Status:** Delivered (2026-11-13; live-budget/real-only update 2026-11-14): contract **1.2.0**, golden **revision 3 (DR1+QR3)**, **83 tests**, `skyblink:final` verified at 844 MB / 105.7 MiB idle / health 1.2.0 / five-target smoke 5/5. B10/S7/D2 are complete, and B12/F11 now enforce the two-minute live budget and real-data-only failure behavior. Public deployment, the public repository switch, demo video, and submission remain. See the implementation-status note below.
**Audit implementation update (2026-11-14):** Phases 1-3 removed product fixtures, repaired coordinate/discovery behavior, and implemented measurement masks, supported backgrounds and matched comparisons. Real-data validation identified target-coordinate corrections and a failed candidate-control stability gate; scientific acceptance is not established. See `docs/verification/phase3-verification.md` and `docs/verification/phase3-calibration-audit.md`. Saved revision-3 assets are unchanged pending coordinated Phase 4 correction/rebuild. Historical completion/container statements are not current scientific validation.

**Phase 4 checkpoint (2026-11-14):** API 1.4.0 adds reproducibility and explanation metadata, pinned replay and corrected-coordinate staging. Scientific cache promotion is blocked; all five shipped datasets remain unchanged. See [Phase 4 verification](docs/verification/phase4-verification.md). UI overhaul is Phase 5; release/container/submission verification is Phase 6. The original delivery figures below are historical.

**Companion document:** `AGENTS.md` — the immutable agent contract, file ownership, and API schemas.

> **Implementation status (2026-11-13):** This roadmap is the original product/science plan. The delivered build differs in measured, documented ways:
> - **Contract 1.2.0** extends the accepted release values to `DR1`/`QR3`/`DR1+QR3`; the schema is unchanged from 1.1.0, which added telemetry sidecars, LVF geometry, optional candidates, and per-channel photometry provenance.
> - **Golden cache is revision 3**, built 2026-11-13 from live IRSA **DR1+QR3**: 5/5 targets, 17 epochs, 17 telemetry sidecars, **12,870,733 bytes / 442 files**. It contains **no QR2 data**. Revision 2 (QR2+QR3) is the documented rollback.
> - **Spectra:** dense tier up to **72 channels/epoch** (12 visits × 6 detectors), not the full 102-band sampling. Revision-3 used/total counts: WISE 0855 158/164; Barnard's Star 2/215; Epsilon Indi B 228/246; RW Aurigae 102/216; R Draconis 0/240. See `README.md` and `golden_cache/validation_report.json`.
> - **PSF-wing recovery and R Draconis NEP re-clustering were measured and dropped** (0/54 and 0/60 channels; R Dra is one continuous 520-day season). See `docs/research/w0-feasibility-report.md`.
> - **Real reference overlays:** SkyView DSS2 Red + WISE 3.4/4.6 and Gaia DR3 pins replace the earlier placeholder overlay; revision 3 reused them SHA-256-verified. Product development fixtures have been removed by audit Phase 1.
> - **Real data only:** normal operation uses live IRSA / saved DR1+QR3 data. A failed live request shows a clean error; it never falls back to `frontend/public/mock/` or `golden_cache/fallback_*`. Those paths and mock opt-ins have been retired.
> - **Live arbitrary budget (2026-11-14):** TAP timeout 60 s, backend sky deadline 120 s, frontend arbitrary timeout 130 s, cutout request timeout 20 s. A verified random field returned HTTP 200 in 39.6 s; warm repeat 0.014 s.
> - **Repository:** private <https://github.com/tureisD/SkyBlink>; make it public or grant judge access before judging if required.
> - **UI:** F4 scientific workstation + F5 telemetry/curtain/comparator + F6 trial-motion/LVF/sonification/triage. The spectrum hover uses nearest-point hit testing and a custom non-interactive tooltip; the four primary screenshots are current revision-3 captures.
> - **No public URL yet.** The image `skyblink:final` is built and locally smoke-tested; public deployment and submission are the remaining work.
>
> Where this document says “102-band,” read “dense SPHEREx spectrum (24–72 channels/epoch in this build).” The authoritative current behavior is `README.md` + `AGENTS.md` §3 + `docs/decisions/o1-contract-decisions.md`.


**Consolidates:** the v0.1/v0.2 roadmaps, the technical audit, and the agent draft. Those working files have been removed to avoid stale instructions; this document and `AGENTS.md` are the source of truth.

---

## 0. How to use this document

This is the **product, science, and execution plan**. `AGENTS.md` is the **engineering contract** for human and AI contributors.

| Reader | Read first | Then |
|---|---|---|
| Team lead / judge-facing lead | §1, §8, §11 | §13, Appendix E |
| Backend/data engineer | §5, §6, §9 | `AGENTS.md` §0–§4, §7A |
| Frontend engineer | §7, §10 | `AGENTS.md` §0, §3, §5, §7B |
| Science/validation engineer | §2–§5, §9 | `AGENTS.md` §4, §7C |
| Reviewer (Gemini or human) | §14 | Flag errors, scope cuts, missing risks |

**Source hierarchy (highest authority first):**

1. Official 2026 challenge page, Participant FAQ, and November 13 Project Submission / Judging guides.
2. NASA/IPAC IRSA SPHEREx documentation and the SPHEREx Explanatory Supplement.
3. The technical audit and v0.2 roadmap (working drafts, now consolidated into this document).
4. The v0.1 roadmap and the research PDF (background only; several claims are unverified).

If two documents conflict, the higher source wins. If a code instruction conflicts with a science guardrail, **stop and ask the Orchestrator**.

---

## 1. Executive summary

**SPHEREx SkyBlink** is a public-facing web tool that turns NASA SPHEREx Level 2 spectral images into a smooth, multi-epoch blink video and a spectrophotometric inspector for any patch of sky.

A user enters a Right Ascension and declination (or clicks one of five official targets). The server queries NASA/IPAC IRSA, fetches lightweight spatial cutouts, subtracts the zodiacal foreground and local sky, aligns the frames onto a common north-up WCS grid, and returns six detector-band frames per epoch plus a difference map. The browser plays those frames like a little video, with band isolation, artifact warnings, a proper-motion reticle, Gaia/WISE comparison, and a linked dense SPHEREx spectrum (24–72 channels/epoch in this build; the mission has 102 bands).

### 1.1 The golden path

1. Open the public URL — no login, no install.
2. Pick **WISE 0855** from the benchmark tour.
3. Watch the field blink; the source is invisible in Gaia and SPHEREx Bands 1–4, then appears in Bands 5–6.
4. Switch to **Barnard's Star**; blink and see the 10.3″/yr motion; toggle difference mode to see the dipole.
5. Inspect **Epsilon Indi B**: two brown dwarfs blended inside one 6.15″ pixel, with a composite CH₄/H₂O spectrum.
6. Blink **RW Aurigae** and **R Draconis** to see variability (or the NIR excess if RW Aur is quiescent) and Mira pulsation, with saturation/artifact warnings.
7. Copy the URL; it reproduces the exact RA, Dec, FOV, bands, epoch, and mode.

### 1.2 The winning demo

Open on **WISE 0855** (the "invisible in optical, glowing in thermal infrared" hook), then **Barnard's Star** (motion + difference dipole), then **Epsilon Indi B** (blending), then **RW Aurigae** and **R Draconis** (variability + flags). Close on a shareable URL and a one-sentence architecture slide.

### 1.3 Key architectural decisions

| Decision | Choice | Why |
|---|---|---|
| Where the FITS work happens | **Server-side** | 70 MB MEFs are unusable in a browser; cutouts + server-rendered frames are fast and reliable. |
| Data query | **IRSA TAP primary; SIA2 fallback** | TAP has no ~1-day SIA2 ingestion lag; SIA2 is a simpler fallback. |
| Primary viewport | **Custom dual-buffered HTML5 Canvas** | Rapid epoch flipping at 60 FPS; Aladin Lite is not built for synchronous blink loops. |
| Reference overlays | **Precomputed SkyView DSS2 Red + WISE 3.4/4.6** on the same WCS | Gaia/WISE comparison without a live Aladin dependency. CDS `hips2fits` was unreachable in the build environment; the committed overlays are real SkyView data. |
| Spectra | **Precomputed for the five targets; best-effort live** | Full 102-band forced photometry across many MEFs is too slow for a synchronous request; the build extracts a dense 24–72-channel visualization-grade spectrum instead. |
| Difference imaging | **Direct subtraction** of un-normalized coadds | PSF matching was measured but not adopted after it failed the residual-improvement criterion; ZOGY is out of scope. |
| Offline resilience | **Golden cache for the five targets** | The demo must survive an IRSA outage. Offline operation uses only the five saved real target datasets. |
| UI | **Precision mission-console aesthetic** | Dark, glassmorphic, high-contrast, keyboard-friendly. |

### 1.4 What changed from the drafts

- Corrected **Epsilon Indi B** (the brown-dwarf binary at `22h04m10.60s, −56°46′58.2″`, not ε Indi A) and **RW Aurigae** (`+30°24′04.8″`, not `+30°24′27″`).
- Added **Epoch 2025.8 propagated coordinates** for high-proper-motion targets; all cutout queries use them.
- Fixed the **HDU indexing trap**: `hdul[0]` is an empty `PrimaryHDU`; always use `hdul["IMAGE"]` … `hdul["WCS-WAVE"]`.
- Added the **`BIT_SOURCE` (Bit 21) preservation rule**: never mask all non-zero flags; only mask `HARD_BAD_MASK`.
- Added **`ZODI` (HDU 4) + local sky background subtraction** before coaddition/difference.
- Added the mandatory **`spectral_wcs.sip = None`** step for the `'W'` WCS.
- Chose **WCS-WAVE** for the MVP spectrum (≈1 nm accuracy); `CWAVE`/`CBAND` are optional validation, not a required 32 MB download.
- Replaced the v0.2 "30-day epoch" heuristic with **6-month survey epochs as the primary timeline**; visit-level sub-frames are optional.
- Corrected the **MJy/sr → μJy** conversion (the v0.2 formula was off by 10⁶).
- Removed the unverified claim of a "major 2025 RW Aurigae dimming episode."
- Scoped **TAP primary**, **golden cache**, **custom canvas**, and **simple difference** as the MVP; HEALPix/Zarr, WebGPU/Rust, ZOGY, auth, databases, and ML are out.

---

## 2. Official challenge brief and rules

### 2.1 The ask

> "Your challenge is to create a public-facing web tool to display images of the sky from the SPHEREx mission, making it easy for anyone to quickly see how they change over time. Users will enter the coordinates of a patch of sky (Right Ascension and declination). Your tool will display a series of images of that patch like a little video, making it easy to spot moving objects."

### 2.2 Background that matters

- SPHEREx launched in March 2025 and has been mapping the whole sky **every six months in 102 near-infrared bands** since May 2025.
- It is sensitive to hydrogen, water, carbon dioxide, carbon monoxide, and other molecules.
- It will image **more than a billion objects** — brown dwarfs, quasars, comets, asteroids, stars, supernovae, galaxies — which often overlap or vary.
- The challenge is explicitly a **public/citizen-science** tool: "help as many people as possible pitch in to make discoveries."

### 2.3 Required vs. optional

| Item | Status | Notes |
|---|---|---|
| Public-facing web tool | **Required** | Browser-based; no local Python; no gigabyte downloads. |
| RA/Dec input | **Required** | Users enter a patch center. |
| Series of images "like a little video" | **Required** | Temporal blinking is the core interaction. |
| Easy spotting of moving objects | **Required** | Primary scientific job. |
| Test on the five named targets | **Required in practice** | The brief says "Test your tool on…". Treat as acceptance tests. |
| Six-detector coadds | Optional | "You may (but are not required to) consider…". |
| On-the-fly spectra | Optional | "Extra kudos." |
| Add/subtract images at different times | Optional | Strong differentiator. |
| Configurable field of view | Optional | Trade-off with data transfer time. |
| Gaia/WISE overlays | Optional | Strong for the Y-dwarf demo. |
| URL coordinate query / embed | Optional | High value for sharing. |
| Display metadata and contamination flags | Optional | Directly addresses artifact false positives. |
| Use Astropy/Aladin | Optional | Strongly recommended. |

### 2.4 Event facts and rules

- **Hackathon dates:** November 14–15, 2026 (48 hours).
- **Theme:** "The Next Frontier."
- **Registration:** open through the end of the hackathon on November 15.
- **Challenge statements:** available now.
- **Resources:** "Resources will be available on Friday, November 13." More may be added before the event.
- **Team size:** maximum 6 members; Local Event teams need at least 1 person; Universal Event teams need at least 2 people for global judging. One challenge per team.
- **Submission:** through the team's project page on `spaceappschallenge.org`; Project Submission Guide and Judging & Awards Guide are released November 13.
- **Super Intelligence (SI) disclosure:** SI tools (LLMs, code generation, image/video generation, etc.) are allowed, but each submission must describe how they were used.
- **Judging criteria** (per 2026 local guidance; verify the official guide): **Impact 25%, Creativity 25%, Validity 25%, Relevance 25%.**
- **Plan for submission deliverables:** public demo URL, public repository, and a ~2-minute video (or a slide deck of ≤7 slides if the guide allows). The audit reports all three are required; confirm in the November 13 guide. Plan to open-source under MIT or BSD-3-Clause.

### 2.5 Compliance note

The official brief requires a **public-facing web tool** and explicitly anticipates data-transfer trade-offs. It does not require client-side-only processing. The live tool must remain reachable by judges **without installation, login, API keys, or a local server**, and must show data provenance. Confirm any 2026 rule changes in the November 13 guides.

---

## 3. Science context

### 3.1 How SPHEREx observes

SPHEREx uses a dichroic beamsplitter to feed two focal-plane assemblies, each containing three 2K × 2K HgCdTe detector arrays behind **Linear Variable Filters (LVFs)**. The result is six detector arrays covering 0.75–5.00 µm.

| Band | Wavelength | Resolving power |
|---|---|---|
| 1 | 0.75–1.09 µm | R = 39 |
| 2 | 1.10–1.62 µm | R = 41 |
| 3 | 1.63–2.41 µm | R = 41 |
| 4 | 2.42–3.82 µm | R = 35 |
| 5 | 3.83–4.41 µm | R = 112 |
| 6 | 4.42–5.00 µm | R = 128 |

**The crucial geometry:** the wavelength varies continuously along one spatial axis of each detector. A single exposure therefore gives one narrow band per sky coordinate. A full spectrum requires a stepped sequence of pointings so the source walks across the LVF gradient. The Level 2 products are **discrete spectral images**, not native 3D cubes.

### 3.2 Why blinking is hard

- **6.15″ pixels** blend nearby sources and make the PSF wider at long wavelengths.
- **Low per-channel SNR**: spreading light across 102 narrow bands makes faint Y-dwarfs and KBOs nearly invisible in a single band.
- **Zodiacal foreground**: the `ZODI` model is not subtracted from `IMAGE`; it varies between epochs and will cause full-frame flashing if ignored.
- **Detector artifacts**: persistence ghosts, cosmic rays, crosstalk, saturation, and optical ghosts can look exactly like astrophysical transients.
- **LVF/time coupling**: the 102 channels are acquired sequentially; fast movers and rotating asteroids can smear or mimic spectral features.
- **Sparse epochs**: by November 2026, most sky positions have **2–3 six-month survey epochs**, not dozens. Do not promise more.

### 3.3 What the tool must not misrepresent

- A broadband coadd is a **high-SNR detection image**, not a calibrated flux measurement.
- WCS-WAVE is accurate to ~1 nm and is fine for visualization; `CWAVE`/`CBAND` are the science calibration products.
- Difference imaging is **direct subtraction** of un-normalized coadds; PSF matching was measured but not adopted. ZOGY is not attempted.
- Product fixtures and illustrative spectra are forbidden. Generated test-only inputs are separately inventoried and excluded from runtime.
- No fake ML confidence scores or invented probabilities.

---

## 4. Target catalog and stress tests

For the five catalog targets, all cutout queries use the **Epoch 2025.8 propagated coordinates**; arbitrary user coordinates use the user-supplied position. The UI displays both the reference-epoch and 2025.8 coordinates for catalog targets and draws the proper-motion vector between them.

| Target ID | Target | Class | Reference coordinates (epoch) | Epoch 2025.8 coordinates | Proper motion (mas/yr) | Demo / stress test |
|---|---|---|---|---|---|---|
| `wise_0855` | WISE 0855 (WISE J085510.83−071442.5) | Y4 sub-brown dwarf, ~250 K, 2.28 pc | `133.79513°, −7.24515°` (2010.0 WISE) | **`133.75921°, −7.24216°`** | `−8118, +680` (~8.15″/yr) | Band dropout: invisible in Gaia and Bands 1–4; appears in Bands 5–6; moves ~4.1″ per 6 months. |
| `barnards_star` | Barnard's Star (GJ 699 / HIP 87937) | M4V red dwarf, 1.83 pc | `269.4521°, +4.6934°` (J2000) | **`269.4463°, +4.7676°`** | `−801.6, +10362.4` (~10.39″/yr) | Motion ~5.2″ per 6 months; difference dipole. |
| `eps_indi_b` | Epsilon Indi Ba/Bb | T1 + T6 brown dwarfs, 3.63 pc | `331.04415°, −56.78284°` (J2000) | **`331.0962°, −56.8005°`** | `+3982.0, −2466.8` (~4.68″/yr) | Ba/Bb separated by 0.6″; blended in one 6.15″ pixel; composite CH₄/H₂O spectrum. |
| `rw_aurigae` | RW Aurigae A/B | Classical T Tauri binary, ~156 pc | `76.95607°, +30.40133°` (J2000) | **`76.9561°, +30.4011°`** | `+2.6, −27.4` | Aperiodic disk occultation/dimming; NIR dust excess; spectral shape changes. |
| `r_draconis` | R Draconis (HIP 81014) | Mira AGB, P ≈ 245.6 d | `248.1676°, +66.7550°` (J2000) | **`248.1674°, +66.7548°`** | `−13.7, −31.0` | High-amplitude pulsation near the North Ecliptic Pole; possible saturation/overflow flags. |

### 4.1 Coordinate policy

- Store both `ra_ref`/`dec_ref`/`ref_epoch` and `ra_epoch2025`/`dec_epoch2025` in `backend/core/targets.py`.
- Query IRSA at the **2025.8** coordinates.
- Use `astropy.coordinates.SkyCoord.apply_space_motion` when computing propagated coordinates; do not hand-wave the PM vector.
- WISE 0855's reference epoch is **2010.0** (WISE discovery), not J2000. Label it clearly in the UI.
- Epsilon Indi B is ~6.7′ from ε Indi A; do not confuse the two. The 0.6″ separation is between Ba and Bb, not from A.
- RW Aurigae's declination is `+30°24′04.8″`; do not use the old `+30°24′27″`.

---

## 5. Scope

### 5.1 P0 — must ship

| Feature | Acceptance criterion |
|---|---|
| RA/Dec search + validation | Invalid input shows a helpful error; valid input centers the viewer. **Arbitrary coordinates are the required path; the five targets are shortcuts.** |
| Real SPHEREx data | At least one target loads real DR1/QR3 cutouts, never a development fixture. |
| Temporal blink | Play/pause, step, 1–8 fps, epoch label, loop. |
| Six-detector bands | Each band 1–6 plus an all-band coadd. |
| Five-target tour | All five official targets load and show a meaningful change. |
| Contamination flags | Flags and metadata visible; `BIT_SOURCE` preserved. |
| Public deployment | HTTPS URL works in a fresh browser with no login. |
| URL state | RA, Dec, FOV, bands, epoch, mode encoded and restorable. |

### 5.2 P1 — should ship

| Feature | Acceptance criterion |
|---|---|
| Difference mode | Epoch A − B with a diverging colormap; static stars removed. |
| Spectrum inspector | Dense SPHEREx spectrum (24–72 channels/epoch in this build; the mission has 102 bands) for the five targets; best-effort for arbitrary clicks. |
| Gaia/WISE comparison | Toggleable precomputed SkyView DSS2/WISE reference images or split curtain (Gaia DR3 pins overlay). |
| Stretch/colormap controls | Linear, log, asinh, zscale; at least two colormaps. |
| Artifact Shield | Bitmask-driven badge and overlay; no fake probabilities. |
| Proper-motion reticle | J2000/reference vs. 2025.8 vector overlay. |

### 5.3 P2 — nice to have

- Template cross-correlation (L/T/Y dwarf, asteroid, M-dwarf).
- CSV spectrum export; PNG frame export.
- Guided onboarding tour.
- Mobile-responsive polish.
- Embed iframe snippet.

### 5.4 Non-goals / do not build

- User authentication, accounts, or a database.
- Full-sky HiPS tile generation or HEALPix/Zarr archive.
- ZOGY or optimal transient detection.
- Custom ML models or fake confidence scores.
- 3D volumetric galaxy flythroughs.
- Planet Nine discovery claims.
- A multi-month production system.

### 5.5 Definition of done

A judge can open the URL, load all five targets, load at least one arbitrary RA/Dec, see a clear temporal change, understand at least one band-dependent effect, inspect a spectrum or flags, and share the view. The demo video works even if the live server is cold.

---

## 6. Data strategy

### 6.1 What is available

- **SPHEREx Data Release 1 (DR1) is released (November 2026)** and contains the reprocessed QR2 images. **QR3** is still released weekly. IRSA recommends **DR1 + QR3 over QR2** (verified 2026-11-13).
- The main product is the **Level 2 Spectral Image MEF**, one per detector per pointing: 6 MEFs per pointing, ~70 MB each, 2040 × 2040 pixels, 6 extensions.
- Some observations do not include all six bands; handle missing detectors gracefully.
- **TAP** gives zero-lag access; **SIA2** lags ingestion by ~1 day.
- **Cutouts** are available from the on-prem IRSA copy.
- **AWS Open Data** mirror: bucket `nasa-irsa-spherex`, region `us-east-1`, prefixes `dr1/level2` and `qr3/level2` (verified 2026-11-13; DR1 objects are present).
- **DR1 now includes an all-sky 102-channel cube** (November 2026). It is **not** integrated in the current app; do not claim 102-band spectra until a separate measured integration lands.

### 6.2 Query strategy

**Primary: IRSA TAP**

```sql
SELECT 'https://irsa.ipac.caltech.edu/' || a.uri
         || '?center={ra},{dec}&size={size}' AS cutout_uri,
       p.time_bounds_lower AS mjd_obs,
       p.time_bounds_upper AS mjd_obs_upper,
       p.energy_bandpassname AS detector_band,
       p.planeid,
       a.uri,
       a.contentlength,
       p.datarelease
FROM spherex.artifact a
JOIN spherex.plane p ON a.planeid = p.planeid
WHERE 1 = CONTAINS(POINT('ICRS', {ra}, {dec}), p.poly)
  AND a.producttype = 'science'
  AND a.contenttype = 'image/fits'
ORDER BY p.time_bounds_lower ASC
```

- **Verified against live TAP on 2026-11-08.** `spherex.artifact` and `spherex.plane` exist; the columns used above are present.
- `a.uri` is **relative** (`ibe/data/spherex/...`); prepend `https://irsa.ipac.caltech.edu/`. The `cutout_uri` expression above is correct.
- `p.energy_bandpassname` values are `SPHEREx-D1` … `SPHEREx-D6`.
- Filter `a.producttype = 'science'` and `a.contenttype = 'image/fits'` to exclude calibration artifacts.
- `p.datarelease` is a public-release **date**, not a release label. Detect **DR1** and **QR3** from `a.uri` (`/dr1/`, `/qr3/`). **QR2 is superseded**; do not treat it as the current release.
- TAP endpoint: `https://irsa.ipac.caltech.edu/TAP`; the MVP can use `sync` with `FORMAT=json`.
- **Coverage on 2026-11-13:** DR1 + QR3 only in the live TAP results. WISE 0855 **258 DR1** (no QR3); Barnard's Star **239 DR1 + 119 QR3**; Epsilon Indi B **338 DR1 + 120 QR3**; RW Aurigae **226 DR1 + 109 QR3**; R Draconis **1,638 DR1 + 855 QR3**. Counts are artifacts, not unique visits. See `docs/reference/resource-release-2026-11-13.md` §2.2.

**Fallback: SIA2**

```text
https://irsa.ipac.caltech.edu/SIA?COLLECTION=spherex_dr1&POS=circle+{ra}+{dec}+{radius}&RESPONSEFORMAT=json
```

- Collections: `spherex_dr1`, `spherex_dr1_deep`, `spherex_qr3`, `spherex_qr3_deep`. QR2 is superseded (2026-11-13).
- `RESPONSEFORMAT=VOTABLE` and `RESPONSEFORMAT=json` both work; the JSON is VOTable-in-JSON. The results table includes `access_url`, `cloud_access`, `s_pixel_scale`, `s_resolution`, `t_min`, and `t_max`.
- SIA is a fallback: ingestion lags by about a day. On 2026-11-13, `COLLECTION=spherex_dr1` returned a valid VOTable; WISE 0855 has DR1 coverage and still no QR3 rows.
- Use TAP first; SIA2 only if TAP is unavailable.

**Cutout**

```text
{access_url}?center={ra},{dec}&size={size_deg}
```

- If the access URL already contains a query string, append with `&` instead of `?`.
- **Verified:** both `size=0.02` and `size=0.02d` were accepted by the live service on 2026-11-08. Use the documented no-suffix form, with a `d`-suffix retry if needed. The earlier 503 responses were transient `"Server busy, retry later."` errors, not format errors.
- The service can return HTTP 503 under load. Use timeouts, retries with backoff, and cache successful cutouts.
- A 0.02° **QR2** cutout was 5.06 MB: a 12 × 12 `IMAGE` plus the unmodified 121 × 101 × 101 `PSF`. The PSF cube dominates. At 0.2° the image arrays are ~117 × 117; budget ~6 MB per cutout. A **DR1** cutout carries an `EPSF` table instead (4.0 MB, verified 2026-11-13).
- Practical cutout size: **0.05°–0.2°** (3′–12′); default **0.2°**. The 240 × 240 grid at 3.075″/px covers 0.205°, so 0.2° is the safe maximum for the MVP.

### 6.3 MEF structure

Each MEF has a primary HDU plus six extensions:

| HDU | `EXTNAME` | Content | Units / rules |
|---|---|---|---|
| `hdul[0]` | `PRIMARY` | Header only | **`data is None`; never call `hdul[0].data`.** |
| `hdul[1]` | `IMAGE` | Calibrated surface brightness | MJy/sr; 2040 × 2040; zodiacal light **not** subtracted. |
| `hdul[2]` | `FLAGS` | Per-pixel status/processing bitmask | 32-bit; see §6.4; never mask all non-zero values. |
| `hdul[3]` | `VARIANCE` | Variance of calibrated surface brightness | (MJy/sr)²; use `w = 1 / VARIANCE`. |
| `hdul[4]` | `ZODI` | Modeled zodiacal-light background | MJy/sr; **must be subtracted** from `IMAGE`. |
| `hdul[5]` | `PSF` | 121 PSFs, each 101 × 101, in a cube | Unmodified in cutouts; use the plane matching the target zone. |
| `hdul[6]` | `WCS-WAVE` | Spectral WCS lookup table | 1 row × 3 columns (X, Y, VALUES); pixel → central wavelength/bandwidth. |

**Science nuance:** WCS-WAVE is intended for visualization; it is accurate to ~1 nm. For publication-grade work, use `CWAVE`/`CBAND` from the separate Spectral WCS calibration product. For the 48-hour MVP, WCS-WAVE is sufficient; state that in the UI.

### 6.4 Bitmask policy

**Never** use `flags > 0` or `flags != 0` as a bad-pixel mask. `BIT_SOURCE` (Bit 21) marks known catalog stars and galaxies — exactly the objects users want to see. `BIT_FULLSAMPLE` (Bit 12) is informational.

| Bit | Value | Name | Policy |
|---|---|---|---|
| 0 | 1 | `TRANSIENT` | Warn (cosmic ray / single-frame transient). |
| 1 | 2 | `OVERFLOW` | Warn (near saturation). |
| 2 | 4 | `SUR_ERROR` | Hard mask. |
| 6 | 64 | `NONFUNC` | Hard mask. |
| 7 | 128 | `DICHROIC` | Warn (≥50% attenuation; Bands 3–4). |
| 9 | 512 | `MISSING_DATA` | Hard mask. |
| 10 | 1024 | `HOT` | Hard mask. |
| 11 | 2048 | `COLD` | Hard mask. |
| 12 | 4096 | `FULLSAMPLE` | Info only. |
| 14 | 16384 | `PHANMISS` | Hard mask. |
| 15 | 32768 | `NONLINEAR` | Hard mask. |
| 17 | 131072 | `PERSIST` | Warn (latent ghost). |
| 19 | 524288 | `OUTLIER` | Warn. |
| 20 | 1048576 | `CROSSTALK` | Warn. |
| 21 | 2097152 | `SOURCE` | **Never mask**; exclude only from background estimation. |
| 22 | 4194304 | `GHOST` | Warn. |
| 23 | 8388608 | `GHOST_FPA` | Warn (currently unused; subsumed into `GHOST_EXT`; retained for forward compatibility). |
| 24 | 16777216 | `GHOST_EXT` | Warn. |
| 25 | 33554432 | `STREAK` | Warn (satellite/meteor). |
| 26 | 67108864 | `BLOOM` | Hard mask. |
| 27 | 134217728 | `SNOWBALL` | Hard mask. |
| 28 | 268435456 | `HALO` | Hard mask. |
| 29 | 536870912 | `SATELLITE_HALO` | Hard mask. |

**Definitions:**

```python
HARD_BAD_MASK = (
    (1 << 2) | (1 << 6) | (1 << 9) | (1 << 10) | (1 << 11) |
    (1 << 14) | (1 << 15) | (1 << 26) | (1 << 27) | (1 << 28) | (1 << 29)
)

ARTIFACT_WARNING_MASK = (
    (1 << 0) | (1 << 1) | (1 << 7) | (1 << 17) |
    (1 << 19) | (1 << 20) | (1 << 22) | (1 << 23) | (1 << 24) | (1 << 25)
)

BIT_SOURCE = 1 << 21
BIT_FULLSAMPLE = 1 << 12
```

**Verify the full Table 16 (Image pixel flags used in spectral images at Level 2) against the Explanatory Supplement before coding.** Table 10 is a different table (Non-Overflow Bloom Pixel Candidates). The current supplement (v2.0, 2026-08-25) defines 23 named bits; bit 23 (`GHOST_FPA`) is currently unused but is retained in the warning mask for forward compatibility. If a bit differs, update `backend/core/flags.py` and its tests together. The MVP masks above cover the known demo-critical cases.

**Photometry nuance:** `DICHROIC` (bit 7) is a warning for the displayed image, but the supplement describes these pixels as low-throughput and "not usefully calibrateable or of value for photometry." For coadds and spectrophotometry, exclude them from flux measurements or apply the throughput correction; do not treat them as clean pixels.

### 6.5 Preprocessing pipeline

1. **Query** TAP (primary) or SIA2 (fallback) for observations overlapping the target.
2. **Group** by detector and by **6-month survey epoch**. Optional: expose individual visits as sub-frames if time permits.
3. **Download cutouts** in parallel (`max_workers=8`, timeouts, retries with backoff).
4. **Parse by name**: `IMAGE`, `FLAGS`, `VARIANCE`, `ZODI`, `PSF`, `WCS-WAVE`.
5. **Subtract `ZODI`**: `img_zodi_sub = IMAGE - ZODI`.
6. **Estimate and subtract local background** on source-masked, artifact-masked pixels using `photutils.background.Background2D` (or `sep.Background` for small cutouts). Mask `HARD_BAD_MASK | ARTIFACT_WARNING_MASK | BIT_SOURCE` for the background estimate only.
7. **Mask hard-bad pixels** to `NaN`; preserve `BIT_SOURCE` in the image. For photometry/coadds, also exclude `ARTIFACT_WARNING_MASK` pixels (including `DICHROIC`) or apply the throughput correction; this is the `PHOTOMETRY_EXCLUDE_MASK`.
8. **Reproject** `IMAGE`, `VARIANCE` (→ weights), and warning flags onto a common **north-up TAN WCS** grid: 240 × 240 pixels, 3.075″/px (2× supersampled native).
9. **Coadd** the detector's channels with inverse-variance weights: `I = Σ(w_i I_i) / Σw_i`.
10. **Normalize across epochs** for blinking: per band, use the 99.5th percentile of static `BIT_SOURCE` pixels (excluding the target aperture/wings, hard-bad, and warning pixels), referenced to a global reference epoch with scale 1.0 (per-band earliest fallback; `reference_epoch="mixed"` when refs differ); clamp the scale to [0.5, 2.0], fall back to an all-pixel 99.5th percentile if too few static sources survive, and record the scales in the manifest; scale the variance by `scale²` before the coadd. Keep the raw flux statistics for difference mode. Coadds use the normalized band frames and the same per-band scales; no separate coadd scale.
11. **Difference**: `E2 − E1` by direct subtraction; PSF matching was measured but not adopted. No ZOGY claim.
12. **Encode** lossless 8-bit WebP frames plus a JSON manifest. Keep per-frame 5th/50th/99.5th flux percentiles.
13. **Spectra**: for each of the five targets, run aperture photometry across all available channels; use WCS-WAVE (`sip=None`); convert to μJy; write JSON.
14. **Cache** golden frames, live frames, and spectra. No synthetic datasets are permitted in the product or its cache packaging.

### 6.6 Flux conversion

Native pixel solid angle: `Ω_pix = (6.15″)² = 37.8225 arcsec² = 8.890 × 10⁻¹⁰ sr`.

```text
F_pix [μJy] = I_pix [MJy/sr] × Ω_pix [sr] × 1e12
```

Equivalent:

```text
F_pix [μJy] = I_pix [MJy/sr] × 23.50443 × Ω_pix [arcsec²]
```

Sanity check: 1 MJy/sr over one native 6.15″ pixel → **~889 μJy**. Use the solid-angle pixel map if time permits; otherwise the nominal pixel area is acceptable for the demo.

### 6.7 Epoch policy

- **Primary timeline:** 6-month survey epochs (e.g., May–Oct 2025, Nov 2025–Apr 2026, May–Oct 2026). Most targets have 2–3.
- **Optional:** individual visits within an epoch, clustered by a few days, for fast movers. Label them "visits," not "epochs."
- The UI shows the actual available epochs, not a hardcoded four.
- If only one epoch exists, show a single-epoch view with a clear "no second epoch available" notice; do not fake a blink.
- Epoch IDs, the reference epoch, and adjacent difference pairs are computed on the full available set. The `epochs` filter only filters the response; a filtered single-epoch view still uses the global normalization.

### 6.8 Saved target data and real-only packaging

| Priority | Source | Behavior |
|---|---|---|
| 1 | `golden_cache/` for the five targets | Real DR1+QR3 saved data, served first; works offline in milliseconds. |
| 2 | Live IRSA TAP + cutouts | Arbitrary RA/Dec; bounded single-epoch path. |
| Retired | `frontend/public/mock/`, `golden_cache/fallback_*` | Removed by Phase 1. Never packaged or served; there is no mock opt-in. |

The golden cache contains WebP frames, difference maps, flag overlays, spectra,
telemetry sidecars, and a manifest for all five targets. It was generated
**during the hackathon** from real data, not before. Normal operation never
substitutes a fixture: a live failure returns a clean error instead.

### 6.9 Attribution

> "This publication makes use of data products from the Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer (SPHEREx), which is a joint project of the Jet Propulsion Laboratory and the California Institute of Technology, and is funded by the National Aeronautics and Space Administration."

Also cite the IRSA DOI for DR1 (images) and QR3, acknowledge Astropy, Gaia, and WISE, and distinguish historical screenshots and test inputs from real observational products in the inventory. The QR2 DOI is historical: QR2 is superseded and appears only in the revision-2 rollback cache.

### 6.10 Reuse the official IRSA tutorials

Do not reinvent the low-level parsing. Adapt the logic from these IRSA notebooks:

- **`spherex-cutouts`** — parallel TAP cutout fetching and WCS-WAVE lookup.
- **`spherex-source-discovery-tool-demo`** — ZODI/background subtraction, reprojection, and difference imaging.
- **`spherex-psf`** — PSF/ePSF extraction and the correct PSF plane for a cutout position.

The tutorials are linked from `https://caltech-ipac.github.io/irsa-tutorials/`.

### 6.11 Verified data-access facts (2026-11-08; DR1 update 2026-11-13)

A pre-event verification pass against the live services and a real QR2 cutout confirmed the 2026-11-08 facts below. The **2026-11-13 DR1 recheck** changed HDU 5 and the release vocabulary:

- **HDU map:** `PRIMARY` is empty; `IMAGE`, `FLAGS`, `VARIANCE`, `ZODI`, and `WCS-WAVE` are present by `EXTNAME`. HDU 5 is the **`PSF` cube in QR2** or the **`EPSF` binary table in QR3/DR1** (441 rows full frame / 451 in the tested cutout; 33 × 33, 5× oversampled). Never assume `hdul["PSF"]`.
- **DR1 cutout verified 2026-11-13:** `IMAGE`, `FLAGS` (returned decompressed as int32), `VARIANCE`, `ZODI`, `EPSF`, `WCS-WAVE`; 4,037,760 bytes for a 0.02° cutout, 8.6 s.
- **Spectral WCS:** `WCS(hdul["IMAGE"].header, fobj=hdul, key="W")` works; `sip=None` is mandatory; `pixel_to_world(6, 6)` returned 2.363159 µm (bandwidth 0.058551 µm) for a D3 cutout.
- **`BIT_SOURCE` is real:** the test cutout's `FLAGS` contained `2097152` (bit 21) on source pixels. `flags != 0` would have masked the target.
- **Flags table:** the correct table is **Table 16**, not Table 10; `GHOST_FPA` (bit 23) is defined but currently unused.
- **Cutout format:** both `size=0.02` and `size=0.02d` work; 503s are transient. A QR2 cutout includes the PSF cube; a DR1 cutout includes the `EPSF` table instead. Both are a few MB even at small sizes.
- **Coverage (2026-11-13):** WISE 0855 is **DR1-only** (no QR3); the other four targets have **DR1 + QR3**. QR2 is superseded. See `docs/reference/resource-release-2026-11-13.md` §2.2.
- **WISE 0855 coordinates:** the 2025.8 position is `133.75921°, −7.24216°`; the earlier `133.76010°, −7.24220°` matched 2025.4. The other four were checked against Gaia DR3: Barnard's Star and RW Aurigae confirm the catalog PM; Epsilon Indi B has no Gaia B source (Gaia A is close); R Draconis's PM is low-confidence.

Full report, query recipes, and the November 13 checklist: `docs/verification/pre-event-verification.md`.

---

## 7. Architecture

### 7.1 Diagram

```text
┌────────────────────────────────────────────────────────────────────┐
│ Browser — React 18 + TypeScript + Vite                             │
│                                                                    │
│  Search / URL ──┐   ┌──────────────────────┐   ┌────────────────┐ │
│                 ├──▶│ BlinkCanvas (Canvas2D)│──▶│ SpectrumDrawer │ │
│  Target tour ───┘   │ ImageBitmap ring      │   │ ArtifactShield │ │
│                     │ LUT, diff, reticle    │   │ CrossMission   │ │
│                     └──────────▲───────────┘   └───────▲────────┘ │
│                                │ JSON manifest + WebP   │          │
└────────────────────────────────┼───────────────────────┼──────────┘
                                 │ HTTPS                 │
┌────────────────────────────────▼───────────────────────▼──────────┐
│ FastAPI service (Docker, 2 GB RAM, persistent /data/cache)         │
│                                                                    │
│  /api/v1/health   /api/v1/targets   /api/v1/sky   /api/v1/spectrum │
│                                                                    │
│  IRSA client (TAP primary, SIA2 fallback)                          │
│  Reduction: Astropy + reproject + photutils + sep                  │
│  Cache: diskcache + golden_cache                                   │
└────────────────────────────────┬───────────────────────────────────┘
                                 │ TAP / SIA2 / cutouts / S3
┌────────────────────────────────▼───────────────────────────────────┐
│ NASA/IPAC IRSA — SPHEREx DR1+QR3 (historical QR2)                  │
│ https://irsa.ipac.caltech.edu/TAP                                  │
│ https://irsa.ipac.caltech.edu/SIA?                                 │
│ AWS: nasa-irsa-spherex (us-east-1)                                 │
└────────────────────────────────────────────────────────────────────┘
```

### 7.2 Backend

- **FastAPI** (Python 3.11) + async endpoints.
- **Astropy** for FITS/WCS/units; **reproject** for alignment; **photutils** and **sep** for background/photometry; **NumPy/SciPy** for arrays.
- **Pillow** for WebP encoding; **diskcache** for caching.
- **`ThreadPoolExecutor(max_workers=8)`** for cutout downloads; timeouts and retries.
- **Docker** single container; serve the built frontend via `StaticFiles` to avoid CORS.
- **Deployment:** Railway or Fly.io, 2 GB RAM minimum, persistent volume at `/data/cache`.

### 7.3 Frontend

- **React 18 + TypeScript + Vite**; **Tailwind CSS**; **Zustand** for state.
- **Custom dual-buffered Canvas 2D** for the blink viewport; pre-decode frames into `ImageBitmap` objects; one `requestAnimationFrame` loop; no React re-mount per tick.
- **Plotly** or **uPlot** for the spectrum; **Framer Motion** for panel transitions (respect reduced motion).
- **SkyView** (DSS2 Red, WISE 3.4/4.6) for real reference cutouts on the same WCS. CDS `hips2fits` was unreachable in the build environment; the committed overlays are precomputed SkyView data.
- **Aladin Lite v3** is optional, only as a picture-in-picture/split-curtain context layer; it is not the primary blink renderer.

### 7.4 API summary

Full immutable schemas are in `AGENTS.md` §3. Endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/health` | Liveness/version. |
| `GET /api/v1/targets` | The five target metadata records. |
| `GET /api/v1/sky?ra=&dec=&size=&target_id=` | Frame manifest for a target or live position. |
| `GET /api/v1/spectrum?ra=&dec=&target_id=` | Dense SPHEREx spectrum (24–72 channels/epoch; best-effort for arbitrary clicks). |
| `GET /api/v1/assets/{target_id}/{filename}` | Cached WebP/JSON assets. |

### 7.5 Performance targets

| Metric | Target |
|---|---|
| First page interactive | < 3 s on venue Wi-Fi. |
| Cached frame load | < 300 ms. |
| Golden target manifest | < 80 ms. |
| Cold cutout generation | Bounded by the live budget: 60 s TAP, 120 s sky deadline, 130 s frontend timeout (verified random field 39.6 s). |
| Blink rendering | 60 FPS; 4–8 FPS blink. |
| Spectrum (precomputed) | < 100 ms. |
| Live spectrum | Bounded by the 90 s live spectrum budget, with progress UI. |
| Initial payload | < 5 MB; lazy-load bands/epochs. |

### 7.6 Deployment and resilience

- One public HTTPS URL; no login; no API key.
- Keep-alive ping during judging; 2 GB RAM; persistent cache.
- Health check and error banners.
- The five catalog targets use the committed golden cache and work even if IRSA is unavailable; arbitrary coordinates return a clean error when IRSA is down. There is no automatic fixture mode.
- Record the demo video on Day 2 morning; do not rely on the live server alone.

---

## 8. Feature specifications

### 8.1 Search and URL state

- Inputs: RA (hours or degrees), Dec (degrees), optional FOV (0.05°–0.2°, default 0.2°).
- For catalog targets, the FOV control crops the precomputed 0.205° full grid (0.2° nominal); it does not regenerate assets. For arbitrary positions, FOV sets the cutout size and is part of the live cache key.
- Parse sexagesimal and decimal; validate ranges; inline errors.
- URL:

```text
?ra=133.75921&dec=-7.24216&size=0.2&target=wise_0855&bands=5,6&epoch=2025_E1&mode=blink&fps=4&diff=0
```

- Debounce updates; `Copy link`; `Embed` iframe snippet; restore on load.

### 8.2 Blink canvas

- Play/pause; step forward/back; 1–8 fps (default 4); ping-pong loop.
- Epoch label/date; progress dots.
- Keyboard: space = play/pause; arrows = step; `D` = difference; `F` = flags; `1–6` = bands; `S` = share.
- Preload next frame; optional cross-fade (default off for crisp blinking).
- **Photosensitivity:** default 4 fps, cap 8 fps, honor `prefers-reduced-motion`, no full-screen white flashes.

### 8.3 Band pills and coadds

- Six pills with the official ranges and resolving powers.
- Click = solo; Shift-click/drag = multi-select; `All` = inverse-variance coadd.
- Presets:
  - **Y-dwarf thermal:** Bands 5 + 6.
  - **Water ice:** Band 4.
  - **Moving dipole:** difference mode.
  - **Optical comparison:** Gaia overlay, SPHEREx off.
- Show effective wavelength range and native pixel scale.
- Soloing/filtering bands changes only the six band frames; `all`, `thermal`, and the Artifact Shield/overlay remain available.

### 8.4 Difference mode

- MVP difference mode compares **adjacent epochs only** (E2−E1, E3−E2, …); do not promise arbitrary A/B pairs. Compute A−B on the common WCS.
- Diverging colormap: blue = negative, red = positive, white = zero.
- Differences are direct subtraction; PSF matching was measured but not adopted after failing the residual-improvement criterion.
- Label "simple difference — artifacts possible."
- For moving objects, show the positive/negative dipole.

### 8.5 Spectrum inspector

- Click a source or use target coordinates.
- X: 0.75–5.00 µm; Y: flux (μJy or relative).
- Use WCS-WAVE (`sip=None`) for the MVP; note the ~1 nm accuracy.
- Error envelope from `VARIANCE`; flagged channels marked.
- Overlay features: H₂O (1.4, 1.9, 2.7, 3.1 µm), CH₄ (1.15, 1.65, 2.2, 3.3 µm), CO₂ (4.27 µm), CO (2.3, 4.67 µm), silicate dust.
- Five targets: precomputed clean spectrum. Arbitrary clicks: best-effort with a "low confidence" badge.
- Spectra use un-normalized, ZODI/background-subtracted frames; the blink normalization is not applied. `target_id` follows the 1.0″ rule; `epoch_id` filters only.
- Template matching (P2): simple correlation score, not a fake probability.

### 8.6 Artifact Shield

- Panel: collection/release, detector, epoch, exposure, WCS center, pixel scale, units, flag legend.
- Flag overlay: red pixels for `ARTIFACT_WARNING_MASK`; toggle.
- Traffic-light badge:
  - **NOMINAL:** no warning flags; `BIT_SOURCE` may be set.
  - **CAUTION:** dichroic edge, minor outlier, `artifact_pixel_fraction > 0.01`, or HALO in display-only mode. A nearby bright source may be noted in the metadata but does not change the flag-based status.
  - **ALERT:** persistence, transient, overflow, crosstalk, ghost, or streak.
- Copy: "Flagged pixels present — possible detector artifact, not a confirmed astrophysical transient."
- No invented probabilities.

### 8.7 Cross-mission curtain

- Draggable vertical split between SPHEREx and Gaia/DSS2 optical or WISE mid-IR.
- Use precomputed SkyView DSS2/WISE overlays on the same WCS; no live HiPS/CDS dependency.
- WISE 0855 demo: Gaia side is empty; SPHEREx Bands 5–6 show a source.
- Aladin Lite optional as a PiP context map; not required.

### 8.8 Target tour

Five cards:

1. **WISE 0855** — "The coldest known object outside the Solar System."
2. **Barnard's Star** — "Watch a nearby star move."
3. **Epsilon Indi B** — "Two brown dwarfs in one pixel."
4. **RW Aurigae** — "A young star with a turbulent disk."
5. **R Draconis** — "A pulsating giant."

Each card: one-sentence story, what to look for, recommended bands, expected phenomenon.

### 8.9 Export and sharing

- Copy URL; download current frame PNG; download spectrum CSV; embed snippet.
- Share text template for forums/Zooniverse.

---

## 9. 48-hour execution plan

### 9.1 Pre-event (November 8–13) — research only

The official FAQ states: **"Teams are not allowed to begin working on the challenges prior to the hackathon."** Do not build the app, UI, backend, or golden cache before the start.

| Date | Task | Output |
|---|---|---|
| Nov 8–9 | Read official challenge, FAQ, judging guide, IRSA docs. | Shared notes; confirmed requirements. |
| Nov 9–10 | Learn the TAP/SIA2/cutout APIs, Astropy/reproject, and Canvas basics. | Throwaway tutorials, not project code. |
| Nov 10–11 | Document the query path and MEF HDUs; test data access only if your Local Lead confirms it is allowed. | Verified query recipe or sample cutout. |
| Nov 11–12 | Define roles, deployment accounts, demo outline. | Role sheet; accounts ready. |
| **Nov 13** | **NASA resources drop.** Inspect data links, submission guide, judging guide. | Final scope lock; updated data plan. |
| Nov 13 evening | Sleep. | Fresh team. |

**2026-11-08 update:** TAP/SIA2/cutout behaviour, Table 16, and the five target coordinates have been verified; see `docs/verification/pre-event-verification.md`. No challenge code was written.

**2026-11-09 exception:** The Berlin Local Event confirmed in writing that registered participants may start before 14 November; see `docs/reference/event-compliance.md`. Conditions: attendance on both event days and timely submission. O1/B1/F1/S1 may start now.

**2026-11-13 update:** the Resources tab was inspected (NASA + CSA). **DR1 is released** and DR1+QR3 supersede QR2; scope is locked to **B10 → S7** data refresh plus I1/I2 submission work. See [`docs/reference/resource-release-2026-11-13.md`](docs/reference/resource-release-2026-11-13.md).

### 9.2 Roles

| Role | Responsibilities |
|---|---|
| **Lead / Orchestrator** | Scope, integration, API contract, judging narrative, demo. |
| **Backend/data** | IRSA client, FITS pipeline, coadds, spectra, cache, deployment. |
| **Frontend** | Canvas, timeline, band pills, spectrum, shield, URL state. |
| **Science/QA/demo** | Golden cache, validation, tests, video, README. |

With 3 people: merge design into frontend; lead handles QA/demo. With 2 people: cut spectra and cross-mission curtain; focus on blink, bands, the arbitrary-coordinate path, and the five-target checks.

### 9.3 Hour-by-hour

Assume H+0 is the event start; adjust to the Local Event schedule.

| Window | Work | Owner | Gate |
|---|---|---|---|
| **H+0–2** | Team sync, scope lock, monorepo, deploy "hello world." | All | Public URL exists. |
| **H+2–6** | Data spike: TAP/SIA2 → cutout → FITS parse for WISE 0855; build golden cache script. | Backend + science | One real frame displayed. |
| **H+6–12** | Generic `/api/v1/sky` + `/api/v1/targets` + Canvas viewer + arbitrary RA/Dec search (live path). | Backend + frontend | Arbitrary-coordinate search works end-to-end. |
| **H+12–18** | Blink player, epochs, six band pills, coadds. | Frontend | **H+12 demo:** blink one target. |
| **H+18–24** | Five-target tour, URL state, Artifact Shield, proper-motion reticle. | All | **H+24 demo:** all five targets load. |
| **H+24–32** | Difference mode + spectrum drawer for the five targets. | Backend + frontend | Dipole + spectrum visible. |
| **H+32–38** | Live-query hardening (timeouts, retries, fallback), cross-mission curtain, polish. | Frontend + backend | Arbitrary-coordinate path is reliable; curtain works or is cut. |
| **H+38–42** | Accessibility, performance, bug fixes. **Feature freeze at H+42.** | All | Frozen. |
| **H+42–46** | Demo video, README, submission. | Science/QA + lead | Submitted. |
| **H+46–48** | Rehearse, buffer, final checks. | All | Done. |

### 9.4 Go/no-go gates

- **H+6:** If real SPHEREx data cannot be fetched, switch to a manually fetched sample and the golden-cache path; do not add an automatic fixture fallback. Do not spend more than 6 hours on data access.
- **H+12:** If one target does not blink end-to-end, freeze new feature work and fix the pipeline; do not start the five-target tour on a broken core.
- **H+24:** If fewer than five targets load, ship the three that work and expand if time permits.
- **H+32:** If spectra are not working, drop to "spectrum coming soon" and keep blink/difference. Spectra are optional.
- **H+38:** If the arbitrary-coordinate path is unstable, restrict the FOV/rate and add clear loading/error states; do not ship a five-target-only tool, because arbitrary RA/Dec is the official requirement.
- **H+42:** Feature freeze. No new features.
- **H+46:** Submit; do not wait for the deadline.

### 9.5 Sleep and integration

- Rotate sleep: at least 5 hours per person on Day 1.
- Integration checkpoints at H+12, H+24, H+32, H+38; merge to `main` only through the Orchestrator.
- Keep a shared "known good" branch and a recorded demo backup.

---

## 10. Scientific validation

### 10.1 Astrometry

- Use the WCS in the MEF headers; reproject to a common TAN grid.
- Validate against at least three Gaia stars; centroid residual < 1 native pixel (6.15″).
- Display WCS center and pixel scale in the metadata panel.
- Check the proper-motion vector direction against the catalog PM.

### 10.2 Photometry and coadds

- Inverse-variance weighting; propagate variance. Reprojected variance is approximate (interpolation underestimates noise); apply a variance floor and label uncertainties approximate.
- Mask only `HARD_BAD_MASK`; exclude `BIT_SOURCE` from background estimation, never from the image.
- `DICHROIC` pixels are low-throughput; exclude them from spectrophotometry/coadds or apply the throughput correction. Warning bits alone do not make a spectral channel bad; report `clean_fraction`/`is_used_in_photometry`.
- Use aperture photometry with a local sky annulus.
- Keep MJy/sr internally; label plots clearly.
- Do not claim absolute spectrophotometry for arbitrary sources; label "relative spectrum" unless calibrated.

### 10.3 Five-target test card

| Target | Expected signal | What the demo shows | Pass condition |
|---|---|---|---|
| **Barnard's Star** | ~10.39″/yr; ~5.2″ per 6 months | Position shift; difference dipole | Shift visible; direction matches PM. |
| **Epsilon Indi B** | Ba/Bb 0.6″ apart; blended at 6.15″ | One unresolved source; the bright primary is ~6.7′ away, outside the default 0.2° field, so the demo explains the separation; composite T1+T6 spectrum | User understands "blended, not resolved." |
| **WISE 0855** | Thermal-infrared only; strongest in Bands 5–6; 8.15″/yr | Vanishes in Bands 1–4 and Gaia; appears in Bands 5–6 | Band-dependent detection is obvious. |
| **RW Aurigae** | Aperiodic dimming (may be quiescent); NIR excess | Difference mode; spectral shape change; if quiescent, show the NIR excess | Epoch-to-epoch brightness or spectral-shape change visible; otherwise the NIR excess is explained. |
| **R Draconis** | P ≈ 245.6 d; large amplitude | Bright/dim phases; saturation flags | Variability + flags visible. |

### 10.4 Known limitations to state

- 6.15″ pixels blend close sources.
- Single-band images can be noise-dominated; coadds help.
- SPHEREx artifacts are real; flags are not perfect.
- DR1/QR3 coverage may not include every epoch for every target.
- WCS-WAVE is visualization-grade; `CWAVE`/`CBAND` is the science-grade alternative.
- The tool is a visual explorer, not a discovery pipeline.

---

## 11. UX and design system

### 11.1 Layout

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Logo  [RA/Dec or name]  [FOV]  [Share] [Help]                        │
├───────────────┬──────────────────────────────────────┬───────────────┤
│ Benchmark     │                                      │ Artifact      │
│ tour          │        BLINK CANVAS                  │ Shield        │
│               │   (frames, reticle, vector)          │               │
│ Story card    │                                      │ Cross-mission │
│               │                                      │ curtain       │
├───────────────┴──────────────────────────────────────┴───────────────┤
│ ◀ ▶  epoch dots  1x 2x 4x  [Diff]  [B1..B6] [All] [Presets]          │
├──────────────────────────────────────────────────────────────────────┤
│ Spectrum drawer (collapsible): flux vs wavelength, features, flags    │
└──────────────────────────────────────────────────────────────────────┘
```

### 11.2 Visual tokens

| Token | Value |
|---|---|
| `--bg-void` | `#06080E` |
| `--bg-hud` | `rgba(13, 18, 30, 0.78)` + `backdrop-filter: blur(16px)` |
| `--bg-elevated` | `#141C2E` |
| `--border-subtle` | `rgba(148, 163, 184, 0.14)` |
| `--border-active` | `rgba(56, 189, 248, 0.65)` |
| Band 1 | `#38BDF8` |
| Band 2 | `#34D399` |
| Band 3 | `#A3E635` |
| Band 4 | `#FBBF24` |
| Band 5 | `#FB923C` |
| Band 6 | `#F43F5E` |
| Shield nominal | `#10B981` |
| Shield caution | `#F59E0B` |
| Shield alert | `#EF4444` |

- **Typography:** Space Grotesk (headers), Inter (body), JetBrains Mono (coordinates/fluxes, `tabular-nums`).
- **Dark only:** high contrast, no pure-white flashes.
- **Glassmorphism:** translucent HUD panels; keep text readable.

### 11.3 Components

- `BlinkCanvas.tsx` — dual-buffered ImageBitmap ring, LUT colormaps, contrast/bias, zoom/pan, reticle, proper-motion vector, pixel footprint box.
- `TimelineDock.tsx` — play/pause, speed, loop, difference, six band pills, presets.
- `ArtifactShield.tsx` — badge, flag overlay, plain-language explanation.
- `SpectrumDrawer.tsx` — spectrum plot, error bars, molecular markers, template overlay, CSV export.
- `CrossMissionCurtain.tsx` — draggable optical/mid-IR comparison.
- `useUrlState.ts` — bidirectional URL sync.
- `TargetTour.tsx` — five cards and camera flights.

### 11.4 Accessibility

- WCAG AA contrast; focus rings; keyboard navigation; ARIA labels.
- `prefers-reduced-motion`: disable autoplay and cross-fades.
- Photosensitivity: default 4 fps, cap 8 fps, warning.
- Alt text and a data-table fallback for the spectrum.
- Mobile: responsive layout; timeline collapses; canvas fits width.

### 11.5 Copy

- "Blink through time."
- "What changed between these epochs?"
- "This source is only visible in the thermal infrared."
- "Two brown dwarfs are hidden inside this one SPHEREx pixel."
- "Flagged pixels: possible detector artifact, not a confirmed discovery."
- "This is a visual explorer. Follow-up observations confirm discoveries."

---

## 12. Demo and submission

### 12.1 Two-minute demo script

| Time | Visual | Voiceover |
|---|---|---|
| 0:00 | Title + one-sentence promise | "SPHEREx maps the sky in 102 infrared bands every six months. We made it blink." |
| 0:10 | WISE 0855, Bands 5+6 | "This is the coldest known object outside the Solar System. It is invisible in optical light." |
| 0:25 | Gaia blank → Band 6 source | "Gaia sees nothing. SPHEREx's thermal infrared sees it immediately." |
| 0:40 | Barnard's Star blink | "Barnard's Star moves nearly a full SPHEREx pixel every six months." |
| 0:55 | Difference mode | "Subtract the epochs and the static stars disappear; the moving star remains as a dipole." |
| 1:10 | Epsilon Indi B | "Two brown dwarfs, 0.6 arcseconds apart, blend into one 6.15-arcsecond SPHEREx pixel." |
| 1:25 | Spectrum drawer | "Click a source for a dense SPHEREx spectrum, with flags and molecular features." |
| 1:40 | RW Aurigae / R Draconis | "Young stars can dim; giant stars pulsate. The tool shows both." |
| 1:50 | URL share + architecture | "Every view is a URL. Real NASA data, served as lightweight frames, in any browser." |
| 2:00 | End card | "SPHEREx SkyBlink — anyone can explore the infrared sky." |

### 12.2 Submission checklist

- [ ] Public HTTPS URL, no login.
- [ ] Public repository with README and setup instructions. (Repo exists at <https://github.com/tureisD/SkyBlink>, currently **private**; make it public or grant judge access if required.)
- [ ] ~2-minute demo video (public hosting) or a slide deck of ≤7 slides if the guide allows.
- [ ] Project description: problem, solution, data, impact.
- [ ] Team members and roles.
- [ ] Data attribution and acknowledgments.
- [ ] Known limitations and future work.
- [ ] SI/LLM usage disclosure (required by the 2026 FAQ).
- [ ] Screenshots for judges who cannot load the live site.
- [ ] Open-source license (MIT or BSD-3-Clause).
- [ ] Submission completed before the deadline.

### 12.3 README outline

1. What it is / screenshot.
2. Live demo URL.
3. The five targets and what to look for.
4. How it works (TAP/SIA2 → cutouts → coadds → WebP).
5. Data sources and attribution.
6. How to run locally.
7. Limitations.
8. Team.

---

## 13. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| TAP schema/columns differ from the draft | Medium | High | Verified 2026-11-08; keep SIA2 fallback; recheck on Nov 13/14. |
| IRSA outage or slow cutouts | Medium | High | Golden cache; AWS mirror; `?demo=1`; recorded video; retries/backoff. |
| Cutout service returns transient 503 "Server busy" | Medium | Medium | Retries with backoff; cache successful cutouts; golden cache. |
| WISE 0855 has no QR3 coverage | Medium | Low | DR1 now covers WISE 0855 (258 artifacts on 2026-11-13); refresh the cache to DR1 and label it honestly. |
| Missing epochs for a target | Medium | Medium | Query DR1+QR3; show available epochs honestly; do not fake a blink. |
| Cutout size/volume too large | Medium | Medium | Clamp to 0.2°; use 0.05°–0.1° for live queries; cache; limit concurrency. |
| `BIT_SOURCE` over-masking | Medium | High | Use `HARD_BAD_MASK` only; tests; code review; grep gate. |
| `hdul[0].data` crash | Medium | High | Access by `EXTNAME`; tests; grep gate. |
| WCS/SIP bug corrupts spectra | Medium | High | `spectral_wcs.sip = None`; validate against IRSA tutorial; unit test. |
| ZODI/background mismatch causes flicker | High | High | Subtract ZODI + local background; shared cross-epoch normalization; visual check. |
| Coordinate propagation error | Medium | High | Use `apply_space_motion`; verify against SIMBAD; query 2025.8. |
| Spectra too slow | High | Medium | Precompute five targets; 24-cutout subset for live; drop if needed. |
| Deployment cold start/OOM | Medium | High | 2 GB RAM; keep-alive; persistent cache; paid tier for the weekend. |
| Cross-mission reference service failure | Medium | Medium | Real SkyView overlays are precomputed and committed; if a key is absent, the curtain hides that side instead of inventing a reference. |
| Scope creep | High | High | P0 lock; feature freeze H+42. |
| Sleep deprivation | High | Medium | Rotations; 5-hour minimum; no all-nighters both nights. |
| Open-source/license/submission mismatch | Low | High | Check Nov 13 guide; MIT license; prepare repo/video/URL. |
| Development fixture presented as real | Low | High | Product fixtures removed; explicit false provenance required; package scan and retired-namespace 404 checks. |
| Photosensitivity/accessibility issue | Low | Medium | 4 fps default; cap 8; reduced motion; warning. |

---

## 14. Verification checklist for November 13

### 14.1 Resolved by the audit (recheck if the guide differs)

- Dates: November 14–15, 2026.
- Server-side processing is permitted; the tool must be publicly accessible.
- SIA collections: `spherex_dr1`, `spherex_dr1_deep`, `spherex_qr3`, `spherex_qr3_deep`. QR2 is superseded (2026-11-13).
- HDU mapping: `hdul[0]` empty; `IMAGE`, `FLAGS`, `VARIANCE`, `ZODI`, `WCS-WAVE` by `EXTNAME`. HDU 5 is `PSF` in QR2 but **`EPSF` in QR3/DR1**. Confirmed on real QR2 (2026-11-08) and DR1 (2026-11-13) cutouts.
- `BIT_SOURCE` = Bit 21; never mask it. Confirmed on a real cutout: source pixels carry bit 21.
- `spectral_wcs.sip = None` is mandatory. Confirmed: `WCS(..., key="W")` + `sip=None` returns wavelengths.
- **TAP schema/columns confirmed (2026-11-08):** `spherex.artifact` + `spherex.plane`; `a.uri` is relative; `p.energy_bandpassname` is `SPHEREx-D1`…`D6`; filter `a.producttype='science'` and `a.contenttype='image/fits'`.
- **Cutout format confirmed (2026-11-08, DR1 rechecked 2026-11-13):** both `size=0.02` and `size=0.02d` are accepted; 503s are transient "Server busy" responses. DR1 cutouts return `EPSF` instead of `PSF` and a decompressed `FLAGS` image.
- **Flags table confirmed (2026-11-08):** the correct table is **Table 16**, not Table 10; `GHOST_FPA` (bit 23) is defined but currently unused.
- **Coverage (2026-11-13):** all five targets have DR1 coverage; Barnard's Star, Epsilon Indi B, RW Aurigae, and R Draconis also have QR3. WISE 0855 is **DR1-only** (no QR3). QR2 is superseded.
- **WISE 0855 2025.8 coordinate corrected:** `133.75921°, −7.24216°` (the earlier value matched 2025.4). The other four were checked against Gaia DR3; see `docs/decisions/o1-contract-decisions.md` §10–11.
- **DR1 all-sky 102-channel cube now exists (November 2026).** It is not integrated; do not claim 102-band spectra.
- Direct difference subtraction is the delivered path; PSF matching was measured but not adopted. Do not attempt ZOGY.
- Use TAP primary and SIA2 fallback.
- Use a custom Canvas, not Aladin Lite, for the blink viewport.
- Golden cache is the key reliability feature.

### 14.2 Still verify on November 13

- [x] Recheck WISE 0855 coverage. **2026-11-13:** WISE 0855 has **258 DR1 artifacts** and no QR3. Revision 3 uses **DR1** for all three epochs; it is no longer “QR2-only”.
- [x] **B10:** recognize `/dr1/`; accept `DR1`/`QR3`/`DR1+QR3`; bump contract to **1.2.0**. **Done (`3c642ef`).**
- [x] **S7:** rebuild the golden cache as **revision 3** from **DR1+QR3**. **Done (`664977e`; 5/5, 17/17 sidecars, no QR2).**
- [x] Compute the exact 6-month epoch grouping for each target from live TAP and record it in the golden-cache manifest. **Done in revision 2; re-measured in revision 3 (same epoch sets, DR1+QR3 labels).**
- [x] Confirm the corrected WISE 0855 `133.75921, −7.24216` in `backend/core/targets.py`, the API examples, and the UI reticle. **Done.**
- [ ] Submission deliverables: live URL, repo, video, slides; open-source license requirement.
- [ ] Team size/local event rules and registration status.
- [ ] SI disclosure wording. The FAQ says each submission must describe how SI tools were used; the exact template is in the November 13 Project Submission Guide.
- [ ] Venue internet and deployment access.
- [x] Resources tab inspected (2026-11-13). Four NASA resources and four CSA partner resources; full list and decisions in [`docs/reference/resource-release-2026-11-13.md`](docs/reference/resource-release-2026-11-13.md).
- [ ] Recheck the Project Submission and Judging & Awards guides on the Resources page. The FAQ says they are released November 13; the guide files were not publicly retrievable at the time of this check.
- [x] Refresh the cache to **DR1 + QR3** (B10 release detection + S7 rebuild) and keep revision 2 as rollback. **Done 2026-11-13:** revision 3, 5/5, 17/17 sidecars, no QR2.
- [ ] Whether the official judging guide changes the 25% weights (2025 reference).
- [x] Docker Desktop is installed but its service requires administrator rights on this machine; use the WSL2 Docker Engine or confirm admin access. **WSL2 engine works; `skyblink:final` verified.**
- [x] Confirm the cutout service stays responsive during the event; keep retries/backoff and the golden cache. **Golden cache + retries/bounded live path tested; still recheck at the event.**

### 14.3 Questions for Gemini/reviewer

**Status 2026-11-08:** Q1, Q2, and Q8 are answered by the live verification; Q3 is partially answered (WISE 0855 corrected; Epsilon Indi B and R Draconis proper motions still need a source decision); Q5 is confirmed to work but remains a science-quality question. See `docs/verification/pre-event-verification.md`.

1. Is the TAP query schema correct for the live IRSA service? If not, provide the exact query.
2. Is the cutout URL pattern correct, and what is the maximum practical size?
3. Are the target coordinates and propagated 2025.8 positions correct? Verify with SIMBAD/Gaia.
4. Is the 2.0-native-pixel aperture (12.3″) and 3.0–5.0 px annulus appropriate for the five targets?
5. Is the WCS-WAVE + `sip=None` approach sufficient for the demo spectra?
6. Is the 6-month epoch grouping correct, or should we use visit-level frames?
7. What is the simplest reliable way to get Gaia/WISE reference cutouts on the same WCS?
8. Are the proposed bitmask policies safe, or are any hard-mask bits missing?
9. Is the 48-hour scope realistic for 3–4 people? What would you cut first?
10. Does the demo narrative overclaim anything?
11. What would make this stand out to NASA judges?
12. What should we explicitly not build?

---

## 15. Sources

### Official NASA / Space Apps

- NASA Space Apps 2026 — Planet X and SPHEREx:  
  https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/
- NASA Space Apps 2026 Participant FAQs:  
  https://www.spaceappschallenge.org/resources/participant-faqs
- NASA Space Apps judging guidance (2025 reference; verify 2026):  
  https://spaceapps-v2-staging.s3.amazonaws.com/media/documents/Final_Space_Apps_2025_Judging_Guidelines_for_web.pdf

### SPHEREx data and documentation

- SPHEREx Archive at IRSA — Data Access:  
  https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access
- SPHEREx Archive at IRSA — Data Products:  
  https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products
- SPHEREx DR1 overview (November 2026): https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_dr1.html
- Official 2026 Resources recheck (project document): [`docs/reference/resource-release-2026-11-13.md`](docs/reference/resource-release-2026-11-13.md)
- CSA NEOSSat: https://www.asc-csa.gc.ca/eng/satellites/neossat/
- CSA NEOSSat tutorial: https://github.com/asc-csa/NEOSSAT_Tutorial
- CSA NEOSSat dataset: https://data.asc-csa.gc.ca/dataset/neossat
- CADC: https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/en/
- IRSA TAP: https://irsa.ipac.caltech.edu/TAP
- IRSA SIA2: https://irsa.ipac.caltech.edu/SIA?
- IRSA cutouts: https://irsa.ipac.caltech.edu/ibe/cutouts.html
- SPHEREx Explanatory Supplement:  
  https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp_QR.pdf
- SPHEREx Data Explorer: https://irsa.ipac.caltech.edu/applications/spherex
- AWS Open Data — SPHEREx: https://registry.opendata.aws/spherex-qr/
- IRSA tutorials (cutouts, source discovery, PSF):  
  https://caltech-ipac.github.io/irsa-tutorials/

### Tools and standards

- Astropy: https://docs.astropy.org/
- reproject: https://reproject.readthedocs.io/
- photutils: https://photutils.readthedocs.io/
- sep: https://sep.readthedocs.io/
- Aladin Lite v3: https://aladin.cds.unistra.fr/AladinLite/
- SkyView: https://skyview.gsfc.nasa.gov/ (DSS2 Red, WISE 3.4/4.6); CDS HiPS2FITS: https://aladin.cds.unistra.fr/hips-image-services/hips2fits (tested; unreachable from the build environment).
- IVOA SIA2: https://ivoa.net/documents/SIA/20151223/
- HiPS: https://www.ivoa.net/documents/HiPS/
- HEALPix: https://healpix.jpl.nasa.gov/

### Internal project documents

- `SPHEREx Challenge Research and Pain Points.pdf` — original background research; treat as secondary.
- `AGENTS.md` — the multi-agent contract, file ownership, and API schemas.
- The v0.1/v0.2 roadmaps, technical audit, and agent draft were consolidated into these two files and removed to avoid stale instructions.

---

## Appendix A — Target coordinates and utility values

| Target ID | RA ref | Dec ref | Ref epoch | RA 2025.8 | Dec 2025.8 | PM RA* (mas/yr) | PM Dec (mas/yr) |
|---|---|---|---|---|---|---|---|
| `wise_0855` | 133.79513 | −7.24515 | 2010.0 | 133.75921 | −7.24216 | −8118.0 | +680.0 |
| `barnards_star` | 269.4521 | +4.6934 | J2000 | 269.4463 | +4.7676 | −801.6 | +10362.4 |
| `eps_indi_b` | 331.04415 | −56.78284 | J2000 | 331.0962 | −56.8005 | +3982.0 | −2466.8 |
| `rw_aurigae` | 76.95607 | +30.40133 | J2000 | 76.9561 | +30.4011 | +2.6 | −27.4 |
| `r_draconis` | 248.1676 | +66.7550 | J2000 | 248.1674 | +66.7548 | −13.7 | −31.0 |

**Notes:**

- `pm_ra*` is `μ_α cos δ`. If propagating manually, divide by `cos δ` to get the RA change.
- Use `SkyCoord.apply_space_motion` with `obstime` for the production path.
- WISE 0855's reference epoch is 2010.0; label it in the UI.
- Epsilon Indi B is 6.7′ from ε Indi A; the 0.6″ separation is Ba–Bb.
- R Draconis is near the North Ecliptic Pole; expect deep coverage and possible saturation.

---

## Appendix B — API summary

Full schemas are in `AGENTS.md` §3. The essential shape:

```http
GET /api/v1/targets
GET /api/v1/sky?ra=133.75921&dec=-7.24216&size=0.2&target_id=wise_0855
GET /api/v1/spectrum?ra=133.75921&dec=-7.24216&target_id=wise_0855
GET /api/v1/health
```

The `/sky` response contains:

- `target`: metadata or `null`.
- `wcs`: `crval1`, `crval2`, `crpix1`, `crpix2`, `cdelt1`, `cdelt2`, `width`, `height`, `pixel_scale_arcsec`, `native_pixel_scale_arcsec`.
- `epochs[]`: `epoch_id`, `label`, `collection`/`release` (per epoch, `DR1`, `QR3`, or `mixed`/`DR1+QR3` if a band falls back; historical revision-2 data used `QR2`/`QR2+QR3`), `mjd_mean`, `date_iso`, `frames` (keys `1`–`6`, `all`, `thermal`, `flag_overlay`), `flag_summary`.
- `differences`: `E2_minus_E1` → frame URLs.
- `reference_overlays`: optical and mid-IR URLs.
- `provenance`: source, collection, release, zodi/background flags, `flux_normalization` (method/scope/reference/applied/status/clamped), `is_simulated_fallback`, citation.

The `/spectrum` response contains `epochs[].channels[]` with detector, wavelength, bandwidth, flux, error, flags, `is_flagged_bad`, `clean_fraction`, and `is_used_in_photometry`, plus `molecular_features`, per-epoch `collection`/`release`, and `provenance` with `zodi_subtracted` and the collection/release rule.

---

## Appendix C — Reference Python pattern

This is a **reference**, not a drop-in module. Verify HDU names, units, and WCS behavior against the live data.

```python
import numpy as np
import astropy.units as u
from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord

BIT_SOURCE = 1 << 21
BIT_FULLSAMPLE = 1 << 12

HARD_BAD_MASK = (
    (1 << 2) | (1 << 6) | (1 << 9) | (1 << 10) | (1 << 11) |
    (1 << 14) | (1 << 15) | (1 << 26) | (1 << 27) | (1 << 28) | (1 << 29)
)

ARTIFACT_WARNING_MASK = (
    (1 << 0) | (1 << 1) | (1 << 7) | (1 << 17) |
    (1 << 19) | (1 << 20) | (1 << 22) | (1 << 23) | (1 << 24) | (1 << 25)
)

def parse_cutout(path, target_ra, target_dec):
    with fits.open(path, cache=False) as hdul:
        # hdul[0] is an empty PrimaryHDU. Access by EXTNAME.
        img = hdul["IMAGE"].data.astype(np.float64)
        flags = hdul["FLAGS"].data.astype(np.uint32)
        var = hdul["VARIANCE"].data.astype(np.float64)
        zodi = hdul["ZODI"].data.astype(np.float64)

        # 1. Zodiacal subtraction
        img = img - zodi

        # 2. Local background on source-masked, artifact-masked pixels
        bg_exclude = (flags & (HARD_BAD_MASK | ARTIFACT_WARNING_MASK | BIT_SOURCE)) != 0
        valid = img[~bg_exclude & np.isfinite(img)]
        local_bg = np.nanmedian(valid) if valid.size > 10 else 0.0
        img = img - local_bg

        # 3. Hard-mask only defective pixels; preserve BIT_SOURCE
        bad = (flags & HARD_BAD_MASK) != 0
        img[bad] = np.nan
        weights = np.where(bad | (var <= 0) | ~np.isfinite(var), 0.0, 1.0 / var)

        # 4. Wavelength at the target coordinate
        spatial_wcs = WCS(hdul["IMAGE"].header)
        x, y = spatial_wcs.world_to_pixel(
            SkyCoord(ra=target_ra, dec=target_dec, unit="deg", frame="icrs")
        )
        spectral_wcs = WCS(hdul["IMAGE"].header, fobj=hdul, key="W")
        spectral_wcs.sip = None  # mandatory
        wave_um, band_um = spectral_wcs.pixel_to_world(x, y)

        return {
            "image": img,
            "weights": weights,
            "artifact_flags": flags & ARTIFACT_WARNING_MASK,
            "source_flags": (flags & BIT_SOURCE) != 0,
            "spatial_wcs": spatial_wcs,
            "wavelength_um": float(wave_um.to(u.micrometer).value),
            "bandwidth_um": float(band_um.to(u.micrometer).value),
        }
```

**Pixel flux conversion:**

```python
OMEGA_PIX_SR = (6.15 ** 2) * 2.350443e-11  # 6.15" squared -> sr
flux_ujy = image_mjy_sr * OMEGA_PIX_SR * 1e12
```

---

## Appendix D — Glossary

| Term | Meaning |
|---|---|
| **LVF** | Linear Variable Filter — wavelength varies along one detector axis. |
| **MEF** | Multi-Extension FITS — image, flags, variance, ZODI, PSF (QR2) or EPSF (QR3/DR1), WCS-WAVE. |
| **DR1** | SPHEREx Data Release 1 — reprocessed QR2 images, released November 2026; use with QR3. The revision-3 cache uses DR1 for all five targets. |
| **QR3** | SPHEREx Quick Release 3 — current weekly release; use with DR1. Revision 3 uses QR3 for RW Aurigae's newest epoch and within the mixed 2026 epochs. |
| **QR2** | SPHEREx Quick Release 2 — superseded by DR1+QR3; historical only, retained in the revision-2 rollback cache. The current cache contains no QR2. |
| **TAP** | Table Access Protocol — SQL-like VO query service. |
| **SIA2** | IVOA Simple Image Access v2. |
| **HiPS** | Hierarchical Progressive Survey — tiled sky image format. |
| **SkyView** | NASA/GSFC service used to precompute real DSS2 Red + WISE 3.4/4.6 reference cutouts. CDS `hips2fits` was unreachable in the build environment. |
| **WCS** | World Coordinate System. |
| **Coadd** | Combining images to improve signal-to-noise. |
| **Difference imaging** | Subtracting one epoch from another to reveal changes. |
| **Persistence ghost** | Latent detector image from a prior bright source. |
| **Proper motion** | Angular motion of a star across the sky. |
| **Parallax** | Apparent shift due to Earth's orbit. |
| **Y dwarf** | Very cold brown dwarf (T_eff ≲ 300 K). |
| **Mira variable** | Pulsating AGB star with large amplitude. |
| **T Tauri** | Young, low-mass star with a disk and variability. |

---

## Appendix E — One-page checklist

### Before the event

- [ ] Official challenge, FAQ, and judging guide read.
- [x] November 13 resources inspected (NASA + CSA; see `docs/reference/resource-release-2026-11-13.md`).
- [ ] TAP/SIA2/cutout query path documented.
- [ ] MEF HDU and bitmask table confirmed.
- [ ] Five target coordinates verified.
- [ ] Team roles and deployment accounts ready.
- [ ] Demo outline drafted.
- [ ] No project code written before the start.

### During the event

- [ ] Public URL deployed by H+2.
- [ ] Real SPHEREx frame displayed by H+6.
- [ ] Blink works on one target by H+12.
- [ ] Arbitrary RA/Dec path works by H+12.
- [ ] Five targets load by H+24.
- [ ] Difference mode works by H+32.
- [ ] Spectrum works or is explicitly cut by H+32.
- [ ] Feature freeze at H+42.
- [ ] Video recorded by H+46.
- [ ] Submitted by H+46.

### Before submission

- [ ] Live URL works in incognito.
- [ ] No login/API key required.
- [ ] All five targets tested.
- [ ] Attribution present.
- [ ] README complete.
- [ ] Video uploaded.
- [ ] SI disclosure included.
- [ ] Open-source license included.
- [ ] Known limitations stated.
- [ ] Submission form completed.
