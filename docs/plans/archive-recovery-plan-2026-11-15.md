# Online archive recovery: diagnosis and execution plan

Prepared 2026-11-15 following renewed direct probes at 22:04–22:06 UTC. This is
an engineering plan with measured starting evidence, not a claim that live
discovery is repaired. API 1.6.0 and image method 13 remain unchanged.

**Execution follow-up:** [completed diagnostics and bounded AWS index study](../verification/archive-recovery-execution-2026-11-15.md).
The user confirmed no second machine is available. A support bundle is prepared;
current discovery still fails and end-to-end repair acceptance remains open.

## Decision

Prioritize restoring a working **metadata search**, then verify fresh file
retrieval and comparison separately. Increasing download retries cannot repair
an unavailable observation inventory. The current evidence supports a failure
in the remote discovery request path; it does not identify the failing internal
IRSA component or exclude a network-specific intermediary.

There are two recovery tracks:

1. Restore supported IRSA discovery through a demonstrably working route. This
   is the shortest path and should receive the first bounded diagnostic session.
2. If IRSA discovery remains unavailable, scope an independent, maintained
   exposure metadata index. This can remove that dependency but is a substantial
   architecture change, not another timeout adjustment or a five-target patch.

## What actually fails

The request pipeline is: local API → coordinate/collection discovery → candidate
selection → FITS download → scientific compatibility/quality checks → output.
Each stage needs its own result. A failed discovery is not an empty sky, a
downloaded file is not a compatible pair, and a pair is not target detection.

The code currently runs **SIA first, then TAP**, despite historical roadmap text
saying TAP first. See `IrsaClient.query_artifacts` in
[`irsa_client.py`](../../backend/services/irsa_client.py). SIA searches four
current wide/deep collections concurrently with a shared deadline. TAP queries
the artifact/plane join and paginates by time and URI. Partial SIA rows may be
returned explicitly to preserve acquisition time. These existing protections
must survive any repair.

### Fresh observations from this investigation

Exact request URLs, timings, response bodies and hashes are retained in
[`archive-recovery-20261115`](../evidence/phase6/archive-recovery-20261115/).
The first matrix used two workers, a 25-second socket timeout and no retries.
Socket timeout is not a hard total wall-clock deadline.

| Probe | Result | Meaning |
|---|---|---|
| TAP availability | 502, 1.375 s | Earlier availability success no longer describes this run. |
| TAP schema, one row | 502, 1.375 s | Failure now extends beyond science queries. |
| Non-SPHEREx `fp_psc`, one row | 502, 1.110 s | Not confined to the SPHEREx artifact join. |
| SPHEREx ObsCore, one row, no spatial predicate | 502, 1.110 s | Spatial geometry is not required to trigger failure. |
| SPHEREx plane, one row | Read timeout, 25.765 s | No usable metadata response. |
| Exact official DR1 SIA HTML example | 502, 0.921 s | Failure exists outside SkyBlink's query implementation. |
| IRSA static cloud guide | 200, 1.547 s | The entire host is not unreachable. |
| AWS byte range of one indexed DR1 FITS | 206, 1.250 s; 5,760 bytes | File storage works for this object; not discovery or full-file validation. |
| Local port 8000 before startup | Connection refused | A separate local service problem existed in this session. |

All five 502 bodies have the same SHA-256 and say the proxy received an invalid
upstream response, with an error reading from the remote server. The plane
request instead timed out. These distinguish transport/service errors from a
valid zero-row VOTable; they do not prove the underlying database is down.

The AWS object reports a total length of 65,790,720 bytes and begins with the
FITS signature. Its path was taken from the existing known-exposure index; it
was **not discovered anew**. Reading a header does not establish that all science
extensions, cutouts or a comparison can be retrieved correctly.

The local API was started using the existing `scripts/dev_api.py --no-reload`
launcher. Startup reports API 1.6.0 and method 13; subsequent health returned
200 with `irsa_reachable=false`. An earlier health attempt during startup also
failed and is retained. No application source was modified.

A subsequent fresh WISE `source=archive&discovery=live` sky request returned
503 `UPSTREAM_UNAVAILABLE` after **62.203 seconds**. All four SIA collections
failed and TAP exhausted its remaining deadline. The exact response is in
`default_archive_after_start.json`. Starting the API repaired local availability
only; it did not repair remote discovery. The method-13 API remains running.

## Why the previous attempts did not solve it

