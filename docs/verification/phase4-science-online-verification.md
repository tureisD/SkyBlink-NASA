# Fresh independent photometry validation

**Primary result: failed.** All eight preregistered region/detector searches finished. Exact-aperture+SAPM photometry passes five of six measurable cells; one exceeds the fixed scatter threshold. The separately reported, predeclared existing center-pixel+constant-WCS baseline passes all six cells on the same eligible controls. This secondary finding does not turn the primary study into a success or justify adopting a different method after seeing results. The [frozen aggregate](../evidence/phase4/phase4-science-online-results.json) records both outcomes.

This investigation uses newly queried Gaia DR3, AllWISE and SPHEREx observations in four preregistered high-latitude regions. It does not rebuild or certify the five saved revision-3 datasets. The original Phase 3 failure and earlier Phase 4 empty/incompatible holdouts remain unchanged.

The frozen [protocol](../evidence/phase4/phase4-science-online-preregistration.json), its [exact-aperture amendment](../evidence/phase4/phase4-science-online-amendment-exact.json), catalog locks, pair ranks, preflight records and measurement JSON files are the evidence. The amendment was approved and written **before any new SPHEREx control aperture flux was extracted or inspected**. Exact circle–pixel intersection became the primary method on numerical grounds; center-pixel and five-by-five subpixel integration remain comparison methods. All stability, isolation, support, wavelength, astrometry and SNR thresholds remained fixed.

## Fixed design and acceptance

The four 0.5-degree catalog regions are the north and south Galactic poles, and Galactic `(l,b)=(180,+60)` and `(0,-60)`. Each is tested on detectors 1 and 3, with at most eight distinct candidate observations per region/detector. No early stopping after passing two fields or detectors is permitted. Pair ranks are frozen from metadata before flux; selection requires calibrated wavelength compatibility, support, independent astrometry and at least three locked controls. Once flux is measured, a failed pair is never replaced.

Controls have Gaia G=10–17, RUWE≤1.4, |parallax|≤10 mas, proper motion≤100 mas/year, no catalog variability flag, and a unique high-quality AllWISE counterpart. Both optical and infrared catalog-neighbor exclusions are 30.75 arcseconds. Catalog locks use AllWISE W1 brightness order before viewing SPHEREx flux. Prior Phase 3 control IDs are excluded. Missing neighbor proper motions, unresolved companions and sources below catalog limits remain limitations; these are **catalog-selected candidate stable stars**, not independently established infrared standards.

The same locked controls must have complete usable aperture support for every compared method, supported image background, at least ten clean native annulus pixels and SNR≥5 in both observations for every SAPM method. No replacement, residual clipping, fitted flux scaling or error inflation is allowed. Define

`z = (F₂ − F₁) / sqrt(σ₁² + σ₂²)`.

Each valid cell requires ≥3 controls, `|median(z)|≤1`, `1.4826 median(|z−median(z)|)≤2`, and `max|z|≤5`. The overall measured gate requires two independent fields and two detectors, and **every measured valid cell must pass**. Missing or insufficient cells are reported, never counted as passes. Five-subpixel versus exact deviations above 0.1σ remain reported diagnostics; after the premeasurement amendment, they are not a gate on exact integration.

## Numerical method and interpretation

All science arrays come from named real FITS extensions. Measurements use unnormalized `IMAGE−ZODI−supported residual background`, retaining SOURCE pixels in the aperture and excluding hard/warning flags. Native-center annulus pixels from radii 3–5 exclude SOURCE as well. The aperture radius is 12.3 arcseconds divided by the local WCS pixel scale. The implementation uses a circle in native pixel coordinates; it is not an exact distorted sky-circle integration.

For exact fractional weights `wᵢ`, surface brightness `Iᵢ` in MJy/sr, variance `Vᵢ` in (MJy/sr)², and release-matched SAPM solid angle `Ωᵢ` in steradians, let `Kᵢ=10¹²Ωᵢ`. Then

`F[µJy] = Σ wᵢ Kᵢ (Iᵢ−b)`

`σ²[µJy²] = Σ wᵢ² Kᵢ² Vᵢ + (Σ wᵢ Kᵢ)² Var(b)`.

Here `b` is the median clean annulus brightness. `Var(b)` is the larger of `(π/2)mean(Vann)/Nann` and `(1.2533×1.4826×MADann)²/Nann`. This approximates median-background uncertainty; it does not propagate all correlated image/background/calibration errors. No synthetic noise is added to the observations. Independent generated-noise trials exist only in isolated mathematical tests.

