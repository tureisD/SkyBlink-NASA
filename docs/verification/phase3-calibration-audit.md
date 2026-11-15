# Phase 3 calibration and target-astrometry audit

Measured on 2026-11-14. Reproducible results, query parameters, input hashes, all 32 flag-bit slots, and source positions are in [phase3-calibration-audit.json](../evidence/phase3/phase3-calibration-audit.json). The executable audit is [phase3_calibration_audit.py](../../scripts/phase3_calibration_audit.py). This work changes no target coordinate, production mask, or golden-cache file.

The current flag definitions match the official supplement. The wavelength lookup is demonstrably an approximation, including bandwidth errors of several nanometers. The WISE 0855 reference coordinate/epoch combination is inconsistent with both published modern astrometry and an independent reconstruction from HST measurements: the frozen 2025.8 center is about **3.60 arcsec** from the published solution. These are separate results; a correct flag table does not validate the target trajectory or spectral calibration.

## 1. Current official flag table

The current [SPHEREx Explanatory Supplement](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp.pdf) is **version 2.1, 2026-11-10**. Table 16 is on PDF pages **33–35**. The older `_QR.pdf` URL used in previous project documentation still returns version 2.0. The current PDF was downloaded, parsed, and hashed; its SHA-256 is `9f3085cea74c6cdb647cc373bef27aaae50e394d348402e68ea2558ea06011cd`.

All **23 defined bit names and numbers** match `backend/core/flags.py`. Positions 3, 4, 5, 8, 13, 16, 18, 30, and 31 have no definition in Table 16; the audit does not invent meanings for them.

| Bit | Official name | Current display classification | Excluded from flux measurements |
|---:|---|---|---|
| 0 | TRANSIENT | Warning | Yes |
| 1 | OVERFLOW | Warning | Yes |
| 2 | SUR_ERROR | Hard | Yes |
| 6 | NONFUNC | Hard | Yes |
| 7 | DICHROIC | Warning | Yes |
| 9 | MISSING_DATA | Hard | Yes |
| 10 | HOT | Hard | Yes |
| 11 | COLD | Hard | Yes |
| 12 | FULLSAMPLE | Informational | No |
| 14 | PHANMISS | Hard | Yes |
| 15 | NONLINEAR | Hard | Yes |
| 17 | PERSIST | Warning | Yes |
| 19 | OUTLIER | Warning | Yes |
| 20 | CROSSTALK | Warning | Yes |
| 21 | SOURCE | Known source | No |
| 22 | GHOST | Warning | Yes |
| 23 | GHOST_FPA | Warning | Yes |
| 24 | GHOST_EXT | Warning | Yes |
| 25 | STREAK | Warning | Yes |
| 26 | BLOOM | Hard | Yes |
| 27 | SNOWBALL | Hard | Yes |
| 28 | HALO | Hard, with existing explicit display exception | Yes |
| 29 | SATELLITE_HALO | Hard | Yes |

The hard/warning split is application policy, not a second official flag table. DICHROIC is unsuitable for photometry despite being displayed as a warning. HALO exclusion is more conservative than the supplement's caution. GHOST_FPA remains unused and is planned for removal in Year 2 processing. SOURCE and FULLSAMPLE must not become blanket bad-pixel exclusions. Actual affected-pixel and measurement tests are reported in the separate Phase 3 science results.

## 2. CWAVE/CBAND comparison with the visualization lookup

The current [IRSA product documentation](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/) explicitly directs science analysis to **CWAVE and CBAND**, and describes WCS-WAVE as a compact visualization approximation. The audit downloaded the real DR1 detector-6 calibration product, **cal-swcs-v5-2026-191**, from the [NASA IRSA public bucket](https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/dr1/spectral_wcs/cal-swcs-v5-2026-191/6/spectral_wcs_D6_spx_cal-swcs-v5-2026-191.fits): 33,312,960 bytes, SHA-256 `19195d253892883586aa2183cb66238b32f6032ade62d490b36b85b0dd18f212`.

Pairing checks are essential here. Both input exposures and the calibration are DR1/D6, both use `DETCOORD=sky`, and **all X, Y, and VALUES arrays of their WCS-WAVE tables are exactly equal**. This provides a direct numerical compatibility check, beyond trusting a filename. The science exposure's calibration UUID is preserved in the JSON, but the standalone calibration does not expose the same UUID, so UUID identity is not claimed.

