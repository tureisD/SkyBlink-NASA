# Phase 3: raw-unit scientific verification

Date: 2026-11-14. API semantic version: **1.3.0**, with unchanged JSON field
types. Implementation checks pass, but **scientific acceptance has not passed**.
The fixed control-star gate failed. This report does not certify the saved
target interpretations, all coordinates, calibrated photometry, or a cache
rebuild. The five shipped revision-3 datasets remain byte-for-byte unchanged.

## Reproducible inputs and acceptance rules

`scripts/phase3_science_validation.py` downloads only source URIs already
recorded in the real golden manifests. Eleven inputs were selected before
examining their raw flux: the first recorded B6 exposure in the first two
WISE 0855 epochs, the first B3 exposure in the first two epochs of each other
target, and the first WISE B1 exposure. Three recorded WISE B3 contributors
were added to investigate the manifest's DICHROIC warning. The second of
those contains the affected pixels; the first and third do not.

All **14/14 inputs downloaded successfully**. Each has an exact URI, SHA-256,
FITS observation dates, dimensions, and measured results in
[phase3-science-results.json](../evidence/phase3/phase3-science-results.json). Raw files remain in
ignored `backend/.cache/phase3/cutouts`; none were added to golden assets.
The 0.2-degree requested field uses a padded 0.286259379-degree detector cutout.
The fixed target query coordinates were retained, including the coordinate
issues identified by the separate catalog audit. Target fluxes here are
forced-aperture diagnostics at those coordinates, not uncontaminated source
measurements or new discovery claims.

```powershell
.venv311/Scripts/python.exe scripts/phase3_science_validation.py
.venv311/Scripts/python.exe scripts/phase3_science_validation.py --analyze-only
.venv311/Scripts/python.exe -m pytest backend/tests -q -rs
```

The second command reuses cached real inputs without network retries. Reports
are published atomically after analysis. Missing raw files produce explicit
skips in local-data regression tests; a fresh checkout cannot claim those
tests passed without downloading the inputs.

The original numerical gates were fixed before target-flux inspection:

- Identical-assumption independent aperture flux: relative tolerance `1e-8`.
- At least three candidate static controls, absolute median standardized
  residual at most 1, robust scatter at most 2, and no absolute residual above 5.
- Controls: Gaia G between 10 and 15.5, proper motion at most 100 mas/year,
  at least 30 arcseconds from the target and 12.3 arcseconds from a known saved
  Gaia neighbor; complete clean aperture, SNR at least 5 in each visit.
- Spectral centers within one quarter of the narrower bandwidth, bandwidth
  ratio at least 0.8, evaluated across the actual retained output pixels.
- Half-output-pixel temporal-motion warning: 1.5375 arcseconds.

The control list is sorted by source ID and capped at ten before inspecting
their residuals. Entire apertures must lie inside the matched field. An early
development run included stars in the padded area outside that field; it was
discarded as an invalid test footprint. The final ten in-field controls and
the failed thresholds below are retained without outlier removal or tuning.

## Implemented processing safeguards

Measurement arrays exclude hard and warning flags **before bilinear
reprojection**. Display arrays remain separate, retaining allowed warnings
and display-only HALO. SOURCE remains eligible for measurement and is excluded
only from background estimates. Science coadds and raw differences use the
measurement arrays; normalization and display stretches do not mutate them.
The actual affected WISE D3 cutout contains **9,605 DICHROIC pixels**. Real-input
tests confirm that DICHROIC and HALO can remain visible while contributing no
measurement pixels, and that clean SOURCE pixels survive.

Background estimation requires sufficient counts and spatial support. An
unsupported estimate reports `subtracted: false`; a channel can have positive
`clean_fraction` while its flux/error are null and `is_used_in_photometry` is
false. This semantic clarification is why the API is **1.3.0**. Scalar fallback
requires at least 11 clean pixels, at least 5% clean coverage, three quadrants,
and half-frame extent in each axis. A robust plane needs additional cell and
held-out improvement gates. Tests also remove background support from real
pixels through explicitly test-only flag mutations, including corner-only
support; these are not packaged observations.

