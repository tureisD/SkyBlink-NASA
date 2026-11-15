# W0 Feasibility Report — Phase 2 Upgrades

**Date:** 2026-11-09  
**Base:** `dab3b88` (W0 read-only spike; no product code, contract, or golden-cache rebuild)  
**Implementation status (2026-11-09; historical):** this report drove the final scope. PSF-wing photometry and R Dra NEP re-clustering were **dropped**; dense spectra (12 visits), telemetry sidecars, real SkyView DSS2/WISE + Gaia overlays, and the F5/F6 UI were **implemented**. It describes the revision-2 implementation; the current data is revision 3 (DR1+QR3). See `README.md` and `STATUS.md`.
**Scope:** validate the ambitious parts of `Upgrades.md` against real cached data before committing engineering time.  
**Data:** 612 cached FITS cutouts (backend + science caches), real IRSA TAP metadata, real SkyView cutouts, and the five golden manifests.  
**Guardrails:** 40/40 tests pass; no `hdul[0].data`; no naive `flags > 0`; all measurements are read-only.

---

## 1. Executive summary

| Item | Verdict | Measured result |
|---|---|---|
| PSF-wing recovery for saturated stars | **NO-GO** | Barnard **0/54**, R Draconis **0/60** pass `f_wing ≥ 0.12` with ≥8 clean wing pixels. Even with no flags, only 23/38 and 10/56 pass. |
| R Draconis 5–6 complete 6-band epochs | **NO-GO** | 2,483 TAP rows form one continuous 520-day season; no >60-day gap. Only one all-6 block at a 10-day gap; D2/D5 have 89 exposures each. |
| Telemetry `<45 KB` sidecar | **NO-GO (budget)** | Real 240×240 float16 + uint32: **78.5–101.0 KiB gzipped**, **104.1–134.0 KiB base64 JSON**. The `<45 KB` claim is false by ~1.8–2.3×. |
| CDS `hips2fits` overlays | **NO-GO** | 6/6 CDS requests timed out from this environment. SkyView is reachable. |
| Real SkyView overlays + Gaia pins | **GO** | DSS2 Red 240×240 on the exact golden WCS (2.5 s, 21 KB WebP); WISE 3.4 240×240 with retry (7.3 s, 5.8 KB WebP); Gaia DR3 fields available, cap to G≤16. |
| LVF 6/9/12 visits | **GO-METADATA** | WISE +46/+80/+106 distinct 5 nm samples; Eps Indi B +61/+121/+172. 12 visits ≈15–17 s per band including downloads; extraction <0.6 s. |
| `<15 s` cold multi-epoch arbitrary blink | **NO-GO** | 3 epochs × B3/B5/B6 = **34.6 s cold / 20.3 s warm**. Best limited case (2 epochs × B5+B6) = **22.7 s cold / 10.1 s warm** with an unusually fast TAP. PSF cube is 96.9% of each cutout, so 0.08° saves only 3.4%. |
| PSF cube indexing | **GO (QR2)** | HDU 5 `PSF` shape `(121, 101, 101)`, `OVERSAMP=10`, `CDELT=0.615″`; zone derivable per cutout. QR3/DR1 use `EPSF` and need a separate reader (already branched in the W0 script). **2026-11-13:** DR1 is now the recommended reprocessed release; do not apply this QR2 measurement to DR1 without re-measuring. |
| Cache mapping | **GO** | `artifact_uris` → SHA-256 cutout path verified 54/54 for WISE and Barnard’s. |
| IVW / PSF-matched differences | **UNMEASURED** | Not covered by W0; validate in B8 before replacing golden differences. |

---

## 2. PSF-wing photometry — NO-GO

The HDU 5 `PSF` cube is real and the indexing rule works for QR2:

- shape `(121, 101, 101)`, `OVERSAMP=10`, `CDELT=0.615″`, `CRPIX=(51, 51)`;
- each plane sums to 1.0;
- zone: `xpix_orig = 1 + x_cutout - CRPIX1A`, `ypix_orig = 1 + y_cutout - CRPIX2A`, nearest `XCTR/YCTR`;
- the 1.2–4.2 native-px annulus contains **13.2%** of the PSF flux.

But the annulus is **not unsaturated** on the two targets that need it:

| Target | Channels | Current usable | PSF-bearing | QR3 `EPSF` | Gate pass | Rejected |
|---|---:|---:|---:|---:|---:|---:|
| Barnard’s Star | 54 | 1 | 38 | 16 | **0** | 37 |
| R Draconis | 60 | 0 | 56 | 4 | **0** | 56 |

Mask-robustness (PSF-bearing channels only):

| Target | Spec mask | HALO-relaxed | Hard-only | No flags |
|---|---:|---:|---:|---:|
| Barnard | 0/38 | 0/38 | 3/38 | 23/38 |
| R Draconis | 0/56 | 0/56 | 1/56 | 10/56 |

The best failed Barnard channel is `f_wing=0.0398` (D5, N=44); R Draconis’s best is `0.00033`. The one currently usable Barnard channel already has a valid aperture measurement. The 1.2–4.2 px annulus is dominated by `BIT_SOURCE`, `OVERFLOW`, and `SUR_ERROR`, so wing fitting cannot honestly recover the claimed ≥45 channels.

**Decision:** remove PSF-wing photometry from the build. Do not add `photometry_method="psf_wing_fit"`. Keep the saturation caveats in the README and UI.

---

## 3. R Draconis NEP clustering — NO-GO

TAP returns **2,483 rows**, matching the directive’s claim, but the time distribution is one continuous season:

- MJD span **60789.9–61310.3** = **520.4 days**; largest night-to-night gap **37.8 days**;
- per band: D1 584, D2 89, D3 575, D4 581, D5 89, D6 565;
- 391 distinct 2.4-hour bins, 547 distinct 0.01-day MJDs, 222 distinct integer days;
- releases: QR2 1760, QR3 723.

Clustering results:

| Gap | Clusters | ≥4 bands | all 6 bands |
|---|---:|---:|---:|
| >60 d | 1 | 1 | 1 |
| >30 d | 2 | 2 | 2 |
| >10 d | 7 | 3 | 1 |

The production `group_epochs` view is also unbalanced (2024_E1 has only D3/D6; 2025_E1/E2 and 2026_E1 have all six but with very uneven per-band counts). Five to six well-populated complete 6-band epochs are not supported by the data.

**Decision:** keep the current four epochs and the honest `2024_E1` B3/B6-only caveat. Do not interpolate or invent epochs.

---

## 4. Telemetry sidecar — GO with a revised budget

Real 240×240 single-band reprojections plus a Table 16 `uint32` flag plane:

| Case | float16 gzip | uint32 gzip | Both gzip | Both base64+gzip | JSON base64+gzip |
|---|---:|---:|---:|---:|---:|
| WISE 0855 2025_E1 D5 | 91,350 B | 4,483 B | **96,773 B** | 129,032 B | 127,975 B |
| R Draconis 2025_E1 D3 | 78,318 B | 1,455 B | **80,429 B** | 107,240 B | 106,559 B |
| Barnard 2025_E1 D6 | 99,331 B | 3,444 B | **103,376 B** | 137,836 B | 137,231 B |

- Honest gzipped both: **78.5–101.0 KiB**.
- Honest base64 JSON: **104.1–134.0 KiB**.
- The float16 plane dominates; the flag plane is only 1.5–4.5 KB.

**Decision:** keep the telemetry sidecar, but state the real budget. Use one binary `float16` MJy/sr plane + `uint32` flags plane, gzipped, outside `epochs[].frames` (e.g. `epochs[].telemetry`). This is still viable: 5 targets × 3–4 epochs × ~100 KB ≈ 1.5–2 MB.

