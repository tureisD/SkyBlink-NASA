# Phase 2 verification: arbitrary-coordinate temporal viewing

Date: 2026-11-14. This document records implementation checks separately from
successful live science retrieval. A passing unit test does not prove archive
coverage, independent photometric correctness, or public deployment readiness.

## Primary-source decisions

IRSA's SIA2 documentation defines POS using circle, polygon, or range shapes,
with footprint-intersection semantics. It does not document `POS=POINT`.
The client uses a zero-radius circle to request containment of the selected
coordinate rather than overlap anywhere within a broad radius. The published
SIA2 definition specifies the circle syntax and does not state a positive
minimum radius. A real DR1 SIA request at WISE 0855 accepted radius zero and
returned 258 records in 3.98 seconds; radius 0.000001 degrees returned the same
258 records in 4.42 seconds. The contemporaneous TAP request returned proxy
HTTP 502 in 1.52 seconds. This confirms SIA syntax acceptance, not full live
image-pipeline acceptance. These measurements were made by the discovery
implementation agent in the same verification session.
[IRSA SIA2 documentation](https://irsa.ipac.caltech.edu/ibe/sia.html),
[IVOA SIA2 recommendation, section 2.1.1](https://www.ivoa.net/documents/SIA/20151223/REC-SIA-2.0-20151223.html)

IRSA documents `TOP`, `MAXREC`, and ordered queries. Its documentation explicitly
distinguishes their truncation behavior: MAXREC reports overflow, while TOP
alone does not. The client therefore checks full pages and the response's
status metadata, including trailing INFO elements. Equal timestamps require a
second unique ordering key. [IRSA TAP documentation](https://irsa.ipac.caltech.edu/docs/program_interface/TAP.html)

OFFSET is an optional ADQL 2.1 feature; its presence cannot be assumed merely
because a service supports ADQL. The implementation instead uses time-plus-URI
keyset continuation. This is an implementation choice based on documented
comparison and ordering operations; it is not a claim that IRSA's OFFSET
implementation was experimentally disproved.
[IVOA ADQL 2.1 recommendation](https://ivoa.net/documents/ADQL/20231215/REC-ADQL-2.1.html)

## Controlled verification

The backend coordinate matrix checks valid RA values around zero, declinations
near and exactly at both poles, and a dense-field coordinate. It verifies FOV
0.05° and 0.2°, clamping outside that range, and rejection of invalid/nonfinite
coordinates before discovery. An explicit empty-archive protocol response is
used; these tests generate no sky images.

Discovery tests cover same-timestamp page continuation, full final pages,
exhausted page budgets, nonadvancing cursors, nested/trailing ERROR and OVERFLOW,
partial SIA collection failure, a fully successful empty SIA result after TAP
failure, preservation of the shared deadline, bounded blocked HTTP responses,
and bounded cutout-worker waiting.

Selection tests use isolated numeric signature arrays to verify the narrower
bandwidth tolerance, all nine field samples, rejection of missing/invalid
samples, most-recent compatible pair selection, identical output band sets,
and the distinction between incompatible multi-epoch samples and genuine
single-epoch coverage. These arrays are algorithm test inputs and are not
observations or packaged assets.

Singleflight tests check shared work for simultaneous same-key requests,
independent waiting deadlines, expired leaders, and retry after failure.
Pipeline tests verify genuine single-epoch coverage, rejection of incompatible
multiple epochs, failure when a missing download prevents verifying a pair,
success when a complete verified pair exists despite an unused candidate's
download failure, and the minimum-two-candidate
configuration rule. A malformed spectral WCS is an upstream failure, not proof
of no coverage.

Integrated backend verification: **157 passed**. Frontend TAN verification:
**1,458 samples** against independent Astropy calculations, maximum inverse
error **1.1733e-10 pixels**, including exact poles, RA wrapping, and invalid
projection domains. Frontend real-data protocol tests and production build
passed. The packaging guard passed and all **288** approved real-cache files
still match their frozen hashes. Generated protocol and mathematical test
inputs are declared in `phase1-data-inventory.json`.

## Reproducible live matrix

`scripts/probe_live_coordinates.py` makes real API requests using FastAPI's
TestClient and the actual networked pipeline. Every field/size runs in a
separate subprocess with an isolated temporary cache and a 145-second hard
wall-clock probe limit. The default two-field smoke can be expanded with:

```powershell
.venv311/Scripts/python.exe scripts/probe_live_coordinates.py --fields all --sizes .05,.2 --concurrent
```

| Field | RA (deg) | Dec (deg) | Purpose |
|---|---:|---:|---|
| high_latitude | 210.80227 | 54.34895 | Noncatalog high-latitude position |
| low_latitude | 83.82 | -5.39 | Low-latitude/star-forming field |
| dense_plane | 266.4051 | -28.936175 | Dense Galactic-center region |
| north_pole | 20.0 | 89.9 | High north declination |
| south_pole | 200.0 | -89.9 | High south declination |
| ra_zero_west | 359.99 | -20.0 | West side of RA wrapping |
| ra_zero_east | 0.01 | -20.0 | East side of RA wrapping |
| field_offset | 210.90227 | 54.44895 | Offset relative to first field |
| detector_edge | 134.90921145189702 | -7.347808815089828 | One native pixel inside a measured detector footprint |

`field_offset` is a shifted cutout, **not** a proven SPHEREx detector boundary.
The separate `detector_edge` case was derived from the real SIA `s_region` of
DR1 D3 exposure `2025W19_1B_0116_1`, MJD 60800.700028–60800.701361.
Its first polygon edge joins `(133.24990295057214, -6.792366530370936)` and
`(136.573730639645, -7.893897878777517)`. The great-circle midpoint was shifted
6.15 arcseconds along the inward normal toward the polygon centroid; the
computed distance is 6.1500000000221275 arcseconds. A separate live zero-radius
SIA query returned 269 rows including this exact source, confirming containment.
[Recorded DR1 source](https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/level2/2025W19_1B/l2b-v27-2026-197/3/level2_2025W19_1B_0116_1D3_spx_l2b-v27-2026-197.fits)

Warm repeats happen only after HTTP 200; failed cold attempts cannot establish
a warm-cache timing. The optional two-client pair starts with another fresh
cache. Main field/size cases run sequentially. The two detector-edge sizes run
in a second sequential process alongside the main matrix, for at most two
concurrent cases. No broader load-capacity claim is made.
The result includes statuses, elapsed time, returned epochs and differences,
provenance, and asset-fetch statuses. Neither missing data nor discovery
probability is inferred from an upstream failure.

## Baseline before Phase 2 integration

The two-field 0.05° run is recorded in `phase2-live-baseline.json`:

- `(210.80227, 54.34895)`: HTTP 503 in 2.296 seconds, upstream HTTP 502 proxy error.
- `(0.01, -20.0)`: HTTP 503 in 60.750 seconds, upstream read timeout.
- Warm retrieval was skipped for both because no product was obtained.

These are observations from this execution environment, not statements that
IRSA is globally down or those coordinates lack SPHEREx coverage.

## Final integration results

**Live acceptance has not passed.** All 18 cold field/FOV requests returned
HTTP 503. No observation payload, epoch pair, difference, or warm-cache product
was obtained. These failures do not demonstrate absent coverage. Most requests
failed during incomplete discovery; two exhausted the shared 120-second budget.
The paired-client and extended-budget diagnostic results are recorded below.
Machine-readable details are in `phase2-live-results.json` and
`phase2-live-detector-edge.json`.

| Field | FOV (degrees) | Cold HTTP | Seconds | Outcome |
|---|---:|---:|---:|---|
| high_latitude | 0.05 | 503 | 120.063 | Shared deadline exhausted |
| high_latitude | 0.2 | 503 | 63.656 | Discovery incomplete (upstream errors/timeouts) |
| low_latitude | 0.05 | 503 | 68.235 | Discovery incomplete (upstream errors/timeouts) |
| low_latitude | 0.2 | 503 | 3.782 | Discovery incomplete (upstream errors/timeouts) |
| dense_plane | 0.05 | 503 | 5.813 | Discovery incomplete (upstream errors/timeouts) |
| dense_plane | 0.2 | 503 | 5.766 | Discovery incomplete (upstream errors/timeouts) |
| north_pole | 0.05 | 503 | 15.312 | Discovery incomplete (upstream errors/timeouts) |
| north_pole | 0.2 | 503 | 8.750 | Discovery incomplete (upstream errors/timeouts) |
| south_pole | 0.05 | 503 | 6.390 | Discovery incomplete (upstream errors/timeouts) |
| south_pole | 0.2 | 503 | 3.875 | Discovery incomplete (upstream errors/timeouts) |
| ra_zero_west | 0.05 | 503 | 67.391 | Discovery incomplete (upstream errors/timeouts) |
| ra_zero_west | 0.2 | 503 | 14.484 | Discovery incomplete (upstream errors/timeouts) |
| ra_zero_east | 0.05 | 503 | 26.875 | Discovery incomplete (upstream errors/timeouts) |
| ra_zero_east | 0.2 | 503 | 62.765 | Discovery incomplete (upstream errors/timeouts) |
| field_offset | 0.05 | 503 | 6.843 | Discovery incomplete (upstream errors/timeouts) |
| field_offset | 0.2 | 503 | 4.609 | Discovery incomplete (upstream errors/timeouts) |
| detector_edge | 0.05 | 503 | 120.047 | Shared deadline exhausted |
| detector_edge | 0.2 | 503 | 6.766 | Discovery incomplete (upstream errors/timeouts) |

The two simultaneous clients for `high_latitude`, FOV 0.05 degrees, both
received HTTP 503 in **85.906 seconds**, with the same incomplete-discovery
error. The worker process exited in 88.875 seconds. No cleanup timeout was
observed. The unit test establishes that same-key work executes once; these
live results establish only consistent bounded failure, not successful shared
retrieval. Across the matrix and paired test, **20/20 HTTP requests returned
503**; none returned synthetic data. No warm timing or difference-frame asset
acceptance could be measured.

One additional diagnostic used a **240-second backend budget**, a 270-second
process bound, and the same high-latitude 0.05-degree field. It returned HTTP
503 in **5.438 seconds**, with upstream HTTP 502 from both discovery paths.
The result is in `phase2-live-extended-budget.json`. Because failure occurred
before the extended deadline, it neither establishes nor disproves the benefit
of longer/background processing for successful archive responses. It does
establish that increasing the deadline alone did not resolve this failure.
No repeated matrix or further network retries were run.

```powershell
.venv311/Scripts/python.exe scripts/probe_live_coordinates.py --fields high_latitude --sizes .05 --sky-deadline 240 --case-timeout 270 --output docs/evidence/phase2/phase2-live-extended-budget.json
```

An independent real-input exercise is recorded in
`phase2-real-spectral-signature-unpadded.json`; the padded follow-up can be repeated with
`scripts/probe_spectral_signature.py`. It downloaded a 3,962,880-byte DR1 B6
cutout referenced by the WISE 0855 golden manifest in 9.343 seconds and evaluated
the actual WCS-WAVE (with SIP removed from the spectral WCS). Wavelengths of
the five covered samples ranged from 4.963335 to 4.971323 micrometers. Four
corner samples were outside this detector-aligned cutout: an upstream cutout
with the same width as a north-up field can clip corners when rotated. This
led to padding live cutout requests by `sqrt(2) * size + 2 * 6.15 / 3600` degrees;
the output/query FOV remains unchanged. A regression checks both the enlarged
fetch size and unchanged query size. This initial probe is not a successful
nine-sample comparison. The follow-up at both FOVs is recorded separately in
`phase2-real-spectral-signature.json`: padding recovered **9/9 finite samples**
for both the 0.05-degree field (fetch width 0.074127345 degrees, 3,974,400 bytes,
12.625 seconds) and the 0.2-degree field (fetch width 0.286259379 degrees,
4,400,640 bytes, 11.672 seconds). This validates the corner-coverage correction
on one real exposure, not a temporal pair. No FITS binary was committed.

The main matrix began before the final cutout-padding correction; later
subprocesses imported the updated code. Discovery failures do not depend on
this correction. Padded real-FITS verification is separate to avoid presenting
the mixed implementation timing as a uniform final acceptance run.

The synchronous production deadline is 120 seconds across discovery, downloads
and processing. Network waits are bounded; CPU deadline checks are cooperative
between processing stages, so an individual CPU stage is not forcibly killed
at the deadline. Singleflight shares work only within one server process.

If successful multi-epoch retrieval cannot fit this budget, the next design
should retain discovery and downloaded cutouts in persistent cache, run the
remaining work as a background job, and expose polling with progress and final
status. It needs bounded concurrency, cancellation, expiry/TTL, and a written
API schema proposal with contract review before implementation. Extending a
timeout alone does not establish interactive usability or scientific validity.
Background work addresses latency and retained progress; it cannot fix an
unavailable archive or guarantee comparable wavelengths. Intermittent HTTP 502
failures support bounded retries and retained progress, never relaxing the
spectral or completeness gates.

## Remaining scientific scope

Phase 2's sampled wavelength compatibility gate is deliberately bounded and
conservative. It is not calibrated spectral resampling, PSF matching, exhaustive
archive search, or proof that temporal differences are astrophysical. Full
background/masking/photometric validation and a scientifically revalidated
golden-cache rebuild remain in subsequent audit phases.
