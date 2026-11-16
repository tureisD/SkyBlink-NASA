# Archive recovery execution — 2026-11-15

## Integrated runtime recovery (November 16 local, API 1.7.0)

Policy v1.19 approves an explicit `discovery=indexed` source in both image and
spectrum APIs. The newer landing/frontend is integrated in
`.cache/archive-frontend-integration` on branch
`integration/archive-and-frontend-20261116`; frontend port 5174 proxies the
integrated API on port 8000. No GitHub commit or push is claimed.

The shipped metadata-only index contains **5,223 records**: 1,718 QR3 detector-1
objects, 3,484 DR1 detector-3 objects across the two measured periods, and
21 fresh supplemental IMAGE headers whose addresses came from historical
catalog metadata. Supplemental addresses were not independently rediscovered.
The compressed approval hash is
`9473476cc6aff09e8dd2d8b93a68d8e6c3bf848582253a2e61f5d21746c48df5`.
`build_spatial_index.py` records the snapshot/header identities. The hash is
checked before use and enters both work identity and immutable analysis
lineage. The decoded metadata is size-bounded. Native TAN-SIP inverse containment
follows the spherical prefilter; image compatibility still uses measured data.
Directory membership does not establish wide/deep collection membership.

### Actual online image requests

All requests used corrected catalog positions, a 0.2-degree field, explicit
archive/indexed mode, and fresh downloads through the frontend proxy. The first
round allowed two different jobs concurrently. HTTP 200 alone was not counted
as comparison success.

| Target | First response | Seconds | Outcome |
|---|---:|---:|---|
| Barnard's Star | 200 | 33.968 | Two epochs; matched visual comparison |
| WISE 0855 | 200 | 50.406 | Two epochs; matched visual comparison |
| Epsilon Indi B | 404 | 14.563 | No usable image band in completed inputs |
| RW Aurigae | 200 | 57.109 | One epoch; incomplete partner downloads |
| R Draconis | 200 | 57.203 | Two epochs; matched visual comparison |

The logs separately recorded HTTP 503 `Server busy` and incomplete chunked
responses. Per-build indexed download concurrency was reduced to at most two.
Sequential follow-ups still returned Epsilon Indi B 404 in 20.860 s and
RW Aurigae one epoch in 53.531 s; lower concurrency is not a proven cure for
upstream availability. Replaying only the two retained Epsilon Indi detector-2
inputs for diagnosis showed background `insufficient_spatial_support`, zero
valid background cells, two covered quadrants and zero usable output pixels.
Those rejected inputs were not promoted or substituted into a fresh request.
Detector-5 HTTP response headers did not establish completed body downloads.

A real Chromium run clicked the landing page's indexed WISE link and displayed
two epochs (2025-05-05 and 2026-05-11), persistent observation canvas, explicit
indexed/partial labels and fresh-download provenance. The result's collection
is `indexed_dr1`, not an inferred wide/deep collection. No response interception
or synthetic observation inputs were used. The final browser run verified that
manual stepping preserves the same canvas and opened Compare and Spectrum
without JavaScript errors. Spectrum returned two epochs and four recorded
eligible samples, with signed flux and eligibility caveats preserved. Both
immutable analysis records contain the approved index hash; all transfer
receipts have `from_cache=false` (two completed image and four spectrum inputs).

A non-catalog control at (286.0012867435891, 43.70488424019806) returned HTTP 200
in 25.344 seconds with one real epoch. An outside-index query at (10, 20)
returned HTTP 503 in 0.140 seconds with explicit unknown-coverage wording,
not a claim that observations do not exist. The unmodified default live source
remains separate and unavailable; the last direct SIA probe timed out in 16.328 s.

Local raw JSON, screenshots and diagnostics are retained under the integration
worktree's `backend/.cache/indexed-live-verification/`; API transfer logs are
in the original workspace's `backend/.cache/indexed-api*.stderr.log`. These
local captures are diagnostics, not newly approved packaged observations.

### Why this differs from the previous attempts