---

## 5. Real overlays and Gaia — GO via SkyView, not CDS

CDS `hips2fits` is unreachable from this environment (6/6 TCP connect timeouts, ~8.2 s each). This is environment-specific; do not claim CDS is globally down.

SkyView works:

| Asset | Result | Timing | Verdict |
|---|---|---|---|
| DSS2 Red 240×240 FITS | Exact golden TAN WCS; 21,382 B WebP; 3/3 reliability | 2.26–2.46 s | **GO** |
| WISE 3.4 µm 240×240 FITS | Exact golden TAN WCS; 5,834 B WebP; 2/3 reliability (one blank 1-element FITS) | 7.29 s | **GO with retry/200×200 fallback** |
| Gaia DR3 TAP pins | All six fields available; WISE 1,196 sources / Barnard 9,909 within 0.2° | ~14–16 s full query | **GO with G≤16 cap** |

Attribution: DSS2 Red via NASA/GSFC SkyView and STScI; WISE 3.4 µm (AllWISE) via SkyView and NASA/JPL/Caltech; Gaia DR3 via ESA/Gaia/DPAC and IRSA TAP. These are display/reference fields, not calibrated photometry; WISE 0855 is not detected in DSS2 or WISE 3.4.

**Decision:** replace the earlier placeholder curtain references with real SkyView DSS2 Red + WISE 3.4, with retry/fallback and explicit attribution. Cap Gaia pins to G≤16 (≈19 KB WISE, ≈64 KB Barnard) and handle ~12% null proper motions.

---

## 6. LVF visits — GO, but not 17 for free

TAP has ample visits (WISE 256, Eps 445), but there is no pointing/detector-Y/wavelength column and HTTP Range is ignored. Selecting 17 visits requires downloading all candidates (~5 MB each), a 3–4× data multiplier.

Measured 6/9/12 visits, band 6, one epoch:

| Target | Visits | Download | Extraction | Channels | Distinct λ |
|---|---:|---:|---:|---:|---:|
| WISE 0855 | 6/9/12 | 13.65 / 17.16 / 16.36 s | 0.27 / 0.34 / 0.44 s | 6/9/12 | 6/9/12 |
| Epsilon Indi B | 6/9/12 | 14.56 / 14.52 / 14.73 s | 0.28 / 0.36 / 0.53 s | 6/9/12 | 6/9/12 |

Estimated distinct-sample gain:

| Target | Existing 3 visits | +6 | +9 | +12 |
|---|---:|---:|---:|---:|
| WISE 0855 | 54 | +46 | +80 | +106 |
| Epsilon Indi B | 68 | +61 | +121 | +172 |

**Decision:** use **12 visits** as the target tier (72 channels/epoch when all six detectors are available), with 9/6 as fallbacks per band-epoch. This is a real, measured upgrade; it is not 102 channels and does not fix saturated targets.

---

## 7. Live multi-epoch blink — NO-GO as scoped

Measured at `134.10, −7.10`, 0.08° cutouts, 1 visit/band:

| Case | TAP | Cold download | Pipeline | Cold total | Warm total | Blink? |
|---|---:|---:|---:|---:|---:|---|
| 2 ep × B6 | 14.87 s | 12.50 s | 4.74 s | **32.11 s** | 19.67 s | yes |
| 2 ep × B5+B6 | 2.77 s | 12.76 s | 7.15 s | **22.68 s** | 10.05 s | yes |
| 3 ep × B6 | 14.98 s | 13.12 s | 7.51 s | **35.61 s** | 22.42 s | yes |

The 2.77 s TAP in the B5+B6 case is a best-case outlier; the same run family otherwise saw 4.8–20.4 s. The PSF cube is **96.9%** of a 5 MB cutout, so `0.08°` saves only **3.4%** of bytes. `build_manifest` has no `bands` parameter; a limited path would require threading a band subset through TAP, visit selection, and rendering.

