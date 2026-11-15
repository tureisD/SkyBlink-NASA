# Explicit known-exposure retrieval — API 1.6.0

Policy v1.12, 2026-11-15. Approved by the root Orchestrator for the user's
request to repair catalog retrieval during the reproduced IRSA discovery outage.

The default remains a live archive search. TAP and SIA can fail while the
cutout service still serves real observations. A previously verified list of
exposure addresses can therefore support a separate, explicitly selected
recovery path. It cannot establish current archive completeness.

## Additive contract

Both `/api/v1/sky` and `/api/v1/spectrum` accept `discovery=live|known`, default
`live`. `known` requires `source=archive` and a catalog `target_id`; all current
corrected-coordinate checks still apply. Invalid combinations return 422.
Existing fields retain their types. Both provenance objects add optional
`discovery_mode: "live" | "known" | null`. Historical products may omit it.
The frontend requires explicit `known` provenance for a known request.

Known mode uses `data/catalog-exposure-index.json`: bounded real metadata
derived from the five earlier verified analysis records. Each entry retains
source-record identity, dates, query coordinates, release, detector, observation
bounds and exposure addresses. The index contains no images or generated
observations. It is included in runtime source identity and packaging.

Every known-mode build downloads its FITS inputs again from the archive and
applies the existing background, masking, wavelength, pixel-support and
measurement rules. Application input/product cache reads remain bypassed.
Failed acquisition stays an explicit failure or partial result; it never
silently loads saved images. The mode participates in work/cache identities
and lineage, preventing a live search and a bounded known request from sharing
the same build identity.

Known provenance reports `discovery_status=partial` and records
`recorded_exposure_index`, the index identity and its original verification
time. This means bounded historical selection, even when every listed image
downloads successfully. It must not be described as a complete current search.
Spectra use that same bounded set and may be sparse; they do not represent all
available channels in the current archive.
Epoch identifiers are relative to the selected inventory and can differ from
those in a live search. Compare recorded UTC observation bounds and source
identities, not an epoch label alone, across acquisition modes.

## Interface and acceptance

The user may select “Fetch known exposures online” after an archive failure or
choose the corresponding catalog-only source option. There is no automatic
switch. Source labels, URLs, recent settings, image requests and spectrum
requests retain the mode. Arbitrary coordinate searches return to live
discovery. Switching back to a fresh search remains available.

Acceptance requires fresh requests for all five catalog targets, independently
checked input receipts and image assets, strict replay of a representative
product, invalid-mode checks, and browser verification of the explicit recovery
action and source labels. Results, including failures, belong in
[the outage verification report](../verification/phase5-discovery-outage-verification.md).
This authorization alone is not a claim that those checks passed.

## Scope

This improves resilience for the five recorded fields while the image service
is reachable. It does not repair IRSA, provide an independent all-sky discovery
index, discover newer observations, or certify target motion or variability.
Saved revision-3 products and scientific acceptance thresholds remain unchanged.