Transport/timeout experiments never produced valid fixed-coordinate TAP/SIA
rows. Known mode could download a small catalog list, but did not perform
spatial discovery. The cloud-header prototype established a separate search
route but was not callable from the product. This change supplies that bounded
index to the existing fresh-download pipeline, adds explicit API/UI/URL source
semantics, checks downloaded time/detector metadata, and packages its approved
identity. It does not repair IRSA's service or imply complete archive coverage.

### Validation and remaining acceptance

Final backend suite: **313 passed, 19 skipped**. The initial full run exposed
two API-version assertions left at 1.6.0; those were corrected before the final
suite. Frontend view/semantics tests and production build/real-data packaging
passed. Two optional frontend checks reported absent ignored real receipts in
this worktree; they are not counted as executed. Skipped tests and historical
production checks are not new all-sky, scientific, container or public-host
certification.

The immediately usable scope is the indexed subset, with explicit failures or
single-epoch limits where fresh inputs cannot establish a pair. Complete search
still requires restored official discovery or a much broader versioned index.

---

The sections below preserve the earlier experiments and their original scope.

## Two-epoch recovery experiment (November 16 local)

**A real two-epoch WISE-field comparison now works through the independent
index in an isolated research process. The normal app still uses TAP/SIA and
has not been switched to this source.**

Two detector-3 directory scans covered DR1 periods `2025W19_1B` and
`2026W20_1A`. Historical WISE coverage chose these periods; this is a targeted
recovery experiment, not a blind all-sky coverage test. Every exposure was
rediscovered through fresh public listings and IMAGE headers, rather than
passed from the known-exposure list.

- 1,812 + 1,672 = **3,484 real headers**, all successful; 100,339,200 range bytes.
  Scan times were 164.515 seconds with four workers and 261.812 seconds with two.
- Spatial bounds passed **31,356** forward-WCS controls across these snapshots.
- Coordinate search found **four** candidates: three in 2025 and one in 2026.
  Two 2025 candidates were additional to the historical recovery list; the
  selected matched pair rediscovers the previously known exposure pair.
- The research adapter supplied this partial inventory to the unchanged
  method-13 pipeline. Three cutouts downloaded afresh, with no application-cache
  reads. Downloaded detector and UTC bounds matched indexed metadata.
- The build returned **two epochs, a difference product and 16 WebP assets in
  30.015 seconds**. `comparison_selection.status` is `matched_visual`; the
  unchanged wavelength/bandwidth gate covered **54,756 output pixels** in a
  0.2-degree field. Failed or excluded measurements were not relaxed.
- This is detector 3 imagery of the WISE field, not proof that the faint WISE
  target is detected, moves visibly, or has validated photometry. No scientific
  promotion is claimed. Research outputs remain outside runtime asset roots.

[Discovery receipts](../evidence/phase6/archive-pair-20261116/discovery.json),
[pipeline/acquisition report](../evidence/phase6/archive-pair-20261116/pair-report.json),
and [output validation](../evidence/phase6/archive-pair-20261116/pair-validation.json)
retain the measured scope and hashes. The reusable adapter is
[`cloud_pair_probe.py`](../research/archive-recovery/cloud_pair_probe.py).
It uses the existing pipeline's `live` scheduling branch for the experiment;
its discovery metadata explicitly identifies the research cloud snapshot.
That internal scheduling value is not a new approved public discovery mode.
The pipeline also generates release-based collection labels, which do not
establish wide/deep membership; the adapter records that membership as unknown.

Neither development server was running when checked. Both were restarted;
the frontend page and direct/proxied API health returned 200/API 1.6.0.
`irsa_reachable` remained false and a fresh minimal TAP query timed out after
20.500 seconds. See [runtime checks](../evidence/phase6/archive-pair-20261116/runtime.json)
and [TAP receipt](../evidence/phase6/archive-pair-20261116/tap-current.json).

The next integration must add an explicitly selected, accurately labeled
indexed-archive mode and snapshot identity to both image and spectrum flows,
URL/history/report/audio semantics, processing identity and packaging checks.
A subset miss must remain an unknown-coverage error. It must not silently
replace live discovery or pretend these two detector directories cover the
five catalog targets or arbitrary sky. Resumable ingestion and broader measured
coverage remain necessary before claiming general archive recovery.

## Continuation: independent coordinate-index prototype

