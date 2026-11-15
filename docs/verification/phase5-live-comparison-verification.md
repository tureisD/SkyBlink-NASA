# Live comparison retrieval verification

Recorded 2026-11-15 UTC. API remains **1.5.0**; the image/cache method is
**12**. The machine-readable evidence is
[phase5-live-comparison-results.json](../evidence/phase5/phase5-live-comparison-results.json).

## Result

The final fixed first pass returned matched visual comparisons for **five of six
fields**, including four of the five named quick-test targets. Epsilon Indi
returned one actual epoch because DR1 discovery failed upstream. One subsequent
request with exactly the same coordinates, source and field size returned its
matched comparison. Every named target and the north Galactic pole therefore
has a successful final-source comparison, but the first-pass limitation must
not be erased or described as six uninterrupted successes.

All requests used `source=archive`, corrected catalog coordinates for named
targets, the supplied position for the north Galactic pole, and **0.2 degrees**.
They were made sequentially through the real HTTP API at local port 8185.
The server retained its **120-second budget**. Final requests ran with logs
redirected to disk and without concurrent tests or replay processing.

| Field | Final first pass | Seconds | Retained inputs | Comparison rounds | Common detector bands |
|---|---|---:|---:|---:|---|
| Barnard's Star | HTTP 200, matched visual | 71.235 | 9 | 3 | 6 |
| RW Aurigae | HTTP 200, matched visual | 52.141 | 7 | 2 | 1 |
| Epsilon Indi B | HTTP 200, single epoch, partial discovery | 32.781 | 4 | 0 | No comparison |
| WISE 0855 | HTTP 200, matched visual | 52.547 | 4 | 1 | 3, 6 |
| R Draconis | HTTP 200, matched visual | 66.250 | 6 | 2 | 3, 6 |
| North Galactic pole | HTTP 200, matched visual | 46.250 | 3 | 1 | 3 |
| Epsilon Indi B, identical retry | HTTP 200, matched visual | 44.156 | 4 | 1 | 5 |

Epsilon Indi's first pass received HTTP 502 from `spherex_dr1` and both deep
collections. Only QR3 succeeded, supplying 120 records in `2026_E1`. The
response correctly retained `discovery_status=partial`, all three missing
collections, one epoch and no difference. This was a discovery outage, not a
wavelength-gate rejection. The retry reported complete discovery and compared
the actual 2025-10-06 and 2026-10-01 observations in detector 5.

Across the six final requests and the retry, all **37 retained input entries**
have verified content hashes and fresh acquisition receipts with
`from_cache=false`. These are entries across requests, not a claim of 37
distinct exposures. Application input/product caches were bypassed; the app
cannot guarantee that IRSA or an intervening proxy did not cache a response.
All **68 served image requests** for epoch and difference assets returned HTTP
200 and bytes matching their immutable filename hashes. Failed downloads and
missing inputs remain recorded; they were not filled from older saved data.

## Diagnosis and change

The previous path sampled visits independently within each detector and epoch,
then submitted an epoch-major batch of up to 54 padded cutouts. A bounded
download failure could leave observations from only one side of a comparison.
Even successful downloads could have poorly matched detector positions and
therefore incompatible wavelengths. SIA already supplied detector footprints,
but `ArtifactRecord` discarded them.

The new path retains the original SIA `s_region` internally. It ranks
cross-epoch, same-detector pairs before downloading:

1. Recorded polygon corners retain their original order and detector
   orientation. Unit-vector coordinates handle RA wrap and poles.
2. A nearest-neighbor search shortlists up to eight opposite-epoch neighbors
   per exposure, then ranks those candidates by mean corresponding-corner
   separation. This is an approximate acquisition heuristic, not a claim to
   find the globally best pair. At most four geometric proposals per
   detector/epoch pair and 24 proposals overall are retained. Missing-footprint
   candidates have reserved fallback opportunities using the existing bounded
   time sample.
3. Each round downloads both sides of two proposed pairs, at most four new
   inputs. Completed inputs remain available within the same request, and
   missing inputs can receive a bounded second acquisition attempt. Each round
   has at most 18 seconds within the remaining overall search allocation.
4. Each completed round is tested immediately. The search stops when a usable
   pair passes, before acquiring unrelated bands. Search allocation reserves
   25% of the remaining total budget for final processing/publication.