| Attempt | What it established | Why the default search still fails |
|---|---|---|
| Replace stale method-11 worker with method 12 | The user's old worker really ran obsolete acquisition logic; a fresh worker obtained a pair. | Fixed a local process problem, not later remote discovery failure. |
| Balanced pair downloads, then method-13 missing-partner completion | Addressed an 18-second round losing a partner despite remaining overall budget. | Runs after discovery. No inventory means no candidates to retry. The recorded post-fix success did not enter the new retry branch. |
| Explicit known exposures | Fresh FITS downloads and real comparisons can work when discovery is bypassed. | Historical metadata for five fields cannot find new observations or arbitrary positions. |
| Longer synchronous query | A constrained spatial TAP request still timed out after 65.750 s. | More waiting did not produce rows; it would consume the image-processing budget. |
| Parameter casing, curl/Python/browser, official positive-radius example | Failure reproduced independently of the application transport and zero-radius syntax. | Variants still depend on the same failing service path. |
| Asynchronous TAP | A job was accepted but stayed queued over roughly 43 s. | Job creation is not execution. Later job reads returned 502; abort/delete cleanup was unconfirmed. Forty-three seconds also does not prove it could never finish. |
| Multipart POST and async GET | Both returned proxy errors. | Encoding/method changes did not establish a working transport. |
| Official Explorer server-side request and minimal ObsCore | Explorer returned an error payload despite HTTP 200; direct ObsCore returned 502. | Another interface is not necessarily an independent search backend. |
| AWS listing | Public objects and release directories are accessible. | Object names do not supply sky footprints. Only root/release levels were inspected; absence of a published index was not exhaustively established. |

Sources: [stale worker/source review](../research/catalog-acquisition-source-review.md),
[outage and known recovery](../verification/phase5-discovery-outage-verification.md),
[method-13 diagnosis](../verification/phase6-live-discovery-diagnosis.md), and
[renewed Explorer/TAP investigation](../verification/phase6-archive-search-renewed.md).

The main diagnostic gap was **fault isolation**, not lack of retries. Previous
checks did not establish same-time availability from a separate network, an
operator-confirmed cause, or a usable independent coordinate index. Reports
also mixed historical success, availability checks and later outages; their
dates and scope must remain visible.

## Execution sequence and decision gates

Effort ranges below are engineering estimates, not promises about archive
recovery. Work in sequence; do not repeatedly run full target builds while the
small discovery controls fail.

### 1. Establish the runtime and a reproducible incident bundle — 30–60 minutes

Owner: integration, with backend diagnostics.

- Verify the frontend proxy points to the actual listener; record PID, working
  directory, API/method and processing identity. Use explicit Windows background
  restarts; a watcher parent is insufficient evidence of a loaded worker.
- Preserve timestamp, exact public URL/ADQL, resolved address, client version,
  status, selected response headers, body hash, elapsed time and exception for
  each probe. Record explicit proxy presence without exposing credentials.
- Use the small matrix above: static page, availability, schema, non-SPHEREx
  row, SPHEREx row and official SIA example. Limit concurrency to two and avoid
  automatic retries. Diagnose failures by stage and VOTable `QUERY_STATUS`.
- Keep local API availability separate from archive readiness. Do not change
  the meaning/type of existing health fields silently. A richer readiness
  endpoint/UI requires an additive coordinated contract decision.

**Exit:** a reproducible smallest failing request and current runtime identity.
Much of this step is completed here; browser proxy verification and a complete
environment/network inventory remain.

### 2. Distinguish a network-specific failure from shared service failure — 30–60 minutes

Owner: integration/backend. Run the **same public requests**, close in time,
from an available second egress such as another machine/network or an existing
remote runner. Different clients on this Windows host do not satisfy this test.
No new paid hosting or public deployment is needed for the diagnostic.

- Remote succeeds/local fails: inspect configured proxy, DNS, TLS and HTTP
  negotiation; reproduce the difference with native curl. Keep certificate
  verification enabled and the documented hostname. Do not adopt guessed IPs
  or undocumented hosts as production endpoints.
- Both fail similarly: prepare an IRSA incident report with the minimal queries,
  UTC times, hashes, old queued job ID `28362490`, and successful storage/static
  controls. Ask about service status, recommended discovery route and whether a
  bulk footprint/time manifest exists. Sending the report is a separate user
  action/authorization; no message has been sent.
- Only SPHEREx fails while another catalog works: focus on the SPHEREx table
  service/ingestion path. If minimal rows work but spatial queries fail, proceed
  to the query-isolation ladder below.

**Exit:** evidence selecting one branch. A web-search fetch or cached page is
not equivalent to a controlled independent network test. No such test has been
completed in this session.

### 3. Prove a supported discovery route before editing runtime code — 1–3 hours

Owner: backend; science independently checks inventory semantics.

Once minimal science rows are available, test incrementally: one plane/ObsCore
row → center containment → one detector → current-release science filter →
artifact join → ordering → multi-page inventory. Use the same corrected target
position at each step, then an arbitrary field. Inspect errors and overflow,
not just HTTP status. One-row probes establish execution only, not completeness.

If only spatial/join/sort stages fail, benchmark equivalent documented queries
and inspect returned IDs before adopting an ObsCore adapter or a changed query
order. If synchronous execution alone is the bottleneck, test one bounded async
job with terminal-state/result retrieval and verified cleanup. Do not keep
creating jobs while the service fails; revisit the existing orphan only when
job management responds. Async adoption requires cancellation and lifecycle
design and may need a background-job API rather than a longer HTTP timeout.

**Exit:** a route returns usable exposure URLs, detector, times, release and
footprints for a catalog and arbitrary field; bounded pagination/overflow and
partial collections are understood. Only then implement the smallest patch.

