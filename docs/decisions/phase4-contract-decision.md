# Phase 4 contract and migration decision

2026-11-14. The user authorized execution of Phase 4. The Orchestrator approves
API **1.4.0** as an additive provenance/interpretation update and correction of
creation-time semantics. This local proposal accompanies the eventual integration
PR; no PR has been published. Frontend/backend compatibility is verified during
implementation and recorded in the Phase 4 verification report.

## Approved meaning

- `provenance.generated_at` is the stored product creation time, never the
  current request time. Missing creation metadata is an invalid product; do not
  invent a timestamp. Existing saved products retain their recorded creation time.
- Optional `provenance.analysis_id`, `analysis_record_url`, `processing_version`
  identify the replay record and method. Absence means lineage is unavailable,
  not that a historical product was reprocessed or independently validated.
- Optional `epochs[].observation_range` contains `mjd_min`, `mjd_max`,
  `date_start_iso`, `date_end_iso`, and `time_scale: "utc"` from contributing observations. These describe
  actual samples, not the semantic meaning of an epoch bucket ID. A legacy
  product without exact bounds may omit the object; no calendar-week bounds
  are substituted for precise measurements.
- Spectrum epochs may carry `measurement_availability` with `total_channels`,
  `finite_channels`, `usable_channels` and explicit `reasons`. Finite flux is
  not necessarily eligible. Null flux remains null.
- Spectrum channels may carry `input_id`, `extraction_ra`, `extraction_dec`
  and `measurement_reasons`. These refer to the native exposure extraction,
  which may differ from the displayed sky pair/composite.
- Telemetry may carry `quantity: normalized_display_intensity` and
  `normalization_applied`. It remains the existing float16/uint32 binary
  representation. Its plane is named by `flux_band`; the values must not be
  described as raw science flux. Missing metadata remains explicitly unknown.

No existing field is removed or retyped. Numeric `clean_fraction` remains the
existing center-pixel eligibility fraction. Fractional-aperture production
adoption is NOT approved by this record: a separately frozen holdout experiment
must support an explicit method decision. The Phase 3 failed result is retained.

## Migration and staging

Corrected reference astrometry is implemented as an explicit staged profile.
The production target catalog, frontend seeds and revision-3 cache must remain
coherent until a replacement passes promotion gates. A corrected stage does
not authorize serving old coordinate assets as though they were rebuilt.
Epoch IDs stay stable; observation labels use actual dates where known.

Internal replay records preserve source hashes, selected inputs, extraction
positions, methods, code/environment identity and limitations. Creation and
retrieval times are separate from the stable scientific fingerprint. Records
never contain arbitrary environment dumps, credentials or local absolute paths.
Replay output goes to a separate location; missing or changed inputs fail
explicitly. Exact artifact hashes, numerical reproducibility and independent
scientific validity remain separate checks.
