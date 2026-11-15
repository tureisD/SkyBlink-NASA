# Reading a SkyBlink result

> **Current evidence (2026-11-15):**
> [method-12 live comparisons](../verification/phase5-live-comparison-verification.md) and
> [the independent control study](../verification/phase4-science-online-verification.md) are
> the latest evidence. A compatible field pair does not establish that the
> named target is detected, unsaturated, unblended or measurable. Catalog
> motion remains expected context, not a fitted displacement. The earlier
> failed studies remain relevant history, not a substitute for this scoped
> current assessment.

> **Current continuation:** API 1.5 adds explicit archive/saved source selection and partial-discovery/single-epoch states. Archive measurement eligibility now requires a full clean contained aperture and at least ten clean local-annulus pixels, plus supported background and a non-hard-bad center. Finite excluded values remain exploratory; saved products retain their recorded rules. [Details](../verification/phase4-online-verification.md).

This is the Phase 4 meaning contract for the UI, exports and documentation.
The implementation is an exploratory comparison tool. Real origin, repeatable
arithmetic and a scientifically validated interpretation are separate properties.
See [science acceptance](../verification/phase4-science-verification.md) and the
[replay format](../reference/phase4-replay-schema.md). Phase 5 still needs to test whether
new users can understand these distinctions in the interface.

## Four questions before interpreting a result

1. **What was observed?** Check the actual observation range, release, detector,
   wavelength and input identifier. An epoch groups samples; its bands are not
   necessarily simultaneous. A historical epoch label is not evidence of a date.
2. **What can be compared?** A detector number alone does not identify the same
   wavelength: SPHEREx wavelength changes across its focal plane. New images
   require matched wavelengths and bandwidths across the retained field. This
   permits a limited visual comparison; it does not establish calibrated variability.
3. **What was measured?** Native aperture flux uses unnormalized measurement
   pixels. Display frames and cursor telemetry have different meanings. Inspect
   eligibility, excluded pixels, background support and approximate uncertainty.
4. **What conclusion is justified?** A residual is a candidate for investigation.
   Blending, changing sampling, artifacts, noise and real variability remain
   alternatives. A catalog proper-motion vector is context, not a motion measured
   by this application. A molecular wavelength guide is not a molecular detection.

## Data and measurement vocabulary

| Term | Exact meaning and permitted conclusion |
|---|---|
| Real origin | Input bytes came from identified observations. This alone says nothing about usable flux or discovery validity. |
| Coverage | Observations were found within the recorded search. A failed upstream query is not evidence of no coverage. |
| Complete search | Only complete within the explicit query, pagination, release and time bounds. The Phase 4 staged historical-URI inventory is not a complete archive search. |
| Observation range | Earliest exposure start to latest end among selected samples, MJD UTC for the inspected Level 2 inputs. Bounds do not imply continuous coverage. |
| Query position | ICRS degrees used for archive retrieval. Catalog targets have a declared propagated query epoch; arbitrary user coordinates do not acquire an epoch label automatically. |
| Extraction position | Native exposure location at which a channel was extracted. Catalog propagation uses the exposure time and the recorded reference time scale. |
| Comparable visual pair | Selected samples pass the implemented wavelength/bandwidth and temporal-span gates. Residual calibration and astrophysical interpretation are not validated by that gate. |
| Measurement eligible | The implementation permits use of the channel. This is a screening decision, not proof of accurate total source flux. |
| Finite but ineligible | A numerical aperture sum exists but a quality rule rejects its use. Do not count it as a usable detection. |
| Null flux | No supported measurement is supplied. It is not zero, an upper limit, a nondetection probability or absence of a source. |
| Omitted channel | No channel could be constructed, for example because wavelength or image coverage was unavailable. This differs from a present channel with null flux. |
| Approximate uncertainty | Native variance plus an approximate shared-background contribution; detector correlations, model covariance and systematic errors are not fully calibrated. |
| Normalized display intensity | A visualization quantity after per-band scaling and band combination. Telemetry identifies its actual `flux_band`; it must not be read as raw aperture flux in the currently selected detector. |
| Unknown | Required metadata was not recorded. Do not infer it from a legacy filename, cache hit or attractive image. |
| Failed / insufficient / not evaluated | Respectively: a performed test missed its fixed threshold; a test lacked required evidence; a test was not performed. None means pass. |
| Strict replay | Verified input bytes and processing source/environment reproduce the recorded numerical outputs. It does not validate the scientific model. |

## Reason codes

These codes describe implementation decisions, not probabilities. Channel reasons
are additive: more than one may apply. Legacy products do not gain retrospective
reasons that were never recorded.

For current archive products, any incomplete clean aperture is ineligible,
including a channel labeled `PARTIAL_CLEAN_APERTURE`. The half-aperture split
below describes the reason label, not the current acceptance threshold.
`FIELD_BACKGROUND_FALLBACK` can retain an exploratory finite sum, but fewer than
ten clean annulus pixels is ineligible under the current policy. Saved products
retain their own recorded eligibility and are not retrospectively recertified.