The spectral selector first screens nine positions and then evaluates the
exact contract-grid pixel centers: **3,364** pixels at 0.05 degrees and
**54,756** at 0.2 degrees. It rejects mismatched widths and localized failures
between coarse samples. An otherwise compatible exposure with unusable
background/measurement support is skipped in favor of another usable pair.
Common output bands use one exposure per epoch and a maximum 30-day
within-epoch composite span. The result remains a visual comparison, with
approximate WCS-WAVE calibration and no PSF matching. Live measurement/display
arrays, flags, and footprints outside the validated crop are excluded before
normalization, statistics, differences, and telemetry.

## Background measurements

The 14 cutouts produced **3 scalar**, **2 supported 2D**, **7 scalar with limited
spatial support**, and **2 insufficient spatial-support** outcomes. The last
two are the Barnard B3 inputs. Crowded/saturated fields do not automatically
receive a plane fit. No claim is made that a plane is preferable everywhere,
or that diffuse astrophysical emission can be separated from sky by this fit.

| Real input | Scalar held-out absolute error (MJy/sr) | Plane error (MJy/sr) | Chosen result |
|---|---:|---:|---|
| WISE 0855 2025_E1 D3, first contributor | 0.00268237 | 0.00132653 | Supported 2D |
| WISE 0855 2025_E2 D6 | 0.00340189 | 0.00299779 | Supported 2D |

These production diagnostics use held-out checkerboard cells, not the fit's
training residual. A separate 4x4 checkerboard plane/scalar RMS calculation is
also saved for every sufficiently supported input. Residual support and
selection criteria remain visible in JSON; no missing-data case is counted as
a successful background correction.

## Aperture arithmetic, official method, and uncertainty

**9/9 finite pipeline fluxes agree** with an independent Photutils center-pixel
sum using identical masks, aperture, annulus, background, and pixel-area
assumptions. Five unusable cases remain null. This validates arithmetic and
units under the stated assumptions, not deblending, completeness of the source
flux, or the physical reliability of every finite result. RW Aurigae's finite
partial measurements remain marked unused; saturated Barnard and R Draconis
cores retain nulls.