For each integer cutout pixel, the audit obtains the original zero-based active detector pixel using the official cutout relationship:

```text
x_original = 1 + x_cutout - CRPIX1A
y_original = 1 + y_cutout - CRPIX2A
```

It reads `CWAVE[y_original, x_original]` and `CBAND[y_original, x_original]`, and compares them with `WCS(IMAGE.header, fobj=hdul, key="W")` after setting `sip=None`. No extra MWIR X flip is applied: the calibration is already in `sky` orientation. Science extensions are accessed by name; the primary HDU supplies header metadata only.

These are **all-pixel comparisons on two real cutouts**, rather than comparisons at one favorable coordinate:

| Recorded sample | Pixels | Absolute wavelength error, median / p99 / maximum (nm) | Absolute bandwidth error, median / p99 / maximum (nm) |
|---|---:|---:|---:|
| WISE 0855, 2025_E1 D6 | 28,224 | 0.386 / 1.279 / 2.069 | 0.630 / 2.689 / 4.391 |
| WISE 0855, 2025_E2 D6 | 23,547 | 0.503 / 1.152 / 1.614 | 2.346 / 3.492 / 3.809 |

The calibration's own header records maximum wavelength/bandwidth approximation errors of **2.823 / 4.923 nm**, respectively. Thus “~1 nm” must not be interpreted as an upper bound on either quantity. Maximum relative bandwidth errors in the tested cutouts are **13.31% and 11.48%**.

At the nearest native pixel to the existing query center, calibrated wavelength/bandwidth are **4.967176 / 0.039115 µm** for the first exposure and **4.417258 / 0.034775 µm** for the second. The lookup bandwidth differs by 1.927 and 2.470 nm. The roughly 0.55 µm difference between these two exposures is much larger than a resolution element: detector number alone cannot establish a valid temporal comparison.

This verifies one calibration product against two compatible DR1 inputs. It does **not** validate every detector/release or convert the lookup into a science calibration. Future extraction labels should state `WCS-WAVE (sip=None; approximate visualization lookup)` until exact calibration products are integrated. A later implementation must select the matching release/version, preserve original detector coordinates, and cache the calibration separately from rendered assets.

## 3. Four targets checked directly against Gaia DR3