| Code | Explanation |
|---|---|
| `UNSUPPORTED_BACKGROUND` | Too little clean, spatially distributed sky support; flux and error remain null. |
| `NO_CLEAN_APERTURE_PIXELS` | No valid, positive-variance aperture pixels survive measurement exclusions. |
| `INSUFFICIENT_CLEAN_APERTURE` | Less than half of the center-selected aperture pixels are clean; ineligible even if a partial sum is finite. |
| `PARTIAL_CLEAN_APERTURE` | At least half, but not all, aperture pixels are clean. No missing-flux/aperture correction is implied. |
| `HARD_BAD_EXTRACTION_CENTRE` | The native extraction-center flag has a hard-bad bit; the channel is ineligible. |
| `FIELD_BACKGROUND_FALLBACK` | Fewer than ten clean local-annulus pixels; extraction relies on the supported field background already subtracted. |
| `NO_FINITE_FLUX` | Every present channel in this epoch has unavailable flux. This aggregate is not an explanation of the individual failure. |
| `MISSING_SPECTRAL_COORDINATES` / `INVALID_WAVELENGTH` / `INVALID_BANDWIDTH` | Internal omission reasons: the wavelength lookup cannot supply a valid positive finite sample. |
| `EXTRACTION_CENTRE_OUTSIDE_NATIVE_IMAGE` / `NO_NATIVE_APERTURE_PIXELS` | Internal omission reasons: no supported extraction geometry. |
| `SELECTED_COMPARABLE_INPUT` | A downloaded input actually contributes to a retained image band. |
| `NOT_SELECTED_BY_BOUNDED_MATCHER` | Considered input not used by the bounded image selector. This does not assert it could never match another observation. |
| `NO_USABLE_OUTPUT_BAND` | Image selection was attempted but the input's band did not survive into the output. |

## The arithmetic that needs explaining

The image extension is in MJy/sr. The pipeline subtracts the supplied `ZODI`
model and estimates residual sky using clean pixels excluding known-source,
hard-bad and warning flags. A supported masked median is the default; a 2D
plane is adopted only when the fixed held-out improvement and support gates
pass. Unsupported backgrounds do not produce usable measurements.

For the retained native aperture method, a pixel contributes when its center
is within 12.3 arcseconds and it passes the measurement mask and variance checks.
Let `C` be those clean pixels, `I_i` their background-subtracted MJy/sr values,
`b` the residual annulus median, and `Omega = (pixel_scale_arcsec / 206264.806)^2`
the approximate native pixel solid angle in steradians. Then:

```text
flux_uJy = 10^12 * Omega * sum_{i in C}(I_i - b)
sigma_uJy = 10^12 * Omega * sqrt(sum_{i in C}(V_i) + |C|^2 * Var(b))
clean_fraction = |C| / number_of_center_selected_aperture_pixels
```

The annulus spans 3–5 native pixels. With at least ten usable annulus pixels,
the background variance is the larger of the native-variance median estimate
and the robust-scatter median estimate. Otherwise the supported field-background
estimate supplies an approximate error. No division by `clean_fraction`, PSF
aperture correction, fractional-area integration or absolute-flux calibration
repair is silently applied. The fractional-aperture experiment remains research;
its independent stability acceptance has not passed.

Image measurements are reprojected to a north-up TAN grid of 240 by 240 pixels
at 3.075 arcseconds per pixel; this oversampling does not improve the instrument's
native 6.15-arcsecond sampling. Display arrays can retain warning pixels that
are excluded from measurement arrays. Blink normalization is shared across
epochs per band and is derived independently of target brightness. Differences
use the measurement arrays before display normalization. Cross-band images
are combinations of available samples, not simultaneously measured spectra.

## Phase 5 capability handoff

| Information | API 1.4 source | Honest legacy/unavailable behavior |
|---|---|---|
| Actual date range | `epochs[].observation_range` in sky/spectrum | Show a recorded mean date with explicit unknown range; if no mean date was recorded, dates are unavailable. |
| Channel usability counts | Spectrum `epochs[].measurement_availability` | Counts can be derived from actual channels; missing reasons remain unknown. |
| Individual channel lineage | `input_id`, `extraction_ra`, `extraction_dec`, `measurement_reasons` | Null IDs/coordinates and empty reasons are not a reconstructed history. |
| Analysis evidence | `provenance.analysis_id`, `analysis_record_url`, `processing_version` | Legacy revision 3 has no replay record; label this plainly. |
| Telemetry meaning | `telemetry.quantity`, `flux_band`, `normalization_applied` | Unknown normalization is not raw flux; do not equate a thermal cursor plane with a selected detector. |
| Pair selection, failed downloads, background fits | Internal linked analysis record | No structured compact public validation-status object yet; do not infer acceptance from text or badge color. |
| Science validation | Scoped reports in `docs/`, not the old `confidence` label | Still blocked for promotion. Old `confidence=high` describes a cache/extraction convention, not a measured probability. |

Required demonstrations for Phase 5 are: finite eligible flux, finite rejected
flux, all-null flux, one observed epoch, compatible visual pair, incompatible
pair, incomplete discovery, upstream outage, and missing legacy provenance.
Use actual retained results or explicit metadata unit tests for these states;
never manufacture observations for a polished product demonstration.