November 15, 22:48 UTC onward (November 16 locally). **Default application
archive discovery is still unresolved.** This continuation produced working
research code for an independent search route; it is not wired into the API.

Fresh controls narrowed the failure: availability returned 200 with
`available=true`, while the minimal plane and WISE SIA queries timed out.
A new async creation attempt returned 502 in 0.922 seconds, so no new job was
created and the proposed longer queue observation could not run. The old
43-second QUEUED result remains inconclusive about eventual completion.
Two direct, non-spatial TAP lookups of an exact plane ID returned by MOST
also timed out after 60.469/61.016 seconds. MOST again returned 66 rows in
1.891 seconds. This rules out our spatial join as a necessary trigger; it does
not identify the internal service failure or prove global downtime.

The cube product documentation lists IMAGE, NHITS, FLAGS, SPECTRAL_CHANNELS and
WCS-WAVE, without a per-exposure inventory. It did not establish a shortcut to
an independent temporal observation index. MOST remains a trajectory search.

### Implemented and measured

The [research tools](../research/archive-recovery/README.md) enumerate one
public AWS directory and build an immutable local metadata snapshot from real
FITS IMAGE headers. The measured scope is QR3 period `2026W40_2A`, processing
version `l2b-v27-2026-285`, detector 1. It was selected from public directory
listings, not from a catalog exposure list.

- Complete two-page enumeration: **1,718 objects**.
- **1,718 successful header reads**, no failed headers, in **148.610 seconds**
  with four workers. Range bodies totaled **49,478,400 bytes**; retained IMAGE
  headers totaled **44,530,560 bytes**. No full images were downloaded in this scan.
- Range length, object length and ETag are checked. Unsupported layouts/time
  systems fail explicitly; missing headers prevent a complete-directory claim.
- A second enumeration returned identical keys, ETags and lengths. This checks
  the two listing views, not a transactional snapshot or future freshness.
- Five corrected catalog positions, one independently chosen position (10, 20),
  and a positive control at an indexed image center were searched. The positive
  control found **eight exposures**; the other six returned zero in this subset.
  These misses never mean no data elsewhere in the archive. Only query positions
  were taken from the catalog index; its exposure records were not search inputs.
- Exhaustive inverse-WCS searches took **37.797-57.094 seconds** per position.
  A conservative spherical prefilter reduced measured search work to
  **0.000-0.484 seconds**, excluding initial snapshot/index loading. All seven
  exact result sets agree with the exhaustive searches; 0.000 is timer rounding.
- The prefilter uses absolute SIP polynomial bounds over the pixel rectangle
  and the CD/TAN mapping, then retains the exact inverse-WCS/round-trip check.
  All **15,462** sampled in-image forward-WCS checks passed (nine per image).
  Unsupported WCS is never culled. Constructing this index took **81.218 seconds**.
- Independent receipt verification checked **1,718 header hashes** and **96**
  real-header boundary/wrap/antipodal/truncation controls across six detectors.
  These are internal geometry/integrity checks, not independent astrometric or
  scientific validation.

Receipts: [snapshot/query summary](../evidence/phase6/archive-continuation-20261115/cloud-prototype-summary.json),
[spatial search comparison](../evidence/phase6/archive-continuation-20261115/cloud-search-validation.json),
[header validation](../evidence/phase6/archive-continuation-20261115/cloud-validation.json),
and [second listing](../evidence/phase6/archive-continuation-20261115/postscan-listing-check.json).
The complete research snapshot, raw list pages and headers remain under
`backend/.cache/archive-index-prototype/qr3-d1/`, excluded from runtime packaging.
The summary hashes that local snapshot; it is not a portable complete inventory.

### Fresh image retrieval from the independently discovered result

The positive-control coordinate search selected an exposure from its eight
matches. A fresh official IRSA cutout request returned **HTTP 200 in 13.813
seconds**, **4,173,120 bytes**, with a 117 x 117 IMAGE and the expected FLAGS,
VARIANCE, ZODI, EPSF and WCS-WAVE extensions. This closes the research path from
coordinate lookup to a real newly downloaded image without TAP/SIA or the known
exposure list. It does not establish a temporal pair or scientific acceptance;
no image was promoted to runtime assets. See the
[download receipt](../evidence/phase6/archive-continuation-20261115/discovered-cutout.json).

