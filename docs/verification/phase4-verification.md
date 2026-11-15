# Phase 4 implementation and acceptance

> **Current continuation:** Historical API 1.4 checkpoint. The archive-first API 1.5 continuation, new independent controls and current validation are documented separately. [Details](phase4-online-verification.md).

Date: 2026-11-14. **Implemented technical work; scientific promotion remains
blocked.** Phase 4 is not an unconditional completion or cache-replacement claim.
The five approved revision-3 datasets remain unchanged. API 1.4.0 and repository
policy v1.6 document the coordinated additive metadata changes.

## What changed

- New image/spectrum builds preserve exact real input URLs, hashes and sizes;
  query/extraction coordinates; considered and contributing exposures; failed
  downloads; masks, background diagnostics, wavelength decisions and method
  versions; source/environment identity and output evidence. Public links name
  the scientific fingerprint rather than a mutable current-record alias.
- Product creation time comes from saved metadata. Observation bounds and
  reference-astrometry time scales are explicit; unknown historical lineage or
  retrieval times are not invented. Channel reasons/counts distinguish null,
  finite-but-rejected and eligible measurements.
- Pinned offline replay, bounded explicit acquisition and a source/input/environment
  bundle exporter reject missing/corrupt inputs and source/environment drift.
  Native numerical agreement and encoded-image agreement are reported separately.
- Corrected astrometry for all five targets is an explicit staged profile.
  Staging uses actual FITS UTC timestamps, keeps failed downloads, omits old
  reference overlays and never automatically overwrites the approved cache.
- Narrow UI copy/types expose accurate dates, telemetry meaning, eligibility
  counts, lineage and null-measurement explanations. The Phase 5 visual/navigation
  overhaul has not been implemented by this work.

The method remains the native 12.3-arcsecond center-pixel aperture. Fractional
aperture integration was investigated but not adopted without independent
acceptance. See [the contract](../decisions/phase4-contract-decision.md),
[schema](../reference/phase4-replay-schema.md), [replay instructions](../guides/reproducibility.md),
[worked examples](../guides/phase4-evidence-walkthrough.md) and
[shared meaning/vocabulary](../guides/result-meaning.md).

## R0: scientific decision and independent evidence

The preregistered Epsilon Indi holdout excluded the ten previously inspected
controls. Fresh catalogs contained 422 Gaia and 1,413 AllWISE entries. **Zero**
new controls passed the fixed quality, field and isolation screen; no holdout
fluxes were inspected. Four separately preregistered alternative D1 pairs all
failed the preliminary wavelength screen. This is insufficient independent
stability evidence, not a passing test and not a measured new stability failure.

The retained Epsilon Indi D3 pair passes two separate prerequisites: exact
release-matched CWAVE/CBAND matching across 54,756 output positions, and native
astrometry using 12/14 in-field Gaia references. RMS residuals are about
0.435/0.292 arcseconds; maximum residuals are about 0.587/0.913 arcseconds, below
the 1.5375-arcsecond criterion. These passes do not cancel the prior failed
control result. Full protocols, source hashes, selection outcomes and limitations
are in [the science verification](phase4-science-verification.md).

The corrected WISE solution queries `(133.76021647484097, -7.242224282436729)`
at 2025.8; corrected R Draconis queries
`(248.16723597981732, 66.7550234840942)`. The primary reference solution, reference
time format/scale, proper motions and caveats are recorded in
[the coordinate profile](../evidence/phase4/phase4-science-coordinate-profile.json). Production
coordinates are deliberately still coherent with their unchanged old assets;
the stage does not authorize labeling those assets as corrected.

## R1/R2: technical replay evidence

