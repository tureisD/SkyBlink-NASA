# Catalog acquisition: source review

Reviewed 2026-11-15 in response to repeated single-epoch and incomplete-download
results in the catalog tour. This review separates useful acquisition changes
from changes that would alter what a temporal comparison means. Implementation
and measured outcomes are recorded in
[the verification report](../verification/phase5-catalog-reliability-and-viewer.md).

**Later discovery outage:** the corrected worker subsequently reproduced
SIA/TAP proxy errors, including outside the application. Known image URLs still
served real FITS data. API 1.6 therefore adds an explicit catalog-only recovery
choice: a bounded previously verified exposure list plus fresh image downloads.
It is not a second live discovery service and never runs automatically. The
live-search default and comparison gates remain. See [contract and scope](../decisions/known-exposure-contract-decision.md)
and [outage/recovery evidence](../verification/phase5-discovery-outage-verification.md).

## What the warning establishes

`PARTIAL_DOWNLOAD_NO_MATCHED_PAIR` describes the inputs accepted by one bounded
request. It does not establish that the archive contains only one epoch.
Discovery, transfer, candidate selection and measured compatibility are separate
stages. Diagnose their retained records before concluding that a target lacks
coverage. An earlier successful test is also not proof that the user's running
process uses the same code, settings or upstream conditions.

The required acceptance is a fresh request through the development UI's actual
backend, with observation dates, selected bands, input receipts and served
assets checked. An isolated test server remains useful for diagnosis but cannot
alone establish that the reported development-server failure is fixed.

## Reproduced development-server discrepancy

The existing `localhost:8000` worker was started before the method-12 changes.
An actual fresh Barnard request returned `matched_image_comparison/11`, complete
discovery, one epoch and `PARTIAL_DOWNLOAD_NO_MATCHED_PAIR` after 106.485 seconds.
Its lineage showed the earlier 54-input acquisition batch. The identical query
on a newly started process returned method 12 and a matched visual pair after
40.407 seconds. The newer code was on disk, but the browser-connected worker
had not reloaded it. This establishes a stale process; it does not establish
the precise cause of the watcher's failure.

The corrective action is to restart the actual development backend, identify
the loaded image method at startup, narrow development reload watching to
application source directories and verify all five fields on that backend.
The narrower watcher detected an edit but its Windows background child did
not finish restarting. Hidden/background sessions therefore use
`python scripts/dev_api.py --no-reload` with explicit restarts; the default
interactive launcher retains source watching. Do not interpret the presence
of a reload parent as evidence that a new worker has started.

The application now captures source identity after startup imports, checks it
before fresh sky/spectrum acquisition and again before creating an analysis
record. Source changes return the existing 503 envelope with
`detail.reason=PROCESSING_SOURCE_CHANGED` and a restart instruction. Documents,
frontend files, tests and cache contents are excluded from the processing
source check. This catches subsequent source drift; it is not an attestation
against simultaneous file changes during startup imports. Standalone replay
tools continue to capture their explicitly invoked source environment.

The stale diagnostic records are retained. Their disk fingerprints must not
be treated as evidence of the actually loaded old code: they mixed a method-11
worker with newer on-disk source hashes. The guard prevents this particular
mislabeling on future application builds; it does not repair historical records.

No alternative transport or relaxation of scientific gates is justified by
this discrepancy alone. Final outcomes, including any remaining upstream
failures, belong in the linked verification report.

## Official alternatives reconsidered

| Route | What it can help with | Boundary |
|---|---|---|
| DR1 and QR3 wide/deep SIA inventories | Locate the available current-release exposures, including additional polar coverage. | Failed collection searches must remain explicit. SIA can lag newly ingested products by about a day. |
| TAP discovery | Another query interface when SIA discovery fails or misses newly ingested products. | It still uses IRSA infrastructure and consumes the same request budget; it does not guarantee an independent outage domain. |
| IRSA spatial cutouts | Fetch the science, variance, flags, foreground and wavelength information needed for the existing pipeline with smaller transfers. | Server-side cutout preparation and transfer can fail or exceed a bounded stage. |
| Official AWS DR1/QR3 mirror | An alternative transport for original spectral-image files if the on-premises service is the bottleneck. | The mirror is the same observation, not another epoch. Full images are roughly 70 MB. Any integration must preserve exact extension/WCS semantics, bounded transfers and truthful source receipts. |
| DR1 all-sky spectral cube / HiPS | Spectral context or a separately labeled mosaic inspection feature. | The 102 layers are wavelength channels, not 102 observation dates. The cube has 12.9 arcsec pixels and cannot replace the missing temporal partner. |
| Gaia, WISE, NEOSSat and other mission images | Independently labeled cross-mission context. | Different instruments and passbands cannot be silently relabeled as another SPHEREx epoch or passed into the existing SPHEREx difference calculation. |
| Explicit saved real examples | Inspect historical observations without waiting for a fresh archive build. | Saved mode remains an explicit user choice with historical limitations. No automatic substitution when archive acquisition fails. |

The current archive guide identifies DR1 plus QR3, including their deep
collections, as the current searchable spectral-image releases. QR2 is
superseded and is not an appropriate hidden fallback to claim a new observation.
[IRSA data access](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access/).

IRSA documents a public, anonymous AWS mirror in `nasa-irsa-spherex`, region
`us-east-1`, with `dr1` and `qr3` prefixes.
[IRSA cloud access](https://irsa.ipac.caltech.edu/cloud_access/).

The product guide describes the spectral images, their position-dependent
passbands, spatial cutouts and the distinct all-sky cube. These are the reasons
to retain measured wavelength agreement even when changing acquisition routes.
[IRSA data products](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/).

## Acceptance boundaries

- Repeat the five named fields sequentially with `source=archive` at the visible
  requested field size. Retain unsuccessful attempts as well as later successes.
- Record discovery completeness separately from download completion and the
  existence of an accepted pair. Completing a pair does not retroactively make
  every attempted download successful.
- Check fresh input receipts, actual distinct observation times, identical
  selected-band composition, measured compatibility and immutable output hashes.
- Preserve arbitrary-coordinate support; avoid target-name exceptions that only
  make the catalog tour appear reliable.
- Keep failed or missing observations unavailable. A scientific exclusion is
  not a transport error to bypass.
- Keep a compact visible comparison status and accessible notification details
  when presentation warnings move away from the image.
- Report matched fields as visual comparisons, not confirmed target detections,
  calibrated variability or measured motion.
