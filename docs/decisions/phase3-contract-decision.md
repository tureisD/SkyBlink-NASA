# Phase 3 measurement contract decision: API 1.3.0

Date: 2026-11-14. User authorization: execute audit Phase 3. Orchestrator
decision: approve the stricter measurement eligibility and version bump.
This written proposal is ready to accompany the integration PR; no PR has
been opened or merged for the accumulated local audit changes.

The original O1 rule could mark a flag-clean aperture usable even when no
supported sky background existed. API 1.3.0 requires all three conditions:

1. `clean_fraction >= 0.5` (the existing native-pixel-count definition).
2. The extraction centre is not hard-bad.
3. The local background estimate has sufficient clean spatial support.

When background support is absent, `flux_ujy` and `flux_err_ujy` are null and
`is_used_in_photometry` is false, even if `clean_fraction` remains positive.
The fraction still describes pixel eligibility; it is not rewritten to hide
the missing-background reason. `is_flagged_bad` remains exclusively hard-mask
based. No field is renamed, removed or retyped, and no new synthetic data or
confidence score is introduced.

`flux_err_ujy` includes an approximate median-background term, with the shared
offset contribution scaling as the square of the number of retained aperture
pixels. Detector correlations and plane-fit covariance remain uncalibrated.
`provenance.background_subtracted` reflects the contributing estimates.
`wavelength_calibration` identifies WCS-WAVE as an approximate visualization
lookup; a universal one-nanometre accuracy guarantee is not made.

The production aperture remains the O1 centre-pixel definition. Fractional
aperture integration is an exploratory diagnostic, not silently substituted
after observing the failed control-star test. It needs an explicit method
decision and an independent validation set before scientific acceptance.

New sky builds use conservative native measurement masks before interpolation,
separate display arrays, exact retained-grid wavelength/bandwidth checks, one
exposure per band per epoch, and a 30-day maximum composite span. Dates and
internal input metadata state what was actually used. Historical revision-3
products remain readable, unchanged, and explicitly labelled unvalidated.
Their coordinates and spectra must be rebuilt together in Phase 4.

Backend implementation and regression coverage implement this decision.
Frontend compatibility review is recorded with the Phase 3 verification:
null flux and false eligibility already have supported UI paths. No frontend
field migration is required. OpenAPI and health report 1.3.0.
