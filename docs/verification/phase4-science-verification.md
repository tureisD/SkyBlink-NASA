# Phase 4 R0: independent holdout and coordinate decisions

Date: 2026-11-14. **Scientific promotion is blocked.** The independent
holdout has insufficient isolated controls; the separately preregistered
alternative pairs fail spectral comparability. No new control-star flux
stability result exists, and the fractional-aperture method has not been
validated for production adoption. The Phase 3 failed ten-control result and
all five shipped datasets are unchanged.

This investigation nevertheless delivers a reusable independent aperture
validator, exact proposed coordinate solutions, fresh optical/infrared
screening, independent native D3 astrometry, and a release-matched D3
CWAVE/CBAND comparison. Passing those prerequisites does not substitute for
the missing stability test.

## Preregistration and independence

The first [frozen protocol](../evidence/phase4/phase4-science-preregistration.json) was written
before acquiring the holdout catalogs or inspecting holdout fluxes. Its
SHA-256 is
`75840b11617cea84a777aae74ff3506dbbf3591ca0e6f72c7a4a99b8e249a858`.
The parent approved the method before execution. It records the exact two
Epsilon Indi D3 inputs and their hashes, all ten excluded Phase 3 Gaia IDs,
selection order, masks, uncertainty calculation, thresholds and failure policy.

Using disjoint sources in the same exposure pair would provide an independent
source holdout, not an independent instrument/systematics sample. The pair
was already known to have compatible approximate wavelengths. Its actual
observation dates are 2025-04-29 and 2025-05-01, despite the historical saved
epoch labels. No epoch or coordinate migration is performed by this audit.

The fixed screening requires:

- Fresh Gaia DR3 neighbors down to G=20 in a 0.18-degree cone; controls with
  G=10–17, RUWE at most 1.4, proper motion at most 100 mas/year, absolute
  parallax at most 10 mas, and no Gaia `VARIABLE` classification.
- No previously tested control ID; at least 30 arcseconds from the target;
  the full 31-arcsecond neighborhood inside the requested field at both dates.
- No Gaia neighbor within 30.75 arcseconds at either observation time.
  Proper motions are propagated from the Gaia reference epoch. Missing
  neighbor motions would be reported as a limitation; none were missing here.
- Exactly one AllWISE match within 3 arcseconds after propagating the Gaia
  position to 2010.5, with no other AllWISE catalog entry within 30.75 arcseconds.
  The infrared neighbor query has no magnitude cut. Required W1/W2 quality:
  `ph_qual` A/B, `cc_flags` zero, variability digits 0/1, SNR at least 10,
  and `ext_flg=0`. Unknown variability does not silently pass.
- Lock at most twenty catalog-eligible sources in ascending numeric Gaia ID
  order before extracting their flux. Never replace a locked source because
  its measurement fails.
- Complete usable aperture support for both integration methods, supported
  field background, at least ten clean annulus pixels and SNR at least five
  for both methods in both visits.

The stability thresholds retain the Phase 3 values: at least three controls,
absolute median standardized residual at most one, robust scatter at most
two and maximum absolute standardized residual at most five. The robust
scatter is `1.4826 * median(abs(z - median(z)))`. There is no residual clipping
or threshold tuning. Catalog isolation is stronger than the Phase 3 screen,
but cannot rule out unresolved companions, subthreshold objects, or actual
infrared variability.

## Actual holdout outcome