The audit queried the [ESA Gaia archive TAP service](https://gea.esac.esa.int/tap-server/tap/sync) by source ID. The response, exact ADQL, and response hash are retained. Each record gives an ICRS reference epoch of **2016.0 TCB**. Positions were propagated with Astropy to decimal year **2025.8 TT**, using proper motion without observer parallax or perspective acceleration, matching the current product's barycentric-direction convention.

| Target | Gaia DR3 source ID | PM RA* / Dec (mas/yr) | RUWE | Separation from stored 2025.8 center |
|---|---|---:|---:|---:|
| Barnard's Star | 4472832130942575872 | −801.550978 / +10362.394207 | 1.085 | 0.115″ |
| Epsilon Indi B | 6412596012146801152 | +3981.976663 / −2466.831815 | 4.296 | 0.135″ |
| RW Aurigae | 156430822114424576 | +2.640643 / −27.397583 | 1.500 | 0.113″ |
| R Draconis | 1648328016354496384 | −20.642812 / +6.148819 | 1.298 | 0.838″ |

**Epsilon Indi B does have a Gaia source.** The earlier “no Gaia B source” statement was wrong. Its Gaia proper motion agrees with the stored rounded values, and the stored J2000 reference position agrees with Gaia propagated backward. Its large RUWE and binary nature nevertheless make it a poor precision astrometric control. The identification is also discussed in the primary [Gaia companion study by Kervella et al.](https://doi.org/10.1051/0004-6361/202142146).

R Draconis combines a reference position consistent with Gaia at J2000 with a different, insufficiently sourced proper motion, **−13.7 / −31.0 mas/yr**. The Gaia declination motion has the opposite sign. The difference is small compared with a native pixel, but its reticle/trajectory should not be described as externally validated. Phase 4 should adopt one documented reference solution and record the variable-star caveat. Gaia agreement for binaries and variables is not proof that an unresolved infrared photocenter lies at the same location.

The JSON includes original catalog coordinates, epoch, parallax, excess noise, stored values, back-propagated J2000 coordinates, and residual vectors for all four targets.

## 4. WISE 0855: published solution and independent sign check

The stored motion **−8118 / +680 mas/yr** is supported by [Luhman & Esplin 2016, Tables 2 and 4](https://arxiv.org/abs/1605.06655). The problematic combination is the stored reference position **133.79513°, −7.24515°** with a claimed epoch of **2010.0**. A position-based object name or equinox label does not determine an observation epoch.

A complete later solution is available in [Kirkpatrick et al. 2021, Table 5, archived by CDS](https://cdsarc.cds.unistra.fr/viz-bin/cat/J/ApJS/253/7). The Harvard VizieR mirror returned the primary table successfully; the Strasbourg ASU endpoint returned 404 during this audit. The matching row is:

| Quantity | Published value |
|---|---|
| Reference RA / Dec | 133.780984° / −7.243932° |
| Reference epoch | MJD 57633.39, approximately 2016.670464 |
| Position errors | 2.3 mas per coordinate |
| PM RA* / Dec | −8123.7 ± 1.3 / +673.2 ± 1.3 mas/yr |
| Absolute parallax | 439.0 ± 2.4 mas |
| Fit | 19 Spitzer epochs, 46 Gaia DR2 reference stars, reduced χ² 0.59 |

Propagating that solution gives a barycentric 2025.8 position of **133.76021647484°, −7.24222428244°**, **3.601845″** from the frozen query center. The indicative diagonal-only propagated uncertainty is about 12 mas per coordinate; full covariance is not supplied in this table. Back-propagating gives **133.79615763400°, −7.24517912735° at 2010.0**. No observer-parallax displacement has been added to either coordinate.

An independent diagnostic uses six actual HST positions from Luhman & Esplin Table 2. It subtracts the published proper motion and the Earth-observer parallax factors, using the paper's 449 mas parallax. Astropy's builtin Earth barycentric ephemeris approximates HST's observer position; **Spitzer positions are excluded from this Earth approximation**. The script retains all six measurements and uses:

```text
P_RA  = X sin(alpha) - Y cos(alpha)
P_Dec = X cos(alpha) sin(delta) + Y sin(alpha) sin(delta) - Z cos(delta)
observed_position = reference_position + proper_motion * elapsed_years + parallax * P
```

This yields 2010.0 reference coordinates **133.79617443481°, −7.24518786025°**, with epoch scatter of **13.54 mas in RA* and 16.35 mas in Dec**. Reversing the parallax sign increases the scatter to **571.48 / 137.52 mas**, providing a sensitive sign check. A separate five-parameter weighted fit to those six HST epochs gives parallax **467.5 ± 19.0 mas**, PM **−8098.9 ± 18.8 / +656.0 ± 15.4 mas/yr**, and χ² **2.98 for 7 degrees of freedom**, consistent with the published solution at the precision of this short subset. Input measurement uncertainties are used directly, without rescaling them to produce a favorable fit.

The reconstructed 2025.8 position differs from the complete 2021 solution by about **0.171″**. Its small epoch scatter is not a total uncertainty: the 2016 paper's proper-motion errors alone contribute approximately **81 / 71 mas** when extrapolating from the mean HST epoch to 2025.8. HST orbit, rounded coordinates, frame differences, and the approximate tangent-plane model also limit this diagnostic. It is independent evidence of the reference-epoch problem, **not a replacement catalog solution**.

The proposed Phase 4 correction is to adopt a complete published coordinate/epoch/motion solution together, regenerate the reference reticle and propagated center, and rebuild the cache. A simple change to the displayed epoch is insufficient without checking the perpendicular residual and the source of the original reference coordinate. The current frozen coordinates and revision-3 cache remain unchanged.

## 5. Reproduction and limits

```powershell
.\.venv311\Scripts\python.exe -m pip install pypdf
.\.venv311\Scripts\python.exe scripts/phase3_calibration_audit.py --download
```

`pypdf` is an audit-only dependency; runtime requirements were not changed. Without `--download`, the script performs no network requests. The science audit must first supply its real cutout inventory; no cutouts are fabricated when inputs are unavailable. Each downloaded product is capped at 40 MB, stored under ignored `backend/.cache/phase3`, and hashed. The calibration download is 33.31 MB. Successful reruns report five explicit outcomes, including the WISE inconsistency rather than treating it as a pass.

These results do not establish full all-detector calibration, externally calibrated image astrometry, aperture-corrected fluxes, or physically validated variability. Those remain separate checks in Phase 3 and inputs to the Phase 4 rebuild. No existing saved observation was rewritten to make this audit pass.