The actual reviewed IRSA `extract_photometry` function is cached with SHA-256
`d89cbe1042383a8e1d03747e9728d4ec310d8201d05ca150367917b3b1a1270d`.
The script refuses an unreviewed source change. Its five-subpixel aperture and
sigma-clipped annulus were run with SkyBlink's 12.3-arcsecond radius and 3–5
native-pixel annulus, conservative masking, and the same constant WCS pixel
area. Five target-input comparisons produce finite results; their flux
differences from center-pixel integration range from **−3.73% to +16.81%**.
Other cases lack usable annulus pixels or aperture flux and are not declared
agreement successes. The official function subtracts full geometric aperture
area; SkyBlink sums retained center pixels. Neither this adaptation nor the
center-pixel reference is an independent IRSA Tractor extraction or an
aperture-corrected, SAPM-calibrated total flux.
[IRSA tutorial](https://caltech-ipac.github.io/irsa-tutorials/spherex-source-discovery-tool-demo/),
[reviewed implementation](https://github.com/Caltech-IPAC/irsa-tutorials/blob/main/tutorials/spherex/spherex_source_discovery/spherex_source_discovery_tool/aperture_photometry.py)

Approximate flux errors now include uncertainty in the shared median
background, in addition to summed native variance. In the finite sampled
measurements, errors increase by factors from approximately **1.00004 to
1.27776** over the native-variance-only floor. A regression changes only real
annulus variance and confirms unchanged flux but a larger error. Fitted-plane
covariance, detector correlations, PSF and pixel-phase effects, and blending
are not fully represented; these errors must not be treated as calibrated
false-alarm probabilities.

All 14 inputs were rendered with three different production WebP stretches.
The displayed bytes changed while raw arrays and repeated extraction results
were unchanged. The historical five-target card is now explicitly classified
as **display smoke and saved-metadata checks**, not scientific acceptance. Its
default output is separate from the historical golden validation report.

## Locked static controls: failed acceptance

The selected WISE, Barnard, RW Aurigae, and R Draconis exposure pairs fail the
wavelength gate. Their raw differences are not accepted as variability tests.
The Epsilon Indi B3 pair passes the dense field comparison, but its ten
candidate controls fail the fixed stability gate:

| Statistic | Measured | Fixed limit | Outcome |
|---|---:|---:|---|
| Absolute median standardized residual | 0.57291 | ≤1 | Within limit |
| Robust scatter | 2.70845 | ≤2 | Failed |
| Largest absolute standardized residual | 13.67990 | ≤5 | Failed |

These Gaia candidates are **not independently certified static infrared
sources**. The saved G<16 catalog cannot exclude all faint blends. The result
therefore identifies an unresolved measurement/control-selection problem;
it does not demonstrate an instrument failure or astrophysical variability.

The strongest residual belongs to Gaia source `6412593916202695936`. Its nearest
saved neighbor, `6412593916202695552`, is **13.7997 arcseconds** away. Both
apertures have zero eligible annulus pixels and use the supported field-level
background. Their center flags contain SOURCE, with no excluded center bit.
Positive-pixel aperture centroid offsets differ from approximately
`(−0.480, −0.072)` to `(−0.133, −0.010)` native pixel.

An exploratory calculation kept the **same ten controls** and the same sky
estimate, changing only aperture-boundary integration to five-subpixel
weights. For the largest residual, fluxes change from **8656.51 → 6640.35 µJy**
to **8222.73 → 7843.03 µJy**. Dividing by the original approximate errors gives
−2.576 instead of −13.680. Across the locked ten, this exploratory statistic
has median 0.5313, scatter 1.4559, and maximum absolute value 3.8393. The actual
IRSA routine yields finite fluxes for five of these controls; it returns null
for the five with no clean annulus, including the strongest residual.

This supports aperture discretization/pixel phase, with possible neighbor
contamination, as issues requiring investigation. It is **not a replacement
passing acceptance result**. Production aperture integration was not changed.
A fractional-aperture repair needs a new, independent held-out sample,
stronger Gaia/infrared isolation checks, and a defensible background treatment
before Phase 4 science certification.

## Temporal smearing and external checks

The JSON audits all recorded image URI planning weeks and between-band mean
dates, with per-band spans. These are conservative calendar-week bounds, not
invented precise exposure times. Saved WISE epoch spans allow about **4.06
arcseconds** of proper-motion drift; Barnard reaches about **4.18 arcseconds**.
Seven saved target/epoch combinations exceed the half-output-pixel warning
using these bounds. The new one-visit-per-band policy avoids such within-band
semester averaging; composites still span real, explicitly bounded times.
The two sampled R Draconis files are dated **2025-04-24** and **2025-05-01**,
despite the first being stored under `2024_E1`. Epoch-label migration belongs
to the provenance/cache phase.

[Independent astrometry](phase3-astrometry-results.md) measured fresh Gaia
positions against real native/reprojected D1 inputs: **9/10 exposures** met the
three-star, 1.5375-arcsecond robust-RMS gate; the last R Draconis exposure had
only two suitable stars and remains insufficient. This is stronger than WCS
self-consistency, but does not certify all bands or saved coadds.

[Calibration and catalog audit](phase3-calibration-audit.md) records the flag
table, WCS-WAVE versus CWAVE/CBAND comparison, reference motion checks, and
their limitations. WCS-WAVE is a visualization approximation, not a guaranteed
1-nm science calibration. Remaining work includes additional detectors/releases,
the primary WISE reference-coordinate correction and R Draconis motion review.
Coordinates and golden products were not silently migrated during this phase.
[IRSA data-product guidance](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/)

## Verification and closure

The focused science/selection/pipeline suite passed **31 tests with no skips**
against the cached real inputs. The final integrated backend suite passed
**184 tests, no skips**, in 14.02 seconds (one Starlette/httpx deprecation
warning). Frontend typecheck, production build, real-data protocol tests, and
1,458 TAN-reference samples passed. An in-memory render of a real-cache-derived
API 1.3 payload with null flux/error, positive clean fraction, and unused
photometry rendered safely without invented zero values. Generated mathematical astrometry
inputs and controlled flag/variance mutations are explicitly listed in the
Phase 1 inventory; no generated observation product was introduced.

Phase 3 delivered safeguards, reproducible raw measurements, and identified
failures. **The scientific gate remains open**. Before a scientifically
certified rebuild: validate the aperture repair on independent controls,
resolve source isolation/background limitations and primary target coordinates,
finish multi-detector calibration checks and insufficient astrometry, and
retest the matched products. Phase 4 must stage a new cache separately and
must preserve the failed results above as evidence rather than tune them away.