The [updated support bundle](../evidence/phase6/irsa-support-20261115-v2.zip)
contains the revised incident, working MOST control and latest discovery
failures, with 44 hash-verified entries. It contains no FITS pixel samples and
has not been sent. The original ZIP remains unchanged as a historical record.

### Remaining work before application integration

This proves bounded independent metadata search, not restored five-target or
arbitrary-coordinate operation. One detector/period lacks all five catalog
positions and temporal comparison coverage. The next milestone is a bounded
multi-period, multi-detector inventory with known coverage controls, followed
by fresh downloads and the existing wavelength/usable-pixel comparison gates.
Before adoption, implement resumable ingestion and failed-object recovery,
measure wider storage/update costs, handle version duplicates and release
semantics, define snapshot freshness and partial-coverage provenance, and make
a coordinated architecture/API decision. Collection membership remains unknown;
wide/deep membership is not guessed from filenames. No automatic fallback,
processing change, runtime index or full-archive crawl has been introduced.

## Earlier diagnostic outcome (22:10-22:14 UTC)

The authorized investigation progressed beyond the plan, but **default live
search is not restored**. No working supported discovery route was found, so
there is no evidence-backed runtime transport patch to ship. The application
remains API 1.6.0 / image method 13 with explicit known/saved recovery unchanged.

Completed: current runtime/proxy verification, fresh independent-client probes,
a portable second-network diagnostic, a ready-to-send support incident, and
bounded AWS metadata-index feasibility measurements. Pending: a controlled
second egress, service/operator diagnosis, a working discovery route and fresh
end-to-end acceptance. No support message or public deployment was sent/made.

## Runtime and fresh fault isolation

The API listener is PID 18044 on 127.0.0.1:8000; Vite listens on localhost:5173.
Both direct and frontend-proxied `/api/v1/health` requests returned API 1.6.0.
This verifies that the actual proxy can reach the API, not a full browser
observation workflow. The startup log records method 13. Source was not edited.

At 22:10 UTC, availability, minimal `spherex.plane`, and the official SIA example
all returned the same 341-byte HTTP 502 body. Native Windows curl independently
returned 502 in 0.739139 s from 134.4.54.42. Python environment proxy variables
and system proxy settings were absent. Python is 3.11.9; httpx is 0.28.1.

The new portable urllib probe also reproduced 502 responses for availability,
schema, a non-SPHEREx catalog and plane queries. Its ObsCore request encountered
a TLS handshake timeout; the SIA example hit a read timeout. Static documentation
returned 200. Failures are retained rather than replaced by successful retries.

The health probe briefly returned `irsa_reachable=true` and its application log
records HTTP 200 for availability at 22:13:11 UTC. Subsequent direct availability
and plane queries again returned 502. This reinforces that availability is an
intermittent, separate signal; it is not science-query readiness. The earlier
fresh default WISE request still stands as the latest end-to-end measurement:
503 after 62.203 s, with all SIA collections failed and TAP deadline exhaustion.

The remote web-fetch tool could not access the two query URLs. It supplies no
controlled egress identity/raw response comparison, so it is **not counted as
a second-network test**. No usable remote runner was established in this turn.
The user confirmed that no second machine is available.

Reproduction tool: [`probe.py`](../research/archive-recovery/probe.py).
It uses standard Python, saves exact URLs/times/statuses/hashes, caps response
size and never retries or creates jobs. Run from a second network and compare
to a new near-simultaneous local run. The prepared
[IRSA incident](irsa-incident-draft-2026-11-15.md) is ready for review/sending.

## New evidence: independent index feasibility

All discovery in this experiment used public AWS directory listings; no known
target index or TAP/SIA result was used to select these sample objects.

- Complete root/release/level2 prefix listings were retrieved for DR1 and QR3.
  No standalone metadata manifest appeared at those inspected levels. Deeper
  or separately published manifests remain possible.
- Selected the first listed FITS object from the first, middle and last planning
  period of each release: six objects, initially all detector 1. Range reads of
  65,536 bytes each contained PRIMARY and the complete IMAGE header.