**Decision:** do not promise a `<15 s` cold multi-epoch arbitrary blink. Either keep the current single-epoch arbitrary path and document it, or add an explicit **“Deep blink”** with a ~30 s budget, progress UI, and caching. This is a product choice, not a science blocker.

---

## 8. Revised scope

### Drop

- PSF-wing photometry (`psf_wing_fit`); the reliability gate fails on the real data.
- R Draconis 5–6 complete 6-band epochs; the cadence does not support them.
- `<45 KB` telemetry claim; use the measured 80–105 KB gzip budget.
- `<15 s` cold multi-epoch blink promise.
- CDS `hips2fits` as a dependency.

### Keep / GO

- **Dense spectra:** 12 visits/band/epoch (fallback 9/6), rebuilt golden cache, honest channel counts.
- **Telemetry sidecar:** separate `epochs[].telemetry`, binary gzip, real MJy/sr + Table 16 flags.
- **Real overlays:** SkyView DSS2 Red + WISE 3.4 with retry, Gaia DR3 G≤16 pins, full attribution.
- **IVW / PSF-matched differences:** validate in B8; keep only if residuals improve.
- **Display-only core inpainting:** optional, explicitly labeled, never applied to science arrays.
- **Wave 2 X-factors:** shift-and-stack/parallax sandbox, LVF visualizer, Web Audio sonification, dynamic-channel triage card, forward T1+T6 comparator, unverified candidate brackets.
- **Contract 1.1.0 (trimmed):**
  - `epochs[].telemetry` `{url, format, width, height, byte_size}`
  - `epochs[].lvf_geometry` per detector `{detector, pa_deg, grad_um_per_arcsec}`
  - `epochs[].candidates[]` only if the candidate feature is built; objective SNR/delta-flux/artifact-clean, no confidence
  - `channels[].photometry_method` with `aperture_12.3` and, if built, `crowded_diff_6.8` (no `psf_wing_fit`)
  - `channels[].aperture_mode`, `aperture_radius_arcsec`
  - display-only `core_inpainted` flag

### Defer / optional

- Live multi-epoch arbitrary blink: a “Deep blink” with a 30 s budget, or leave the current single-epoch path.
- Binary inverse fitting: keep only the forward T1+T6 comparator.
- 17-visit LVF scanning: not worth the 3–4× download multiplier; 12 is the practical tier.

---

## 9. What this means for the project

**Gains**

- Spectra grow from 18 to up to 72 channels/epoch on bands/epochs with 12 visits, with measured, honest channel counts.
- The cursor can display real MJy/sr and per-pixel Table 16 flag names from the sidecar.
- The curtain becomes real (DSS2 Red + WISE 3.4) with Gaia DR3 pins, not placeholder graphics.
- The LVF visualizer, shift-and-stack sandbox, sonification, and triage card become credible instrument-physics/outreach features.
- The contract stays additive and the honesty story stays intact.

**What does not change**

- Barnard’s Star and R Draconis remain saturation-limited; their spectra will still show null/fluxless channels. Dense sampling does not fix a saturated core.
- R Draconis `2024_E1` remains B3/B6-only.
- No 102-band claim, no Planet X discovery claim, no fake confidence scores.

---

## 10. Decisions required

1. Approve the **revised scope**: drop PSF-wing and R Dra NEP; build dense spectra, telemetry, real overlays, IVW/PSF differences, and the Wave 2 X-factors.
2. Choose the visit tier: **12** (maximum, ~15–17 s per band/epoch), **9** (balanced), or **6** (fastest).
3. Choose the telemetry format: binary gzip (80–105 KiB; browser `DecompressionStream`) or base64 JSON (104–134 KiB; no decompressor).
4. Choose the arbitrary-coordinate behavior: keep single-epoch, or add a “Deep blink” with a ~30 s budget and progress UI.
5. Approve the additive **1.1.0** contract with the trimmed field set.
