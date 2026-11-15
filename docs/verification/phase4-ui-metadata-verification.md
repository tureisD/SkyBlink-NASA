# Phase 4 frontend metadata verification

Date: 2026-11-14. Scope: the narrow frontend interpretation changes approved in
[the API 1.4.0 decision](../decisions/phase4-contract-decision.md), not the Phase 5 redesign.
Frontend review confirms compatibility with the optional additions. Existing
API 1.3.0 payloads remain readable; missing metadata does not become a passing
quality or validation state. Production target seeds were not changed.

## Archive-first continuation (API 1.5.0)

The later [source-policy decision](../decisions/phase4-online-contract-decision.md) supersedes
the unchanged-seed statement above for archive mode only. The frontend now keeps
two explicit seed sets: all five corrected archive positions match
`backend/core/staged_astrometry.json`; historical saved positions still match
the unchanged revision-3 manifests. Numeric coordinate searches preserve their
position and use the archive; named buttons explicitly choose a catalog target.

`source=archive|saved` is carried in API requests, URL state and request identity.
Archive is the default. A source selector remains available during loading and
errors; saved data never substitutes automatically. Named and arbitrary archive
requests both have a 130-second client budget. Badges and provenance distinguish
the requested/recorded source, while absent legacy metadata remains unknown.
Single-epoch states apply to catalog and arbitrary positions, show the recorded
comparison limitation and expose no difference products.

The approved partial-discovery extension adds optional `discovery_status` and
`missing_collections` to sky and spectrum provenance. Partial responses visibly
state that retrieved observations are shown but coverage/latest-epoch inventory
is incomplete, including the missing collections when recorded. Absent metadata
remains unknown; an empty missing-collection list does not establish completeness.
CSV and Markdown reports retain these fields. Metadata-only tests verify the
notice and reject malformed statuses/collection lists without changing any
real channel data. The expanded tests and production build pass; this notice
still needs an actual partial-response browser check after backend integration.

The expanded semantics test passes for corrected/saved coordinate separation,
both endpoint source parameters, URL source round trips/defaults/invalid values,
and RA `359.9999999` without rounding to an invalid 360-degree request. The
production build and real-data protocol tests passed.

Actual API 1.5 browser checks used current Vite source at `127.0.0.1:5175` and
backend `127.0.0.1:8015`, installed Chrome, desktop 1440×1000 and mobile 390×844.
Saved WISE data displayed `SAVED`, `legacy_unvalidated`, the original
RA `133.75921`, and `source=saved` in the URL. The mobile page had no horizontal
overflow and its source control/badge were visually inspected.

Submitting exact NGP coordinates `(192.85948, 27.12825)` through the search form
switched to archive, omitted `target_id`, and requested size 0.05. This real
request returned HTTP 503 after 5.736 seconds: both TAP and SIA discovery reported
upstream HTTP 502 proxy errors. The UI retained archive mode, displayed the
recorded error, and offered retry/search recovery with no saved substitution or
JavaScript error. This is an observed failure, not successful online field
acceptance; no new analysis record or `from_cache=false` input receipt was
available to inspect. Full diagnostic text is technical and remains a Phase 5
presentation issue. Evidence is retained in
`backend/.cache/phase4/online-smoke/results.json` and three PNG captures.
One named WISE request also used the corrected full-precision archive coordinates
and size 0.05, then returned HTTP 503 after 34.268 seconds with the same upstream
discovery failure. The subsequent explicit saved switch rendered saved data;
its scripted URL assertion ran before the existing URL-write debounce and failed.
That QA script now waits for the URL update, but this second check is not yet
claimed as a complete pass. Its original evidence is `named-results.json`.

After the coordinated discovery-reliability update, one independent NGP browser
attempt succeeded: HTTP 200 in **108.524 seconds**, archive source, QR3, one
actual `2026_E1` epoch with observation bounds 2026-06-01 to 2026-06-24.
`comparison_status=unmatched_single_epoch`, reason
`NO_MATCHED_PAIR_IN_BOUNDED_SAMPLE`, and empty differences were preserved. The
rendered ARCHIVE badge and single-epoch limitation were visually inspected;
there were no JavaScript errors. Discovery was complete for the four requested
collections (268 DR1 rows, 131 QR3 rows, zero in each deep collection), so no
partial-search notice was expected or observed in this successful case.

The fingerprint-named record was fetched through the API:
`sha256:3021e92e536d4b58df22b320911440424c7671b8de5c61882742a3c610964a34`.
Its 54 real input acquisition receipts all record `fresh_archive_response` and
`from_cache=false`; discovery receipts retain the initial HTTP 502 retries and
the successful responses. All ten separately fetched live assets (nine WebP
images and one telemetry sidecar) matched the record's SHA-256 values and were
served with `Cache-Control: no-store`; every image decoded as 240×240. This is
fresh acquisition and rendering evidence, not a validated temporal comparison.
The exact response, record, asset checks and captures are retained separately in
`backend/.cache/phase4/online-smoke-2/`; earlier failures were not overwritten.
The API 1.4 screenshots below remain historical evidence of their stated version.

