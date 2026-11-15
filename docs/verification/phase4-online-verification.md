# Phase 4 continuation: online sources and scientific scope

This checkpoint supersedes the API 1.4 cache-first checkpoint in
[the earlier report](phase4-verification.md). API **1.5.0** defaults to upstream
archive acquisition for named targets and arbitrary coordinates. The five
historical revision-3 datasets remain unchanged, available only through explicit
`source=saved`. No failed archive request substitutes saved or generated data.

## What is now implemented

- `/targets`, `/sky` and `/spectrum` share `source=archive|saved`; archive uses
  corrected reference astrometry, while saved coordinates remain paired with
  their original assets. Numeric coordinate searches preserve the user's
  position rather than snapping to a nearby demonstration target.
- All four DR1/QR3 wide/deep collections are queried through bounded parallel
  SIA, with bounded TAP fallback. Valid partial discovery is explicitly labeled
  with unavailable collections. Partial empty discovery is an upstream error,
  not proof of absent coverage. Strict science/rebuild discovery remains strict.
- Archive requests bypass application product and raw-cutout cache reads and
  request upstream cache revalidation. Retained bytes support replay; they are
  never the automatic input substitute for a new archive request. Proxy/server
  cache implementation is outside the application's control.
- Acquisition receipts record requested URLs, actual retrieval times, hashes,
  sizes, cache status and failures. A download-stage deadline reserves time for
  processing. A completed real subset may be used; missing inputs remain in the
  record. Late download workers cannot alter an already published receipt set.
- Image pair selection retains its spectral/quality gates. It checks candidates
  in the same increasing spectral-distance order and stops after the best valid
  candidate, avoiding work on worse pairs. A bounded search that cannot find a
  usable pair may display one actual epoch with a specific limitation and no
  differences. This is an image-access result, not a temporal detection.
- Spectral eligibility now requires the whole chosen aperture to be inside the
  native image and clean, at least ten clean local-annulus pixels, supported
  field background and a non-hard-bad center. Finite unsupported partial sums
  remain inspectable but ineligible. Missing flux is never area-corrected or
  invented. Native method version 2 / cache schema 6 records this change.
- Source, discovery limitations, comparison availability and measurement
  exclusions appear in UI/report metadata. This is targeted correctness work;
  the larger Phase 5 navigation/visual overhaul remains separate.
- Published image/difference/telemetry URLs contain their content SHA256. A
  later refresh cannot overwrite the pixels referenced by an earlier response.
  Image method/cache version 11 records this final publication correction.

The [coordinated contract decision](../decisions/phase4-online-contract-decision.md) documents
the approved semantics. Live sky and spectrum budgets remain 120 seconds;
the client allows 130 seconds. Upstream outages can still cause honest errors.

## NASA resources and what the app actually uses

The [fresh official-source recheck](phase4-source-recheck.md) confirms DR1 + QR3
as the active spectral-image releases, and Gaia DR3 as the current full Gaia
release. The app actively queries DR1/QR3; the scientific study additionally
retrieved Gaia, AllWISE, release-matched CWAVE/CBAND calibration and SAPM inputs.
This does not mean every resource listed by NASA/CSA is integrated. The
102-channel all-sky cube, NEOSSat and CADC are not runtime inputs. Historical
WISE/DSS/Gaia overlays are not silently transplanted into a newly queried field.

## Scientific result and decision

The [fixed independent study](phase4-science-online-verification.md) completed
all eight field/detector searches. Six had qualified measurements, comprising
32 repeat comparisons of 27 distinct Gaia sources in four high-latitude regions,
two detectors and DR1/QR3. Two searches lacked enough qualified controls/pairs;
they do not count as passes. All twelve measured exposures pass the fixed robust
astrometric gate, with 1,445 matched-star observations and robust RMS including
bias of 0.235–0.417 arcseconds. Individual outliers remain in the evidence.

**The proposed exact-overlap/SAPM method failed its primary gate:** one group's
robust scatter is 2.14869 against the fixed maximum of 2. No source replacement,
residual clipping, fitted scaling or error inflation was used to hide this.
The independently specified secondary baseline—existing center-pixel aperture
and constant local-WCS pixel area—passes all six evaluable groups. Its largest
group scatter is 1.91056 and largest individual absolute residual is 3.87985σ.
The existing integration remains in production; the failed refinement is not
adopted. Primary and secondary results remain separate in the frozen report.

