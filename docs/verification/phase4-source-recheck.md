# Phase 4 online-source recheck

Checked 2026-11-14, approximately 20:48–20:49 UTC. This is a fresh primary-source
review, not a claim that historical saved products have been refreshed.

## Official resources and current use

The [official challenge Resources tab](https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/?tab=resources)
was fetched successfully with installed Chrome and normal TLS validation. It
still lists four NASA resources and four CSA partner resources. Initial Python
and PowerShell attempts failed certificate-chain validation; no TLS verification
was disabled. The browser-rendered capture and request log are retained under
`backend/.cache/phase4/source-recheck/`.

| Listed resource | Current project use | Not implemented by citing it |
|---|---|---|
| [IRSA SPHEREx](https://irsa.ipac.caltech.edu/Missions/spherex.html) | TAP/SIA discovery, real spectral-image cutouts, calibration references | Full-sky guaranteed temporal comparisons; every archive tool |
| [SPHEREx notebooks](https://caltech-ipac.github.io/irsa-tutorials/spherex/) | Access/file-layout guidance and validation reference | Running every notebook or every science tool in production |
| [WiseView](http://byw.tools/wiseview) | Blink-viewer inspiration; separate WISE reference products in historical saved data | WiseView ingestion or a live WiseView integration |
| [Gaia at MAST](https://archive.stsci.edu/missions-and-data/gaia) | Gaia DR3 reference positions, saved pins, independent audit queries | Automatic DR4 migration or fresh pins for every arbitrary query |
| [NEOSSat overview](https://www.asc-csa.gc.ca/eng/satellites/neossat/) | Related-resource context | Data ingestion |
| [CADC](https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/en/) | Related-resource context | Data ingestion |
| [NEOSSat tutorial](https://github.com/asc-csa/NEOSSAT_Tutorial) | Related-resource context | Executed production pipeline |
| [NEOSSat dataset](https://data.asc-csa.gc.ca/dataset/neossat) | Related-resource context | Data ingestion |

The [IRSA release page](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_dr1.html)
confirms November 2026 DR1, reprocessed QR2 spectral images intended for joint
use with QR3, and a 102-channel all-sky cube. The cube is available upstream but
is not the app's native-exposure spectrum source. [The QR overview](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_qr.html)
states that QR2 is absent from IRSA/VO search results and remains directly
downloadable through February 2027. DR1/QR3 remain the correct image releases.
MOST, mosaic, source discovery and the hosted spectrophotometry tool are linked
upstream; they are not runtime dependencies merely because IRSA lists them.

[ESA's release schedule](https://www.cosmos.esa.int/web/gaia/release) and
[DR4 page](https://www.cosmos.esa.int/web/gaia/data-release-4) were independently
fetched with HTTP 200 and verified TLS. DR4 is scheduled for 2 December 2026;
DR3 remains the latest full release today. The 2023 focused product release is
separate. The challenge still explicitly names DR3. The former guessed path
`/web/gaia/data-release-scenario` returned 404; it is not the source of this claim.

## Request-flow audit before the approved archive-first change

- `backend/routers/sky.py:470` and `spectrum.py:201` use saved catalog products
  without contacting IRSA. `/api` and the frontend's `source: "live"` therefore
  do not mean upstream acquisition occurred.
- `frontend/src/hooks/useSkyData.ts:30` gives catalog requests 20 seconds versus
  130 seconds for arbitrary fields. The catalog budget must change for online
  acquisition. The timeout helper races a timer but does not abort its fetch.
- `backend/routers/assets.py:61` gives catalog-named saved assets precedence.
  Online corrected-coordinate products require separate live keys, or a new
  manifest could accidentally load an old image with the same filename.
- `frontend/src/App.tsx:550` has a retry-only initial error screen. Technical
  details exist in hook state but the visible message conflates no coverage,
  unavailable upstream services and incompatible comparisons. An online default
  needs coordinate/source recovery controls in this state.
- The coordinate parser accepts both poles and normalizes RA 360 to zero;
  direct API RA remains `[0,360)`. Numeric entry is currently snapped within
  five arcminutes of catalog reference/query coordinates. That behavior conflicts
  with preserving arbitrary user positions and must be restricted to explicit
  named-target selection.

The approved [API 1.5 source policy](../decisions/phase4-online-contract-decision.md) resolves
the architectural choice: archive by default, explicit saved mode, no automatic
fallback. Saved coordinates remain paired with saved products; reviewed corrected
seeds are used only for archive products. Source and comparison provenance must
be visible and included in request/cache/share keys. Missing reference overlays
must remain unavailable rather than copied from a different WCS.

## Preregistered lightweight coordinate matrix

Frozen here before the discovery agent runs this expanded matrix. Metadata-only
TAP/SIA discovery initially; no result-dependent replacement fields and no claim
that metadata coverage guarantees usable pixels or comparable epochs. The
discovery agent owns upstream probes to avoid duplicate archive load. Record
transport, request parameters, HTTP status, elapsed time, rows/overflow,
collections, and errors for every attempt. Cap each probe at its configured
deadline; failed/partial attempts remain in the report.

| ID | RA deg | Dec deg | Reason |
|---|---:|---:|---|
| wrap-west | 359.9999 | 0 | Cross-zero boundary |
| wrap-east | 0.0001 | 0 | Nearby position on other side |
| north-near | 0 | 89.999 | Near-pole geometry |
| north-pole | 0 | 90 | Exact coordinate singularity |
| south-near | 0 | -89.999 | Near-pole geometry |
| south-pole | 0 | -90 | Exact coordinate singularity |
| sparse-galactic-pole | 192.85948 | 27.12825 | Sparse field, fixed before query |
| dense-galactic-centre | 266.4051 | -28.936175 | Crowding/extinction stress |
| historical-field-b | 334.622377 | 0.806761 | Previous bounded-discovery reference |

Use a 0.2-degree field for consistent metadata comparisons. Also retain the
discovery agent's already selected corrected Epsilon Indi control, with its
exact coordinates in that agent's log. Invalid-value parser tests (NaN/infinity,
out-of-range Dec, malformed sexagesimal) are local and must not contact IRSA.
Acceptance is correct bounded behavior and honest outcomes across these cases;
neither universal available data nor universal scientific validity is asserted.

First full application probe: NGP at size 0.05 via API 1.5 returned HTTP 503 in
5.736 seconds, with upstream HTTP 502 errors from both discovery paths. The
frontend preserved the exact coordinates and archive selection without saved
fallback. This does not establish pixel/epoch coverage; the metadata-only
matrix and transport diagnosis are recorded separately by the discovery agent.

Following the coordinated reliability changes, the same NGP 0.05-degree
application request succeeded in 108.524 seconds with one actual QR3 epoch.
Discovery completed all four current-release collections with 399 rows total;
54 input receipts explicitly record fresh archive responses and no local cache
read. The browser displayed the lack of a matched comparison and no differences.
This successful fresh-input case, its served asset hashes, and the preserved
earlier failures are documented in [UI verification](phase4-ui-metadata-verification.md).

## Fetch evidence

Local logs: `fetch-log.json`, `additional-fetch-log.json`,
`challenge-browser-log.json`, and corresponding HTML captures in the ignored
source-recheck directory. The challenge capture SHA-256 is
`011bd1a5a4d8a2e1379a515377c27b29a85869207654414499cf8aa32b54a6af`.
DR1 HTML: `de48a08241e09e22abd9b2f1f74384ff473710d425174bed5ea1427b1901c1b1`;
QR HTML: `de4ce8a8e971388a1e4d0721f5d5e2b3a6caeaca89c64511d49c0f6c5ff4b098`;
ESA release schedule: `980c40c04de5fca7d27fa827aa08749b530ccab92b380f9cd3d3ebc4ee7c910f`.
These are retrieved-page identities, not observation-data provenance.