### 4. Implement and validate the evidenced repair — 0.5–1 working day

Owners: backend acquisition; science tests/receipts; integration contract/review;
frontend only for user-visible state changes.

- Change the failing layer identified in step 3. Retain global deadlines,
  same-query sharing, admission limits and provenance. Preserve SIA ingestion
  lag and incomplete-collection reporting. Do not switch to known/saved mode
  automatically or misreport failures as `NO_DATA`.
- Add regressions for the demonstrated failure: HTTP 200 error documents,
  VOTable errors/overflow, incomplete pages, deadline/cancellation and source
  selection as appropriate. Reuse existing discovery-boundary tests.
- If file retrieval is also impaired, test one complete on-premises/AWS pair
  of the **same object**, then compare HDUs, spatial/spectral WCS, flags,
  variance, ZODI and extracted pixels. Verify byte identity when expected;
  document representation differences. A successful 5,760-byte range alone
  cannot authorize replacing the download path.
- Cap transfer size, concurrency and time. Re-run processing on fresh bytes;
  preserve exact source URL/object identity and hashes. Change processing/cache
  identity if behavior changes. API changes need the normal contract decision.

**Exit:** focused regressions pass and fresh actual-server discovery works.
If no working discovery route is evidenced, stop this branch; do not write a
speculative transport adapter simply to show code progress.

### 5. Acceptance through the actual application — 2–4 hours initially

Use fresh archive/live requests, with no known index or product-cache reads:
all five named fields plus fixed arbitrary positions (including the north
Galactic pole, RA wrap, pole and a detector-edge control). Run sequentially and
retain first failures and any explicitly separate retries. Measure discovery,
download, processing and publication separately.

For each request verify inventory status, distinct actual observation times,
fresh input receipts, unchanged wavelength/mask/background acceptance,
analysis identity and served asset hashes. Test both sky and spectrum; null or
excluded photometry is not retrieval failure. Complete-empty results at truly
uncovered positions are valid; outages are not complete-empty results.

At least one catalog field and one arbitrary covered field must produce a
fresh accepted pair to claim restored end-to-end comparison. Record every
other field's status rather than requiring scientifically unsupported pairs.
Verify the frontend's actual default request without response interception,
consistent source labels and no automatic fallback. Run strict replay on a
new analysis and the required regression/packaging checks.

Repeat a fixed small matrix in at least three separated time windows, reporting
sample size and failures. This is initial stability evidence, not an uptime SLA.
Define separately: metadata search restored, file retrieval restored, matched
comparison available, and sustained reliability still under measurement.

## If the supported discovery services remain unavailable

An **independent spatial metadata index** is the credible way to support arbitrary
coordinates without a live IRSA search dependency. An AWS download switch alone
is not. Before implementation, spend 1–2 days on a bounded feasibility study:

1. Seek an official release manifest/footprint table through published materials
   or the support request. Prefer that over scanning every image.
2. If unavailable, sample a bounded set of public objects and measure directory
   listing plus FITS header range reads. Locate actual `IMAGE` headers, not just
   PRIMARY, and verify that spatial WCS, observation bounds, detector and release
   can be recovered without downloading entire files. Compressed layout and
   extension offsets must be measured, not assumed.
3. Estimate object count, bytes, request count, wall time and update cost from
   measured samples before approving a full scan. Stop if bounded extraction
   cannot support a practical bootstrap/update schedule.
4. Design spherical footprint lookup, exact containment, wrap/pole tests,
   release/version deduplication, immutable snapshots, ingestion watermarks and
   atomic updates. Validate completeness against live inventories when available.
5. Specify explicit indexed-source provenance, snapshot date, coverage and
   freshness. Unknown coverage cannot become `NO_DATA`. Keep existing known
   mode distinct; it is a small historical subset, not the new spatial index.

A validated prototype might take several working days; a maintained complete
service is more plausibly 1–3+ weeks, conditional on metadata availability and
volume. The repository currently excludes a database/full-sky archive from MVP
scope, so this needs a separate architecture/policy decision before integration.
It is proposed here, not authorized as a hidden fallback or implemented.

## Official references and boundaries

- [IRSA SPHEREx data access](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access/)
  documents the current DR1/QR3 wide/deep collections, SIA example, cutouts and
  the roughly one-day SIA ingestion lag. Lag cannot explain proxy errors from
  minimal queries and availability endpoints.
- [IRSA TAP instructions](https://irsa.ipac.caltech.edu/docs/program_interface/TAP.html)
  describe synchronous/asynchronous access and overflow behavior. Merely
  switching libraries still calls these remote services.
- [IRSA cloud access](https://irsa.ipac.caltech.edu/cloud_access/)
  identifies the anonymous AWS bucket and release prefixes. It establishes a
  supported storage source, not an independent coordinate-search API.

Immediate recommendation: finish network/service fault isolation and prepare
the reproducible support bundle while preserving explicit known-mode recovery.
Do not spend another iteration changing download retries to address discovery.