The earlier crowded-field worst residual has a catalog neighbor 13.80 arcseconds
away and zero clean annulus pixels in both visits. An isolated EPSF predicts
only a 0.48% aperture-response change against the observed 23.29% change, with
poor model fits. Pixel phase alone does not explain it. The new support rule
marks this measurement and four other original controls ineligible. Five
original controls remain eligible; this posthoc screen is not a replacement
passing scientific test or proof that the field is unblended.

Consequently the scientific basis is stronger and a restricted existing-method
baseline is supported. **Universal calibrated photometry is not established.**
Catalog isolation, calibrated wavelength matching and SNR cuts used by the study
are not all automatically enforced by every online spectrum query. Product
eligibility is a necessary support check, not a scientific-validation badge.
Detectors 2/4/5/6, crowded/saturated sources, absolute flux/aperture corrections,
correlated uncertainties and discovery significance remain outside this test.

## Coordinate and online evidence

The fixed [nine-position discovery matrix](../evidence/phase4/phase4-online-discovery-geometry-final-policy.json)
returned real records for all nine positions: eight complete discoveries and
one explicitly partial result. It includes both poles, both sides of RA zero,
high latitude, the Galactic center and the historical arbitrary-field example.
Metadata discovery does not establish usable pixels or compatible epochs.

Earlier full HTTP probes already returned fresh-input images for WISE 0855,
Barnard's Star and Epsilon Indi B, and spectra for the latter two. A real browser
NGP request returned a single QR3 epoch; all ten served assets matched its
record. Failures and slow requests from those runs are preserved, not replaced
by successful retries. Final fixed end-to-end results are recorded below after
the download-budget and eligibility changes.

### Fixed five-target HTTP matrix

All ten endpoint requests returned HTTP 200 with fresh upstream receipts for
every retained input, `data_access=archive`, no simulated fallback, matching
analysis links, and matching hashes for every displayed frame. The
[complete report](../evidence/phase4/phase4-online-api-targets.json) preserves request coordinates,
times, provenance and input counts. These are actual outcomes, not expected
counts for future requests.

| Target | Sky seconds | Image comparison | Spectrum seconds | Present / finite / eligible channels |
|---|---:|---|---:|---|
| WISE 0855 | 111.891 | Matched visual pair | 36.516 | 17 / 17 / 16 |
| Barnard's Star | 104.750 | One real epoch; bounded sample lacked matched pair | 27.047 | 18 / 1 / 0 |
| Epsilon Indi B | 80.907 | Matched visual pair | 23.031 | 16 / 8 / 0 |
| RW Aurigae | 95.594 | One real epoch; incomplete downloads/no verified pair | 26.484 | 18 / 16 / 0 |
| R Draconis | 97.234 | Matched visual pair | 39.203 | 18 / 0 / 0 |

Visual compatibility is not calibrated variability. In particular, a finite
spectrum can have zero eligible measurements; R Draconis correctly retains
channel/flag metadata with null fluxes. Original timeout/503 probes are retained
under `backend/.cache/phase4/online-api-{first,integrated}.json`; they are not
counted as successes in this matrix.

After the ten target requests, the probe/server stopped before the final
publication fix to avoid recording files different from running code. An
in-flight coordinate attempt was interrupted, not counted. The same three
fixed coordinates resume in a separate report on image method 11. The target
matrix tests the same acquisition/selection/measurement implementation before
content-addressed output naming; it is not misrepresented as a test of that
later publication change.

### Fixed coordinate continuation on final publication code

The [coordinate report](../evidence/phase4/phase4-online-api-coordinates.json) records NGP at
`(192.85948,27.12825)`, the exact north celestial pole `(0,90)`, and the RA-wrap
position `(359.9999999,-20)`, all with a 0.05-degree field. NGP and the pole
returned HTTP 200 in **90.907** and **80.422** seconds, respectively. Both contain
one real epoch with an explicit incomplete-download/no-comparison limitation;
all retained inputs have fresh receipts and served frame hashes match.

