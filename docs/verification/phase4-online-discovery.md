# Fresh upstream discovery: diagnosis and repair

These measurements were made on 2026-11-14 against IRSA, without discovering
inputs from the saved target manifests. Raw HTTP bodies, query parameters,
retrieval times, SHA-256 hashes and sizes are retained under
`backend/.cache/phase4/online-discovery/`; the accompanying
`docs/phase4-online-discovery-*.json` files preserve each run, including failures.
No cutouts or flux measurements were used to select these diagnostic fields.

## What failed

An application HTTP 503 does not necessarily mean IRSA returned HTTP 503.
The application maps incomplete discovery, archive HTTP 502 and timeouts to
its upstream-unavailable response. The new raw probes distinguish those cases.

- TAP availability returned HTTP 200, while a small `TAP_SCHEMA.tables` query
  returned HTTP 502 in 1.078 s. The returned proxy error says it received an
  invalid upstream response and failed while reading from the remote server.
- The same north Galactic pole spatial TAP query timed out after 90.734 s
  using both GET and form-encoded POST. Changing HTTP method did not repair it.
- At the same time, unchanged SIA requests at the north Galactic pole returned
  DR1 **268 rows in 3.250 s** and QR3 **131 rows in 2.782 s**.
- Collection failures were intermittent and affected both wide and deep
  collections. In the first geometry run, the west side of RA zero returned
  all four collections; the east side returned the same 223 DR1 and 114 QR3
  wide rows but failed on both deep collections. At the exact north pole DR1
  succeeded while QR3 failed; at the south pole QR3 succeeded while DR1 failed.
- An identical failed south-pole DR1 query also returned HTTP 502 using
  form-encoded POST and multipart POST. A documented multi-collection SIA
  request likewise returned HTTP 502 in the two initial probes.

The measured failure is an upstream proxy/backend response problem, not a
general inability to reach IRSA or evidence that these positions have no data.
The exact internal archive failure cannot be established without IRSA's server
logs. The observations do not justify asserting a particular database or
load-balancer defect. Earlier successful archived observations are not used as
a substitute for these fresh measurements.

Evidence: [initial transport probes](../evidence/phase4/phase4-online-discovery-ngp-transport-initial.json),
[south-pole method comparison](../evidence/phase4/phase4-online-discovery-south-pole-post.json),
[initial geometry run](../evidence/phase4/phase4-online-discovery-geometry-wrap-poles.json).

## Changes

`IrsaClient.query_artifacts` now tries SIA first. It queries the four current
wide/deep DR1/QR3 collections concurrently with at most four workers, each with
its own HTTP client and the same absolute stage deadline. TAP remains a bounded
fallback. Explicit `fallback=False` retains the previous TAP-only diagnostic.
The existing stable time/URI keyset pagination, page bounds, response byte
limits and VOTable `QUERY_STATUS` checks remain in force.

Retries remain controlled by `Settings`; there is no hidden retry floor.
The approved live default is three attempts. Every retry consumes the same
remaining deadline. The independent HTTP probes and earlier sequential matrix
remain in the report set; they are not relabeled as tests of the later parallel
implementation.

Strict callers still require complete discovery. The separately approved
`allow_partial=True` policy allows the live application to use nonempty rows
from **fully successful collections** while declaring `status: partial`, the
missing collections and a non-exhaustive scope. It preserves the remaining
download budget instead of waiting for a failing TAP service. Rows from an
overflowed or otherwise failed collection are discarded entirely. Partial
empty discovery remains an upstream error, never `NO_DATA`. This does not
establish exhaustive temporal coverage or scientific variability.

`use_cache=False` bypasses application cutout reads, sends
`Cache-Control: no-cache` for proxy revalidation, and still retains newly
received bytes for replay. Acquisition receipts distinguish fresh responses
from retained-cache reads and include the exact source URL, hash, size and
known retrieval time. An old cache read has an unknown original retrieval
time. Discovery bodies, including error bodies, are retained separately.

Coordinate serialization now wraps RA after decimal rounding: a valid value
just below 360 degrees cannot become an invalid `center=360.000000` request.
The exact supplied/extraction coordinate remains distinct from serialized
query coordinates. Both poles remain valid inputs.

## Fixed coordinate evidence

The preregistered positions are recorded in
[the source recheck](phase4-source-recheck.md). The uniform sequential rerun
with three attempts and proxy revalidation completed **8/9** positions:

| Position | Records | Discovery |
|---|---:|---|
| RA 359.9999, Dec 0 | 337 | Complete |
| RA 0.0001, Dec 0 | 337 | Complete |
| RA 0, Dec 89.999 | 430 | Complete |
| RA 0, Dec 90 | 430 | Complete |
| RA 0, Dec -89.999 | 526 | Complete |
| RA 0, Dec -90 | 526 | Complete |
| North Galactic pole | 399 | Complete |
| Galactic centre | 302 | Complete |
| Historical Field B | — | Upstream failure retained |

The successful calls took 5.609–28.313 s under those test settings. This tests
metadata discovery, not image usability or a universal service guarantee.
[Full retry-run evidence](../evidence/phase4/phase4-online-discovery-geometry-retry3.json)

Two additional independently preregistered science regions returned complete
inventories: north-b60 **246 rows** and south-b60 **354 rows**. Their raw
footprints were passed to the science agent before SPHEREx flux inspection.
The repeated strict south Galactic pole call failed; the earlier fresh wide
snapshot remains explicitly scoped rather than being called complete.
[Science-region discovery](../evidence/phase4/phase4-online-discovery-science-retry3.json)

The later parallel/explicit-partial run is stored separately as
`docs/evidence/phase4/phase4-online-discovery-geometry-final-policy.json`. It returned real
metadata at **9/9** fixed positions in **5.141–6.672 s**: **8 complete** and
**1 explicitly partial**. Galactic-centre DR1 returned 207 records while QR3
failed; the missing collection is recorded. Historical Field B returned 331
records on this later attempt. All earlier failures remain in their original
reports. Consult the per-field status rather than treating every returned
inventory as complete. These are metadata-only outcomes, not nine successful
image comparisons or an all-coordinate guarantee.

## Verification and authoritative interfaces

The focused discovery tests cover unchanged overflow/keyset/deadline behavior,
fresh-cache bypass and receipts, RA wrapping, concurrent collection requests,
strict rejection of partial results, exclusion of overflowed-collection rows,
partial-empty errors and bounded waits for stalled workers. Generated transport
bytes stay inside tests; none are observations or runtime fallback data.

IRSA documents SIA2 for current SPHEREx spectral images and notes that SIA
ingestion can lag the directory/TAP interfaces by about a day. That lag remains
visible in discovery metadata; SIA success does not mean the archive contains
no newer unindexed observations.
[Official SPHEREx data access](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access/)

IRSA's SIA documentation supports repeated `COLLECTION` parameters and both
GET examples and POST form examples; those alternatives were tested without
changing the scientific position. The documentation was retrieved with normal
TLS and retained as `online-discovery/sia-doc.html`.
[Official SIA instructions](https://irsa.ipac.caltech.edu/ibe/sia.html)

IRSA documents synchronous TAP and asynchronous jobs; the failed synchronous
probes here do not establish that every TAP mode is unavailable. Moving a
public request to an unbounded asynchronous archive job is not part of this
repair.
[Official TAP instructions](https://irsa.ipac.caltech.edu/docs/program_interface/TAP.html)