### Current API 1.5 eligibility tightening

The later approved measurement gate preserves the native center-pixel flux
calculation and API field types. New archive channels require a wholly contained
aperture with all chosen aperture pixels clean, supported field background,
at least 10 clean local-annulus pixels, and a center without hard-bad flags.
Finite partial-aperture or insufficient-annulus sums remain visible for
exploration but arrive with `is_used_in_photometry=false`. The frontend uses
that recorded flag in eligible summaries; it does not turn those finite values
into zero or reclassify historical saved measurements using unavailable annulus
metadata. Spectrum/help/report copy distinguishes the new policy from saved
flags and states that eligibility does not certify isolation or variability.

The existing API 1.4 replay reports remain evidence for their frozen source only.
The new [API 1.5 independent replay report](../evidence/phase4/phase4-online-independent-replay.json)
uses source digest
`d070c73e2172adbf999010c9e12e39c029c288e1e1f8eb2d0a89ec0f31f2a182` and the new
online WISE image/spectrum records. All 122 bundle files (309,225,204 bytes)
and 66 installed package pins were checked independently. Strict replay from
the verified bundle passed for 54 image inputs and 17 spectrum inputs, with
matching science arrays and all 15 encoded image assets. The spectrum preserved
17 finite channels, 16 eligible channels, and one `PARTIAL_CLEAN_APERTURE`
exclusion. No drift override or scientific source edit was used.

Public reacquisition was attempted first into new empty stores, separately from
the bundled inputs. Spectrum acquisition failed twice at its first input;
image acquisition retained two verified inputs before failing. Exact-URL
diagnostic retries acquired one spectrum and one additional image input with
matching size/hash, for four independently reacquired inputs in total. One
recorded spectrum retry returned HTTP 503 before a later HTTP 200. Complete
fresh-input reacquisition and fresh-only replay did **not** pass. The successful
strict replays used retained bundle bytes and must not be presented as full
fresh reacquisition. The report preserves commands, timings, failures and
transport settings. It is a separate reviewer agent on the same host using the
isolated environment, not a human/different-platform replication. This evidence
does not cover later source revisions or the subsequent immutable-asset
publication repair.

The additional API 1.5 R Draconis null record
`sha256:0e8558538049aa3a1fe8478522e92db1b0e349827821362a2d8485268e4e5701`
also passed independent strict replay from its own frozen-source bundle. All
68 bundle files (76,983,263 bytes) and 66 package pins were verified. All 18
present channels retained null flux/error and false eligibility, with no
numerical or reason-code differences. No new public acquisition was requested
for this null case. It uses the same `d070…` source revision as the WISE records,
not the later asset-publication repair.

### Final immutable-asset publication check

The final image revision was independently replayed separately from those
earlier freezes. Source digest
`16113fcdab8afb50c915a10828d8bdd19f33d0d6ec6db81339f7ded9eb40aa9a`, analysis
`sha256:be1aec7271e5730165ba8be854b97174b68938895597257b6a3869d3e6072e3e`:
all 102 bundle files (208,322,026 bytes), 66 package pins and 52 retained inputs
verified; strict numerical replay and all ten encoded-asset hashes matched.
This adds current publication evidence without relabeling the earlier records.

Installed Chrome also fetched all ten actual content-hash-named URLs from API
8015. Each filename's hash matched the downloaded bytes and the recorded output
hash; the `ALL` image rendered as 240×240 with no JavaScript errors. The immutable
analysis URL returned the expected ID. This was a direct published-asset check,
not a new full application/archive search, and used no response interception.
Evidence is `backend/.cache/phase4/online-independent-review/publication-browser.json`
and its PNG capture. The earlier full-app NGP and saved-mode checks remain
separate. No fresh-input acquisition was requested for this final replay.

## Implemented behavior

| Recorded fact | Frontend behavior | Missing/legacy behavior |
|---|---|---|
| `epochs[].observation_range` | Dates come from contributing-observation bounds, including in spectrum legends, timeline labels and exports | A sky `date_iso` is explicitly a mean date with unavailable bounds; spectrum dates are unavailable. Bucket labels/IDs are not parsed as dates |
| Telemetry `quantity`, `normalization_applied`, `flux_band` | Cursor names display intensity and its actual plane; identifies a mismatch with the displayed image band and the recorded normalization | Quantity and normalization metadata are explicitly unavailable; no raw/calibrated source-flux claim |
| Query coordinate context | Catalog coordinates retain their stored 2025.8 query-epoch label; arbitrary ICRS coordinates say coordinate epoch unspecified | No epoch is assigned to an arbitrary coordinate |
| Provenance analysis ID/record URL/processing version | Existing provenance areas and Markdown report expose the values; record links use the API asset resolver | Unavailable legacy metadata is stated, without implying reprocessing or independent validation |
| Spectrum availability and channel reason codes | Finite/total/eligible counts are shown separately; recorded reasons are displayed literally, not inferred from prose | Existing flags/eligibility remain available; absent reasons are not invented |
| Channel input ID and extraction position | CSV includes optional input ID, extraction coordinates and measurement reasons, plus analysis ID/version and observation bounds | Missing values remain blank |
| Eligible-flux summaries | Triage summary requires finite flux, `is_used_in_photometry`, no hard-bad centre and the existing clean-fraction threshold; preserves measured flux sign | No eligible channels produces a null median, never zero or a median of excluded channels |