The first local curated bundle is `backend/.cache/phase4/replay-bundle`, containing
two analysis records and two shared real D3 inputs. Payload size is **9,447,256
bytes**, excluding its index. Its declared runtime is CPython 3.11.9, Windows
AMD64, NumPy 2.4.6, Astropy 8.0.2, reproject 0.21.0, Pillow 13.0.0, WCSLIB 8.6
and WebP 1.6.0; the bundle contains the complete relevant version record and
resolved package pins. Source files include uncommitted implementation changes.
The tracked [bundle index](../evidence/phase4/phase4-curated-bundle-index.json) has SHA-256
`6c4dc3870b711c29e596631ed94d9f05dfe84511d0b2d3135d2215411392bc18`.

Implementer strict replay passes for both analyses. Image measurement/variance/
flag/display-plane hashes, normalization and encoded assets match; both native
channels agree under the predefined `1e-10` relative/absolute tolerance. This
pair is a **visualization-compatible replay example**, not a scientifically
accepted variability comparison. Its actual dates are 2025-04-29 and 2025-05-01.

Independent image and finite-spectrum replay **passed** in a new isolated
CPython 3.11.9 environment, run by a separate reviewer agent on the same Windows
host. All 52 exported files independently passed size/hash verification; all
66 pinned distributions matched and `pip check` passed. No source/environment
drift override was used. Both numerical replays passed, including all ten encoded
image assets. This is a separate implementer/reviewer check, not an independent
human or different-platform replication. See the
[machine-readable review](../evidence/phase4/phase4-independent-replay-results.json).

Public permanent access is not established: the bundle
is retained locally outside Git, with an explicit maintainer transfer procedure
and no hosting/retention SLA. Revision-3 products have no reconstructed replay
record. Arbitrary-coordinate success everywhere is not claimed.

## R3: staged rebuild and rollback boundary

The staged acquisition attempts all image-contributor URIs retained in the five
old manifests, at the corrected query coordinates. This is a bounded, partial
historical inventory: old spectrum-only inputs and other archive observations
were not necessarily recorded. Upstream failures remain explicit.

Acquisition completed, followed by a **fully offline rebuild** from exact retained
inputs using the frozen processing source. All seven successful products (two
image products and five spectra) passed record-fingerprint, input-hash,
source/environment and product-link verification. This is provenance verification
of the stage; it is not a claim that every staged product was independently
numerically replayed or scientifically accepted.

| Corrected target | Verified padded inputs / recorded URIs | Image result | Spectrum present / finite / usable |
|---|---:|---|---:|
| WISE 0855 | 28 / 54 | No compatible pair in retained sample | 13 / 12 / 12 |
| Barnard's Star | 29 / 54 | No compatible pair in retained sample | 13 / 1 / 0 |
| Epsilon Indi B | 53 / 68 | Built, unpromoted | 37 / 21 / 20 |
| RW Aurigae | 43 / 53 | No compatible pair in retained sample | 34 / 30 / 16 |
| R Draconis | 42 / 60 | Built, unpromoted | 34 / 0 / 0 |

The second column describes the initial padded image-input/header acquisition.
Spectra use separately retained exact 0.2-degree cutouts; these counts are not
interchangeable. The fixed visit-selection limits and upstream failures explain
why a staged spectrum is not the entire release's channel inventory. All original
recorded URIs were attempted, but successful downloads do not establish complete
archive coverage. See [compact staging evidence](../evidence/phase4/phase4-staging-summary.json)
and the [full frozen report](../evidence/phase4/phase4-staging-results.json). The frozen report hash
is `99f60efae5dc96ddee0cfa60ea0781b09c1adf32e035edab847a9d67707d6c59`.