The existing `candidate_visits_per_band` metadata describes the bounded time
sample used when footprints are missing. Actual attempted records, proposed
pair ranks and round outcomes are retained separately in `live_acquisition`
inside the analysis record; footprint ranking can inspect records beyond that
time sample. Download receipts accumulate across rounds. Late workers cannot
change a published receipt snapshot.

**Acceptance gates were not relaxed.** Geometry only orders acquisition. The
measured spectral WCS still must pass the coarse screen and the dense test over
every retained output pixel: center difference at most one quarter of the
narrower bandwidth and bandwidth ratio at least 0.8. At 0.2 degrees the dense
gate covers 54,756 output pixels. The existing usable-image, masking,
background, common-band and 30-day within-epoch composition rules remain.
Spectral SIP is cleared. No photometry method, calibration threshold or flux
value was changed by this retrieval repair.

SIA's `em_min`/`em_max` describe the detector-wide bandpass, not the wavelength
at the requested position, and are not used to accept a pair. Wavelengths
depend on detector position; see the official
[SPHEREx data products documentation](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/)
and [IRSA SIA interface](https://irsa.ipac.caltech.edu/ibe/sia.html).

The bounded nearest-neighbor implementation was compared with the first
implementation's exhaustive corner ranking using the **actual retained
discovery inventories for all six fields**. All 24 ordered pairs were identical
in each case. Inventories ranged from 258 to 2,493 records; bounded ranking took
0.047–0.375 seconds in that check. This measured agreement does not establish
identical rankings for arbitrary future inventories.

## Failures retained

The initial implementation run returned matched comparisons for Barnard,
RW Aurigae, Epsilon Indi, R Draconis and the north Galactic pole. WISE 0855
returned HTTP 503 after **128.094 seconds**, with a server-budget error. That
response remains in the evidence JSON, including SHA256
`0a6bd1261a8af7f13075f924a35391a447638c881198a2c989d0108c0ea93fd4`.

The initial harness accumulated large amounts of Astropy logging in an
undrained server-output pipe and also overlapped some tests/replay with requests.
Output backpressure is a suspected contributor, not proven sole causality.
Final requests corrected these harness conditions. Synchronous scientific
processing checks deadlines at operation boundaries, so the configured budget
is not a hard wall-clock preemption guarantee. The timeout message now tells
users to retry the request rather than suggesting a catalog target when the
failed request already names one.

Transient upstream HTTP 502/503 errors also occurred in final acquisition.
Barnard required three rounds and RW/R Draconis required two. These failures,
the partial first Epsilon Indi result, and the separate successful retry remain
visible. This work does not guarantee every archive request will succeed.

## Regression and exact replay

The full backend suite passed **281 tests** on the final runtime source.
The focused ranking file passed **eight tests**, including three boundary tests
added after that full-suite collection. Checks cover paired acquisition and
second-round rescue, discovery-order-independent tie handling, deadline checks,
RA-wrap geometry, missing-footprint fallback, and rejection of incompatible
measured wavelengths even when footprints are identical. Generated protocol
inputs stay isolated in tests and are not observation products.

The final runtime source digest is:

```text
0dc7ab56c70eb76b093a811fd54e6758010cacb93b5a92f000d0693efcc5536f
```

Every final first-pass record and the Epsilon Indi retry carries that digest.
The final Barnard record replayed offline with matching source/environment,
all nine retained input hashes verified, exact scientific-plane and flag
hashes, and all **12 image/difference/telemetry asset hashes** reproduced.
No code/environment-drift override was used.

```text
Analysis: sha256:712536c8f71daa3535f646ae41363b9db0cddb437ca425ff737ca79e77261daa
Replay report SHA256: 0d64f5c48ee818132c3024f39962f9368af6b1df864682b3eab44172110c2b03
```

The JSON records the exact replay command, record/response hashes, retained
input URLs and cutout parameters, acquisition times, failed attempts, output
checks and local evidence paths. Raw inputs and replay products remain under
ignored `backend/.cache/phase5/comparison-first/`; this is local validation
evidence, not a newly published permanent archive or a promoted saved dataset.
The five golden revision-3 datasets remain unchanged.

`matched_visual` establishes a real, wavelength-compatible field comparison
under the recorded gates. It does not certify a target detection, usable target
photometry, calibrated variability, or all-sky scientific validity. Replaying
arithmetic and assets does not establish those interpretations either.