The status-bar subtraction labels now follow their provenance booleans rather
than always asserting successful subtraction. The spectrum table explains that
null flux can reflect unsupported background as well as missing clean pixels.
The original epoch IDs and scientific arrays remain unchanged. Native spectrum
inputs are explicitly separate from the displayed image pair in the report.

Telemetry text wrapping was adjusted only to keep the new meaning/plane labels
readable within the existing HUD; the responsive layout was not redesigned.
Asset links reject unsupported URL protocols as well as the retired synthetic
paths. This is necessary for the new clickable analysis-record link.

## Verification performed

From `frontend/`:

```powershell
npm run test:semantics
npm run test:real-data
npm run build
```

All passed. The build includes TypeScript checking and the real-data public/dist
packaging guards. `git diff --check -- frontend` also passed.

`qa/phase4/semantics.test.mjs` reads real saved observations and exercises
isolated metadata-only variations. It verifies finite-but-excluded summaries,
the real all-null R Draconis spectrum, signed eligible flux from Epsilon Indi,
the commissioning bucket's actual 2025 mean date, absent spectrum date metadata,
arbitrary-coordinate epoch labeling, and known/unknown/mismatched telemetry
semantics. Metadata test scenarios remain in QA and never enter product assets.
The protocol tests continue to accept all five real payloads and reject
simulated/unknown origin, retired asset paths and unsafe URL schemes.

An API 1.4.0 browser smoke test passed on 2026-11-14 using installed Chrome,
current Vite source at `http://127.0.0.1:5174`, and the backend at
`http://127.0.0.1:8014`. Desktop (1440×1000) and mobile (390×844) checks used real
saved R Draconis and WISE 0855 observations, without response interception or
synthetic routes. The checks confirmed:

- Repeated R Draconis requests preserved `generated_at=2026-11-13T20:00:31Z`.
- The real R Draconis spectrum showed 0 finite / 240 recorded samples and 0
  eligible samples, unavailable observation dates and legacy analysis metadata.
- The timeline showed the actual 2025 mean date rather than a commissioning
  bucket year. Mobile telemetry identified its thermal plane while the image
  displayed all bands, and stated unavailable normalization metadata.
- No JavaScript errors or horizontal document overflow occurred in these cases.

The mobile screenshot was visually inspected: the new metadata text is visible
within the HUD. This is a narrow smoke check, not comprehensive responsive or
accessibility acceptance. Ignored local evidence is retained in
`backend/.cache/phase4/frontend-smoke/` (`results.json`, `run.cjs`, and three
PNG captures). New staged analysis-record links were exercised by metadata
tests, not by serving/promoting a staged product in this browser check.

Separately, [independent replay results](../evidence/phase4/phase4-independent-replay-results.json)
record strict image, finite-spectrum and null-spectrum replay by a separate reviewer agent on
the same Windows host in a new isolated Python 3.11.9 virtual environment.
All 52 bundle files passed independent size/hash checks, all 66 pinned package
versions matched, and `pip check` passed. Those two replays matched code, environment,
inputs and numerical results; all ten encoded image assets also matched hashes.
The separate real R Draconis null bundle also passed: all 83 files (142,693,784
payload bytes) passed independent hash/size checks, and the same isolated
environment matched all 66 pins. Strict replay preserved all 34 present channels
with null flux/error and false eligibility. Independently inspected outputs
matched 34 `NO_CLEAN_APERTURE_PIXELS`, 34 `HARD_BAD_EXTRACTION_CENTRE`, and 30
`UNSUPPORTED_BACKGROUND` reasons; all per-exposure differences were empty.
The corrected-coordinate null example is separate from the 240-channel legacy
product used for the browser smoke test. No drift override was used in any run.
This is not an independent human or different-platform replication, and
numerical reproducibility does not establish scientific validity.

## Remaining Phase 5 work

This change does not implement the full evidence-state model, guided entry,
mobile navigation, modal focus repair, keyboard point inspection, signed plot
domain, explicit all-null chart replacement, or complete share-state restoration.
The all-null spectrum now exposes zero finite/eligible counts, but the existing
empty chart remains until that redesign. Recorded reason codes are available
as technical metadata; reviewed plain-language explanations remain a Phase 5
task. Historical data remains legacy data even when served through API 1.4.0.

The reviewed Phase 4 record and scientific acceptance gates must determine
whether a comparison is valid. The frontend does not derive a quality pass from
an analysis ID, a cache hit, the real-data marker, or a human-readable warning.