The new R Draconis null analysis is
`sha256:c4b8656866e0e7d9e028c14a862aafc82fe5870c220b759e060a6e1953833e34`.
All 34 channels have no clean aperture pixels and a hard-bad extraction center;
thirty also have unsupported background. Implementer strict replay preserves
the null flux/error and false eligibility. Its separate local retained bundle
contains **142,693,784 payload bytes**; the
[tracked index](../evidence/phase4/phase4-null-bundle-index.json) lists all files. The
[walkthrough](../guides/phase4-evidence-walkthrough.md#unavailable-measurement-r-draconis)
explains one actual channel and separates these reasons.

**Independent null replay also passed** in the separate reviewer's isolated
environment, using the bundled source and no drift overrides. All 83 bundle
files and 66 package pins verified. All 34 output channels retained null flux
and error, false eligibility and the same reason codes, with no numerical or
per-exposure differences. The null bundle index SHA-256 is
`6ab98594cfb6c627bb226107b3f49525d25547109d4cc09878ec765c57e2ff85`.
The [independent review](../evidence/phase4/phase4-independent-replay-results.json) now records
all three cases: image, finite spectrum and null spectrum. These are same-host
fresh-environment checks by another agent, not independent human science review.

As additional implementer checks, both corrected staged image products
(Epsilon Indi and R Draconis) also passed strict numerical/normalization and
encoded-asset replay. Their local reports are retained under
`backend/.cache/phase4/frozen-eps-image-replayed` and
`backend/.cache/phase4/frozen-rdra-image-replayed`.

The final staged report records target-by-target outcomes. Passing a build is
not scientific acceptance. Reference overlays require their own real rebuild
in the corrected WCS. Promotion also requires independent stable controls,
all-five physical/provenance checks and coordinated frontend/catalog migration.
No automatic promotion or rollback mutation is performed; the approved original
288 files are the unchanged rollback boundary.

## R4 and remaining acceptance

The walkthrough, vocabulary, reason-code dictionary, mathematical explanation
and public/internal metadata capability map are written. They explain the finite
example, unavailable measurements and limits without requiring source-code
reading. This is a technical explanation foundation. Human novice/expert task
testing remains a Phase 5 acceptance gate; automated replay cannot prove that
the UI is understandable.

| Package | Current acceptance |
|---|---|
| R0 science repair | Corrected reference decisions and prerequisites documented; independent stability/promotion blocked. |
| R1 lineage/time semantics | Implemented for new products; legacy unknowns preserved; API 1.4 coordinated. |
| R2 replay/bundle | Real image, finite-spectrum and null-spectrum replay passed in a separate fresh environment; public retention remains open. |
| R3 staged replacement | Staging implemented and executed separately; promotion not approved. |
| R4 explanation/handoff | Technical documents and narrow semantic UI work delivered; human comprehension unverified. |

To close Phase 4 scientifically, preregister another suitable independent field/
visit sample before inspecting residuals, obtain enough isolated controls,
evaluate the chosen aperture method with unchanged acceptance thresholds, and
rebuild/review all affected products and references. A failed or insufficient
result must remain visible; choosing a dramatic-looking example does not close
the gate. Phase 5 design can use the explicit limitations, but it must not present
unvalidated legacy products as a newly validated release.

## Regression verification

The full backend run passes **242 tests, no skips** with the retained real inputs.
One upstream FastAPI/Starlette deprecation warning remains. This suite includes
lineage tamper/missing-input rejection, offline behavior, real finite/null native
extraction, real image replay, corrected-profile isolation, stable saved timestamps
and historical unknown metadata. A clean clone without the separately retained
audit FITS files explicitly skips the corresponding real-input tests.

Frontend semantic tests, real-data tests, TypeScript checking and production
build pass. A narrow Chrome smoke check of API 1.4 at desktop 1440 by 1000 and
mobile 390 by 844 passes on real legacy R Draconis/WISE data without intercepted
responses. It verifies stable creation time, 0/240 finite R Draconis samples,
legacy unknown metadata and the actual telemetry plane/meaning. No JavaScript
errors were observed. New staged links were tested as metadata, not as a promoted
browser dataset. See [UI verification](phase4-ui-metadata-verification.md).

`scripts/verify_real_data.py --require-dist` and `git diff --check` pass; all
288 approved real-cache files match their inventory hashes. The local Python
environment is excluded from Git and was already excluded from Docker context.
The temporary Phase 4 API and UI servers were stopped after verification.
No new container, public deployment or broad arbitrary-coordinate scientific
acceptance is claimed.
