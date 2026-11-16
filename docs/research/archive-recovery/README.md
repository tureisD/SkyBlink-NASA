# Reproduce the discovery incident

This folder contains a standard-library-only Python diagnostic. It makes seven
read-only requests, sequentially, without retries. It does not create async jobs
or alter SkyBlink. Output directories must be new so earlier failures survive.

From the repository root, run on each machine close in time:

```text
python docs/research/archive-recovery/probe.py --out archive-probe-network-a --timeout 20
```

Use `archive-probe-network-b` on the second machine. An exit code of 1 means at
least one minimal science query did not return a successful VOTable with rows;
the receipts explain whether it was an HTTP error, timeout or other result.
This diagnostic deliberately does not certify discovery completeness or images.
Responses are capped at 1 MiB; timeouts are socket-operation limits, not a hard
total wall-clock cap. Proxy values and credentials are not recorded.

Compare exact URLs, UTC request times, resolved addresses, HTTP status, response
hashes and XML query statuses. Different clients sharing the same network do not
provide the independent egress test. Send both receipt directories to the
maintainer; the [prepared IRSA incident](../../verification/irsa-incident-draft-2026-11-15.md)
contains the existing findings. It has not been sent.

The [execution report](../../verification/archive-recovery-execution-2026-11-15.md)
records the local result and the bounded cloud-index feasibility experiment.

## Bounded async diagnostic

`async_probe.py` uses the existing `httpx` dependency to create one minimal TAP
job and observe its phase for up to three minutes. It records responses and
attempts abort/deletion on exit. Cleanup is verified only by a subsequent
404/410; an accepted deletion request alone is insufficient. Request and cleanup
timeouts can extend wall time beyond the polling budget. It is not an application
transport and does not repair a service returning 502 at job creation.

```text
.venv311/Scripts/python.exe docs/research/archive-recovery/async_probe.py --out backend/.cache/archive-async-new --seconds 180
```

## Independent metadata-index prototype

`cloud_index_probe.py` is research code using existing Astropy, NumPy and httpx
dependencies. It enumerates exactly one public DR1/QR3 detector directory, with
a maximum of 2,500 objects, four list pages, six workers and three range lengths
per object. Defaults are 2,000 objects and four workers. These are work caps,
not a hard wall-clock deadline. It does not retry failed headers.

Range responses must match the listing's ETag and object length. The reader
recognizes empty PRIMARY and named IMAGE headers, increasing the range length
when necessary. Only the padded IMAGE header is retained, never science pixels.
Changed objects, unsupported layouts, invalid UTC bounds and failed WCS checks
remain failures and prevent a complete-directory claim. Wide/deep collection
membership is unknown, not inferred from the path. A listing plus sequential
reads is an acquisition interval, not an atomic view of a changing bucket.

```text
.venv311/Scripts/python.exe docs/research/archive-recovery/cloud_index_probe.py build --prefix qr3/level2/2026W40_2A/l2b-v27-2026-285/1/ --out backend/.cache/archive-index-prototype/qr3-d1-new --workers 4
.venv311/Scripts/python.exe docs/research/archive-recovery/cloud_index_probe.py query --snapshot backend/.cache/archive-index-prototype/qr3-d1-new/snapshot.json --ra 133.76021647484097 --dec -7.242224282436729 --out backend/.cache/archive-index-prototype/wise-query.json
```

Coordinate queries verify retained-header hashes, use the full spatial TAN-SIP
inverse transform, require a forward round trip, and test image-center
containment. They do not establish full-field coverage, spectral compatibility,
usable pixels, photometry or a temporal pair. Search errors remain explicit.
`all_archive_complete` is always false: a miss in this research subset never
means the archive contains no data. The immutable runtime known-exposure index
is neither read for exposure selection nor modified by these tools.

Snapshots, partial checkpoints and real headers stay in `backend/.cache`, outside
runtime asset roots and Docker packaging. No application adapter loads them.
Promoting this prototype requires the source/provenance and coverage decisions
in the [recovery plan](../../plans/archive-recovery-plan-2026-11-15.md), broader
verification, resumable ingestion, storage planning and update handling.

`cloud_search_probe.py` adds a conservative spatial prefilter. Absolute SIP
polynomial coefficients bound the distorted pixel rectangle; the CD matrix and
TAN projection turn this into a spherical cone. Unsupported WCS is always kept
as a candidate. Accepted candidates still require the original inverse-WCS
test. The build checks nine forward-transformed positions in every image;
verification compares exact result sets against all seven exhaustive searches.

```text
.venv311/Scripts/python.exe docs/research/archive-recovery/cloud_search_probe.py build --snapshot backend/.cache/archive-index-prototype/qr3-d1/snapshot.json --out backend/.cache/archive-index-prototype/qr3-d1/search-index.json
.venv311/Scripts/python.exe docs/research/archive-recovery/cloud_search_probe.py verify --snapshot backend/.cache/archive-index-prototype/qr3-d1/snapshot.json --index backend/.cache/archive-index-prototype/qr3-d1/search-index.json --out backend/.cache/archive-index-prototype/qr3-d1/search-validation.json
.venv311/Scripts/python.exe docs/research/archive-recovery/verify_cloud_probe.py --snapshot backend/.cache/archive-index-prototype/qr3-d1/snapshot.json --header-samples docs/evidence/phase6/archive-execution-20261115 --out backend/.cache/archive-index-prototype/qr3-d1/header-validation.json
```

The verifier uses six real retained detector headers and coordinate controls:
interior/corner points, points beyond each edge, equivalent RA values, an
antipodal position and truncated header bytes. These are diagnostic inputs;
no generated observation arrays or product fixtures are introduced.