- IMAGE starts at byte 2,880 in these samples. Spatial TAN-SIP WCS, detector,
  UTC `MJD-BEG`/`MJD-END` and dates are present in IMAGE; PRIMARY did not contain
  the needed observation metadata. Only headers were parsed; PRIMARY data was
  never accessed. Four-corner footprints were computed for exploratory inspection,
  not accepted as exact curved-edge containment.
- A separate follow-up selected the first object for **each detector 1–6** in
  the latest QR3 period. Every 28,800-byte range contained the complete IMAGE
  header. Reads took 0.218–0.391 s on a reused connection. UTC bounds, detector
  IDs and spatial WCS parsed; center pixel/world round trips passed within
  1e-5 pixels. This is an internal WCS check, not independent astrometric validation.
- A bounded, fully paginated listing of that one QR3 period completed in 11
  pages and 4.578 s: **10,352 objects totaling 672,703,073,280 bytes**. The final
  page was explicitly non-truncated. This is one period, not a full archive count.

The metadata extraction premise therefore passes a small feasibility gate:
we can obtain real per-exposure position/time metadata independently of IRSA
discovery, without downloading each full 62–66 MB image. That is substantially
more concrete than merely observing that an AWS bucket exists.

### Cost and unresolved design

For the measured 10,352-object period, one 28,800-byte read per object would
transfer about **298 MB** of response bodies, rather than 673 GB of full files.
At the observed 0.218–0.391 s per request, serial header acquisition alone would
take roughly **38–67 minutes**, excluding retries, listing, parsing and storage.
These are extrapolations, not a completed index build or sustained throughput.
At one million objects the same body-size assumption is 28.8 GB and about
61–109 serial hours; one million is a sizing scenario, not the measured total.

Do not multiply a single period count into a purported complete archive count.
The six initial period listings were each capped at 1,000 rows and truncated.
Only the latest QR3 period was enumerated fully. Further work must measure
archive volume, version duplication and update cadence before a full crawl.

An implementation would still need adaptive header lengths (28,800 is a sample
finding, not a format guarantee), bounded retries and resumable manifests,
object/version identity, complete enumeration watermarks, spherical broad-phase
search followed by exact inverse spatial WCS containment, wrap/pole/edge tests,
release/collection semantics, atomic snapshots and explicit snapshot provenance.
Comparison wavelength checks still require actual science/WCS-WAVE inputs.
No inference of wide/deep collection membership from a directory name is approved.

**Decision:** proceedable as an offline research prototype; not ready to replace
live discovery or be presented as complete coverage. Integrating an indexed
source still requires the architecture and additive provenance decision in the
[recovery plan](../plans/archive-recovery-plan-2026-11-15.md). No runtime adapter,
database or full-archive crawl was introduced.

## Evidence and next executable step

Receipts are in [`archive-execution-20261115`](../evidence/phase6/archive-execution-20261115/).
`header-feasibility.json` identifies six initial byte-range samples and their
hashes; `all-detector-header-check.json` records six subsequent range reads
(one object overlaps). Retained `.header` files contain only padded headers;
the initial `.bin` range captures include bytes beyond the headers and are
diagnostic samples, never runtime observations. `bounded-period-count.json`
lists hashes for the full period pages retained under
`backend/.cache/archive-index-feasibility/`. These local raw-page receipts are
not a portable archive inventory.

With no second machine available, the next external action is to submit the
prepared support incident and request service diagnosis or an official bulk
manifest. The independent-network comparison stays unverified; run the portable
probe if another network becomes available. If only this network fails,
investigate the measured transport difference.
Default archive acceptance remains blocked until one of those branches yields
valid science metadata. Repeating full five-target builds now would not test a
new repair. The six-header study provides a measured starting point for the
independent-index branch, not a disguised recovery claim.

The [support ZIP](../evidence/phase6/irsa-support-20261115.zip) packages the
incident draft, portable tool and selected public-query receipts with a SHA-256
manifest. No science pixel samples are included. ZIP integrity, 23 retained
response/header hashes, portable-script syntax and 418 local documentation
destinations passed verification before this final package link was added.
The portable network run correctly exited 1 for failed discovery. Its recorded
script hash predates a final tightening that additionally requires returned
TABLEDATA rows; the final script was syntax-checked, not re-run against IRSA.