Fresh [Gaia TAP](https://gea.esac.esa.int/tap-server/tap/sync) returned **422
sources**. AllWISE TAP timed out after the bounded request; the documented
[IRSA Gator interface](https://irsa.ipac.caltech.edu/applications/Gator/GatorAid/irsa/catsearch.html)
then returned **1,413 real AllWISE entries** for the same cone and fields.
Both responses, exact queries, byte counts and hashes are retained under
ignored `backend/.cache/phase4/science` and referenced by the
[result](../evidence/phase4/phase4-science-results.json). This fallback changes transport, not
catalog selection. VOTable ERROR/OVERFLOW and row-cap results fail closed.

| First applicable rejection | Sources |
|---|---:|
| Gaia quality limits | 321 |
| Outside the guarded field | 58 |
| Gaia neighbor within the fixed radius | 21 |
| Previously inspected Phase 3 control | 10 |
| AllWISE neighbor within the fixed radius | 12 |
| Eligible catalog controls | **0** |

All twelve candidates that survived the earlier gates failed infrared
isolation. The [control lock](../evidence/phase4/phase4-science-control-lock.json) is explicitly
empty. No new control flux was extracted; both aperture stability outcomes
are **insufficient**, not pass or measured failure. The isolation radii were
not reduced to obtain a sample.

## Separately preregistered alternative search

The [second protocol](../evidence/phase4/phase4-science-search-preregistration.json), SHA-256
`a4649d7a62da0f58d7f3e49068398a1704e37a5d961367b27efaa2483a0ce3dd`,
preserves the first empty result and fixes four different D1 field pairs in
advance. It uses the recorded first/last D1 exposures already retained for
the astrometry audit. It would select the first spectrally compatible pair
with sufficient catalog controls, using unchanged isolation and measurement
thresholds, before inspecting flux. There is no post-flux replacement.

All four pairs fail the initial nine-position wavelength screen within the
central 0.12-degree region of the existing cutouts. A passing pair would
require padded downloads and the full requested 0.2-degree dense check; none
reached that step. The central values below illustrate the mismatch; the
actual decision uses all nine positions and bandwidth checks.

| Fixed order | First/second central wavelength (µm) | Outcome |
|---|---|---|
| WISE 0855 D1 | 0.992608 / 1.090830 | Incompatible |
| R Draconis D1 | 0.943596 / 1.008226 | Incompatible |
| Barnard's Star D1 | 0.750143 / 0.775609 | Incompatible |
| RW Aurigae D1 | 1.068350 / 0.981763 | Incompatible |

The [search result](../evidence/phase4/phase4-science-search-results.json) retains every outcome.
No additional archive image or control flux was needed for these rejections.
This bounded search says nothing about the existence of better pairs elsewhere
in the archive. Finding them requires a new prospective sample protocol.

## Reusable aperture comparison

`scripts/phase4_science_validation.py:measure` implements the candidate
five-subpixel aperture independently of production extraction. Center-pixel
and fractional methods use the same prepared native image, mask, local median
annulus and constant WCS-derived pixel solid angle. For weights `w`, conversion
`K = 1e12 * Omega_pix`, intensity `I` in MJy/sr and variance `V` in
`(MJy/sr)^2`:

```text
F = K * sum(w * (I - b))
Var(F) = K^2 * [sum(w^2 * V) + sum(w)^2 * Var(b)]
Var(b) = max[(pi/2) * mean(V_ann)/N_ann,
             1.2533^2 * MAD_scaled(annulus)^2/N_ann]
```

The aperture radius is 12.3 arcseconds. The annulus retains native
pixel-center radii 3–5. The holdout deliberately rejects fewer than ten clean
annulus pixels instead of using the production global-background fallback.
Any excluded fractional boundary pixel disqualifies a complete-support
control, even when the center-pixel aperture would not contain it. Aperture
and annulus must fit inside the image.

The variance term uses **squared integration weights**. It is not the
Phase 3 exploratory statistic that divided changed fractional fluxes by
unchanged center-pixel errors. No aperture correction, pixel solid-angle
map, detector covariance, complete background-model covariance or deblending
is claimed. The method has only mathematical regression validation here:
actual independent real-source stability could not be measured.

Eight focused tests pass. They check fractional area across pixel phase,
uncertainty against 30,000 independent seeded Gaussian noise trials, missing
annulus/background support, fractional-boundary warnings, truncated support,
catalog overflow, empty/previous-control rejection, and preservation of failed
evidence during replay. Constant arrays, controlled flags and noise trials
are explicitly **generated test-only inputs**, not scientific observations.

## Independent D3 prerequisites

The [prerequisite report](../evidence/phase4/phase4-science-prerequisites.json) evaluates the
original Epsilon Indi pair without treating it as a successful control sample.

Independent native-image peak detection and Gaussian centroid fitting against
the fresh Gaia catalog pass the fixed 1.5375-arcsecond robust-RMS threshold:

| Observation date | Stars within requested field | Robust RMS including bias | Largest residual |
|---|---:|---:|---:|
| 2025-04-29 | 12 | 0.434595″ | 0.586534″ |
| 2025-05-01 | 14 | 0.292140″ | 0.913385″ |

These final counts exclude the padded perimeter. No star is removed based on
its final residual. The comparison uses native D3 centroids, not saved coadds
or all detectors; the Gaussian PSF model and absence of observer-parallax
correction remain limitations. Its stars support positional registration,
not certified infrared constancy or the stricter AllWISE holdout isolation.

The official [DR1 D3 calibration product](https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/dr1/spectral_wcs/cal-swcs-v5-2026-191/3/spectral_wcs_D3_spx_cal-swcs-v5-2026-191.fits)
contains 33,312,960 bytes, SHA-256
`51750c8f948a30541d391e54930279aa067c62c398a7cc2679e592bc6044427a`.
Both exposures have matching detector/release, `DETCOORD=sky`, and exact
equality of all X/Y/VALUES arrays in their WCS-WAVE tables. Calibration UUID
identity is not inferred when the standalone product does not expose it.

CWAVE/CBAND are bilinearly sampled at all **54,756 retained output centers**
after mapping spatial WCS positions to original detector coordinates using
`x_original = 1 + x_cutout - CRPIX1A` and the analogous Y expression. The
calibrated pair passes: maximum wavelength separation divided by narrower
bandwidth **0.00569013** (limit 0.25), minimum bandwidth ratio **0.986641**
(limit 0.8). WCS-WAVE differs from these calibrated samples by up to **1.073
nm in wavelength** and **1.637 nm in bandwidth**. Per-pixel calibration
interpolation is not full filter-response or PSF equality.

This extends measured calibration coverage from the prior D6 subset to this
D3 pair. It does not establish all-band/release calibration and does not
authorize a general variability claim.

## Proposed coordinate profile

[The staged coordinate profile](../evidence/phase4/phase4-science-coordinate-profile.json)
preserves complete primary coordinate/motion/epoch solutions, source hashes,
time formats/scales and derived barycentric directions. It proposes a uniform
Gaia DR3 reference epoch for the four Gaia targets and the full published
Kirkpatrick solution for WISE 0855.

| Target | Reference solution | Proposed RA / Dec at decimal year 2025.8 TT (degrees) |
|---|---|---|
| WISE 0855 | Kirkpatrick 2021 Table 5; MJD 57633.39 | 133.760216474841 / −7.242224282437 |
| Barnard's Star | Gaia DR3 4472832130942575872; J2016.0 TCB | 269.446312919114 / 4.767629180930 |
| Epsilon Indi B | Gaia DR3 6412596012146801152; J2016.0 TCB | 331.096249633630 / −56.800525858408 |
| RW Aurigae | Gaia DR3 156430822114424576; J2016.0 TCB | 76.956089530008 / 30.401130005743 |
| R Draconis | Gaia DR3 1648328016354496384; J2016.0 TCB | 248.167235979817 / 66.755023484094 |

WISE's adopted reference position is RA **133.780984°**, Dec **−7.243932°**,
PM RA* **−8123.7 mas/year**, PM Dec **+673.2 mas/year**. Preserve MJD 57633.39
internally, using the stated UTC interpretation; the table does not explicitly
resolve its epoch time scale, whose effect is negligible here relative to
the positional uncertainty. Decimal year 2016.6704644808742 is a display
equivalent, not permission to round away the reference time. The primary
[Kirkpatrick et al. 2021 table](https://doi.org/10.3847/1538-4365/abd107) and its
[CDS catalog](https://cdsarc.cds.unistra.fr/viz-bin/cat/J/ApJS/253/7) support
this complete solution. The frozen position differs by about 3.60 arcseconds.

R Draconis uses reference RA **248.1673783672889°**, Dec
**66.75500674547219°**, PM RA* **−20.642811719160797 mas/year**, PM Dec
**+6.148818852711324 mas/year**. This replaces the mixed reference/motion
combination with one documented Gaia solution. Variable-star photocenter
limitations remain. Epsilon Indi's RUWE ≈4.30 and unresolved binary nature,
and RW Aur's binary/variable nature, also require visible caveats.

All propagation uses Astropy angular space motion. Parallax is retained as
source metadata, not added as observer-dependent displacement; no radial
velocity/perspective acceleration is included. **J2016.0 TCB is not the same
encoding as decimal year 2016.0 TT.** Preserve exact format and scale in the
staged internal profile, and generate query centers and reticles from that
same source. The science script does not edit production targets or caches.

## Reproduction and next gate

```powershell
.venv311/Scripts/python.exe scripts/phase4_science_validation.py --register
.venv311/Scripts/python.exe scripts/phase4_science_validation.py --download
.venv311/Scripts/python.exe scripts/phase4_science_validation.py --analyze
.venv311/Scripts/python.exe scripts/phase4_science_validation.py --coordinates
.venv311/Scripts/python.exe scripts/phase4_science_validation.py --prerequisites
.venv311/Scripts/python.exe scripts/phase4_science_validation.py --register-search
.venv311/Scripts/python.exe scripts/phase4_science_validation.py --search
.venv311/Scripts/python.exe -m pytest backend/tests/test_phase4_science.py -q
```

The required original FITS/primary catalog inputs are the hashed Phase 3
research files; acquire them with the corresponding Phase 3 audit scripts if
absent. `--analyze` performs no network requests. `--download` and
`--prerequisites` may retrieve missing official catalog/calibration bytes.
No raw FITS or catalog is packaged as a product. Recorded holdout/search
results retain their original timestamp and bytes on identical replay;
changed outcomes require a new reviewed report instead of overwriting them.

To close R0, preregister another genuinely independent, spectrally compatible
sample with sufficient isolated infrared controls, then measure both methods
with correctly propagated errors. Source/field search may be expanded in a
new version, but the thresholds and failed evidence above must survive.
Only a successful independent measurement and explicit method decision can
justify production adoption or scientific cache promotion. A diagnostic
staged build may still be useful if clearly marked unvalidated.