The RA-wrap request returned an honest **503 in 61.421 seconds**: discovery
could not complete its upstream SIA/TAP attempts. It did not return fabricated
coverage, a saved target or a comparison. The original remains in the report;
[one identical retry](../evidence/phase4/phase4-online-api-wrap-retry.json) is separate evidence.
The first full access matrix therefore passes **12/13**, not 13/13. Geometry
support is established separately from successful archive availability.

The identical RA-wrap retry returned **HTTP 200 in 80.609 seconds**, with fresh
input receipts and matching served-frame hashes. Thus every fixed case had a
successful real-data response, but one required a retry: 13 successes in 14
attempts, not a failure-free availability claim. The initial 503 remains visible.

## Reproducibility and remaining Phase 4 gates

The record/replay mechanism verifies exact input, method, source and environment
identity. An upstream query today and a replay of yesterday's retained analysis
are deliberately different operations: newly published observations can change
discovery; pinned replay must not. Local storage remains useful for reproducible
evidence even though application requests now fetch upstream by default.

The earlier clean-environment image/finite/null replay proves its recorded
API 1.4 source only. Current-source replay results must identify their own
records; they cannot inherit that verification. See [the workflow](../guides/reproducibility.md).

The [new independent report](../evidence/phase4/phase4-online-independent-replay.json) verifies
API 1.5 WISE image and spectrum plus the R Draconis null spectrum in a separate
pinned environment. Input hashes, source/environment identities and numerical
results match; all 15 WISE encoded assets match. The null replay preserves all
18 null channels and exclusion reasons. Full public reacquisition encountered
HTTP 503 responses and did not complete; four distinct independently downloaded
inputs matched exactly. Retained-bundle replay and partial network reacquisition
are explicitly different outcomes. No drift/hash overrides were used.

Records are checked in under [phase4-online-records](../evidence/phase4/records),
including exact public URLs and hashes. Large input/source bundles remain local
and unpublished; a public durable bundle still belongs to release preparation.
Earlier 1.5 records use their frozen source bundle. The final NGP image record
uses content-addressed publication and its own source identity.

That final NGP source was independently replayed: **52 input hashes**,
scientific planes/normalization and **all ten encoded asset hashes** match in
the pinned environment. Chrome then retrieved all ten actual content-named
URLs with HTTP 200, checked filename hash = response bytes = record hash, and
rendered the 240-by-240 image without JavaScript errors. This final publication
check uses retained bundle inputs; it does not claim complete network
reacquisition. The source digest and commands are in the independent report.

Final backend regression: **275 passed, no skips**, one Starlette/httpx
deprecation warning. Focused publication tests use two different existing real
frames to verify that a refresh preserves the first result's bytes, and check
telemetry/difference naming. Frontend checks/build and the distribution scanner
pass; all **288** approved legacy observation files retain their original hashes.

The user-authorized online-first policy supersedes replacing the historical
cache as the default product path. Those files remain a labeled rollback/example
set. It does not waive scientific promotion: the failed proposed method, missing
test coverage and historical products are not certified by successful HTTP or
replay checks. Public release artifacts, human comprehension sessions, the
Phase 5 UI overhaul and Phase 6 deployed-container checks remain separate work.

### Phase 4 handoff

| Work package | Current disposition |
|---|---|
| R0: coordinates and science decision | Corrected archive profiles active; existing-method restricted baseline supported; failed proposed refinement rejected and preserved |
| R1: lineage and dates | Implemented, including fresh acquisition receipts and immutable output links |
| R2: repeatable execution | Independent pinned image/finite/null replay passes; complete public reacquisition remains availability-limited; durable public bundles not yet published |
| R3: rollout | User-authorized online-first route passes all five named-target endpoints; legacy saved cache preserved and explicitly labeled, not scientifically re-promoted |
| R4: explanations and handoff | Source/comparison/eligibility meanings, null case and evidence workflow documented; novice/expert comprehension sessions remain Phase 5 |

The implemented online-first Phase 4 path is ready for the UI work within these
limits. Reproducible arithmetic and readable metadata are established technical
capabilities; universal science, public reproducibility availability and human
understanding are not automatically solved by them.