The separate constant-WCS approximation uses `Ω=(pixel_scale_arcsec×π/(180×3600))²`. It is reported independently and is not interchangeable with SAPM validation. Exact overlap reduces geometric quadrature error for pixel-constant surface brightness; it does not correct the PSF, aperture loss, blends or different spectral responses. [Photutils aperture documentation](https://docs.astropy.org/projects/photutils/en/stable/user_guide/aperture.html) describes the overlap methods and propagation conventions.

Calibrated matching uses release/detector/orientation-matched CWAVE/CBAND arrays whose WCS-WAVE table agrees exactly with the exposure. The maximum center shift is ≤one quarter of the narrower bandwidth and bandwidth ratio≥0.8 on a fixed 21×21, 3.075-arcsecond grid around each control, centered at both visit positions. This is a local sampled neighborhood test; it is not proof of identical spectral response functions or a full-field image comparison. SAPM units are checked as arcsec² and converted explicitly. [Official SPHEREx data-product documentation](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/) distinguishes calibrated arrays, approximate visualization WCS and pixel solid angles.

Independent astrometry uses native image peaks and fresh Gaia propagated to exposure time. It does not clip residual outliers. Each exposure requires at least three matched stars and robust RMS including bias≤1.5375 arcseconds. This constrains registration, not source variability.

Embedded EPSF diagnostics follow the official native-pixel template convention: select the detector zone, evaluate the oversampled effective PSF at native pixel centers, normalize the finite 11×11 template, then fit amplitude plus constant sky with input variances. The effective PSF already includes pixel response; re-integrating it as an optical PSF would be wrong. These fits are diagnostics, **not official Tractor equivalents or certified total fluxes**: they omit simultaneous neighbor fitting, spatial PSF interpolation and full covariance/calibration treatment. [Official EPSF tutorial](https://caltech-ipac.github.io/irsa-tutorials/spherex-psf/), [IRSA forced-photometry tool](https://irsa.ipac.caltech.edu/onlinehelp/spherex/spherex/sp.html).

## Transport and validation deviations retained explicitly

Some original candidate downloads returned HTTP 503. The Orchestrator approved uniform retries of the exact failed URL before flux in that cell, without changing the eight-observation cap or pair ranks. The original south-pole D1 failed lock is retained; a separate `D1-retry-*` chain records the successful original rank-one pair. The first retry succeeded. Subsequent transfers allow at most three attempts under one 90-second per-file budget, with finite read timeouts; this is a research transfer limit, not a production API latency guarantee.

The first two D3 preflight files propagated source positions and astrometry, but accidentally omitted repeating catalog-neighbor exclusions at each observation epoch. Separate `*-D3-isolation-audit.json` files record this check after the first measurements: **all nine north-pole and ten south-pole locked controls still pass the unchanged cuts**. No measured source was deleted or replaced. Later preflights include these checks before flux. AllWISE neighbor coordinates lack proper motion in this query and remain at their catalog positions; Gaia neighbors with missing PM also remain at reference positions.

Fresh pole discovery is scoped to the retained wide DR1/QR3 responses; completeness of deep discovery was not assumed. Fresh b60 discovery subsequently succeeded in all four collections, but the predeclared research ranks continue to use wide responses only for consistent scope. Every accepted input and calibration has a raw-byte SHA256 and retrieval receipt in the ignored research cache. No observations come from the shipped golden cache.

## Final measured results

| Field | Detector | Primary exact+SAPM controls | Median z | Robust scatter | Maximum absolute z | Status |
|---|---:|---:|---:|---:|---:|---|
| North Galactic pole | 3 | 3 | −0.33893 | 0.30800 | 0.54667 | Pass |
| South Galactic pole | 3 | 5 | −0.11823 | 0.64891 | 1.54591 | Pass |
| South Galactic pole | 1 | 9 | 0.94047 | 0.55729 | 3.80982 | Pass |
| North Galactic pole | 1 | — | — | — | — | No compatible pair in frozen bounded candidates |
| North b60 | 1 | 3 | −0.22380 | 1.27032 | 1.08062 | Pass |
| North b60 | 3 | 7 | 0.39833 | **2.14869** | 2.17409 | **Fail** |
| South b60 | 1 | — | — | — | — | Insufficient supported controls in frozen candidates |
| South b60 | 3 | 5 | −0.04391 | 1.16745 | 1.72707 | Pass |

The six measurable cells include **32 source/detector repeat comparisons involving 27 distinct Gaia sources**, across four fields, two detectors and both DR1 and QR3. All remain in the evaluation. North-pole D1 exhausts 24 frozen pairs with fewer than three wavelength-compatible controls, including after its transport-only retry. South-b60 D1 exhausts 23 pairs: 22 fail wavelength matching; the best pair has four spectrally matched controls but only two with sufficient support. Neither cell counts as a pass. South-b60 D3 selects the second ranked pair after the first input returns 503 on all three exact-file attempts.

Five-subpixel photometry also fails north-b60 D3 (scatter 2.03949). All **64** five-subpixel versus exact measurements differ by less than 0.1σ, with maximum 0.08338σ. Thus finite five-subpixel quadrature does not explain this failed stability gate. There was no threshold relaxation, source deletion, replacement pair or empirical uncertainty adjustment after measurement.

The native astrometry gate passes all twelve measured exposures, with 1445 matched-star observations and robust RMS including bias from 0.23482 to 0.41669 arcseconds. The maximum individual residual is 2.72566 arcseconds; three individual matches exceed 1.5375 arcseconds and are retained. The preregistered astrometry criterion is the robust RMS, not a claim that every star meets that individual limit.

### Separate secondary comparison: existing production integration

This table uses **center-pixel weights and constant local-WCS solid angle**, matching the existing production integration convention. It uses the same eligible source population as the primary study, without method-specific source selection. The error formula includes the same approximate median-annulus uncertainty.

| Field | Detector | Controls | Median z | Robust scatter | Maximum absolute z |
|---|---:|---:|---:|---:|---:|
| North Galactic pole | 3 | 3 | −0.38047 | 0.65378 | 0.82144 |
| South Galactic pole | 1 | 9 | 0.89686 | 0.57544 | 3.87985 |
| South Galactic pole | 3 | 5 | −0.53753 | 0.91841 | 1.53595 |
| North b60 | 1 | 3 | −0.08091 | 0.65250 | 1.15820 |
| North b60 | 3 | 7 | 0.18478 | 1.91056 | 1.97542 |
| South b60 | 3 | 5 | −0.26891 | 1.57992 | 1.33455 |

All six secondary cells pass the fixed thresholds. This supports retaining the existing integration method for the **screened population**, while tightening eligibility to full usable aperture support, at least ten clean local annulus pixels and supported field background. It does not show that flags alone establish isolation, certify crowded/saturated sources, establish all-band/all-sky performance, or calibrate detection significance. Retaining the baseline is not adoption of a new method or a retrospective change to the primary endpoint. No fractional-aperture production change is justified by this primary study.

Five isolated tests pass: analytic exact-circle area, independent-noise uncertainty with variable pixel solid angles, rejection of unknown integration methods, preservation of an individual stability failure, and an actually moving neighbor crossing the fixed isolation radius. Generated inputs are confined to tests. Earlier failed reports remain unchanged. This research script does not edit production processing.

## Why the earlier crowded-field failure is not an aperture-only diagnosis

The separate [historical diagnostic](../evidence/phase4/phase4-science-online-historical-diagnostic.json) revisits the same ten Phase 3 controls at their original extraction coordinates, using their retained real inputs. It is explicitly posthoc and cannot count as independent acceptance. The original −13.68σ outlier has a Gaia neighbor only 13.80 arcseconds away, **zero clean annulus pixels in both observations**, and a center-aperture flux change from 8656.51 to 6640.35 µJy (−23.29%). Its positive-aperture centroid offset changes from about −0.48 to −0.13 native pixels in x.

The embedded isolated-source EPSF predicts center-aperture response fractions 0.97608 and 0.97137, a change of only −0.48%. Its amplitude-plus-background fits have reduced χ²=65.8 and 66.3. These measured discrepancies show that aperture pixel phase alone is insufficient to explain the observed flux change. They support a blend/background/PSF-model mismatch concern without uniquely identifying its cause or proving the star constant. Many original controls also fail the stronger full-aperture or annulus prerequisites; they remain in the historical record and are not retrospectively removed to manufacture a passing gate.

The new high-latitude controls have much better catalog isolation and support. Passing their repeatability tests can validate a **restricted measurement method**, not retrospectively certify the old crowded scene, saturated targets, unmeasured detectors, absolute total flux, or astrophysical significance. Crowded sources require separately validated neighbor-aware modeling or explicit unusable-measurement output. The official IRSA tool's simultaneous source/sky fitting is a relevant comparison, but this investigation has not obtained an independently executed official Tractor result.

The [separate eligibility audit](../evidence/phase4/phase4-science-online-historical-eligibility.json) applies the proposed full-support/ten-annulus rule to the same ten historical controls. **Five are ineligible in both visits**, all because fewer than ten clean annulus pixels remain; this includes the −13.68σ outlier. Five remain eligible under this support-only rule. Their original results are not removed and no newly passing historical subset is claimed. Catalog isolation remains a separate requirement; support alone does not establish unblended or constant sources.

An implementation error during the first b60 preparation converted an Astropy FITS Header to a plain dictionary before rebuilding WCS; multiline COMMENT cards then failed ASCII validation. That run was interrupted before any b60 control flux, and preparation restarted with the original Header preserved. Raw successful downloads and frozen candidate ranks were reused; no observations were ranked by measured results.

## Reuse and remaining limits

`scripts/phase4_science_online.py` implements separate `--catalogs`, `--rank`, `--prepare`, `--preflight`, `--measure`, `--audit-isolation`, `--historical-diagnostic`, `--historical-eligibility` and `--summarize` stages. Frozen locks and final measurements refuse overwrite. Raw catalogs, observation FITS, spectral calibration and SAPM files remain under ignored `backend/.cache/phase4/online-science`, each with byte hashes and retrieval receipts. The final aggregate records the script hash and software versions; the tests run with `python -m pytest backend/tests/test_phase4_science_online.py -q`.

The finite sample is small and its dispersion estimates are noisy, but the preregistered thresholds were not relaxed. Image-pixel correlation, calibration covariance, PSF variation, source colors within finite spectral channels and true infrared variability remain unmodeled. Those limitations require a new independent protocol before stronger scientific claims. The measured outcomes support explicit eligibility and uncertainty limitations, not a promise that every arbitrary coordinate yields comparable data. The failed primary result remains a Phase 4 limitation even where the existing-method secondary comparison is useful.
