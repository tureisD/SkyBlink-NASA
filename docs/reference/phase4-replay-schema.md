# Scientific records and offline replay

This describes the internal `skyblink.analysis/1` record implemented by
`backend/services/provenance.py` and `scripts/replay_analysis.py`. It is distinct
from the public API contract. A successful replay establishes numerical
reproducibility in its recorded environment, **not scientific validity**.
Independent calibration, astrometry and static-control gates still apply.

## Identity and time

The envelope contains `schema_version`, `analysis_id`, `identity`, `created_at`
and `retrieved_at`. `analysis_id` is `sha256:` followed by the SHA-256 digest of
the canonical JSON object containing `schema_version` and `identity`.

Canonical JSON is UTF-8 with sorted string keys, compact separators and no
ASCII escaping. Only JSON dictionaries, lists, strings, booleans, integers,
finite floats and explicit nulls are accepted. Nonfinite numbers, numpy scalar
types, duplicate parsed keys and implicit stringification are errors. Callers
must explain unavailable measurements and explicitly use null. This format is
defined for the supported Python replay path; it does not claim RFC 8785
cross-language numeric canonicalization.

Creation and retrieval times are envelope metadata and do not change the
scientific identity. Retrieval is `null` when the original archive fetch time
is unknown, including bytes recovered from an older cache. Retaining or
accessing a file now does not retroactively establish its retrieval date.
Observation times/ranges belong in the exposure metadata and do affect the
identity. Response time is not part of this record. A rebuilt record's
`created_at` is its creation time; an existing product retains its original
creation time when served again.

Everything under `identity` contributes to the fingerprint, including expected
outputs, extraction positions, eligibility, source URLs, code and environment.
Do not place transient build/response timestamps or absolute local paths there.
The identity must not include the analysis record's own hash as an output:
that would be circular. Derived image bytes may differ between encoder
environments even when scientific quantities reproduce.

## Record fields

| Identity field | Meaning |
|---|---|
| `kind` | `spectrum` for native extraction; `image` for recorded-selection image replay |
| `query` | Supplied/canonical ICRS coordinates, crop and target astrometric assumptions supplied by the builder |
| `inputs` | Deduplicated content index: `sha256`, `size_bytes`, `source_url`, `cutout`, `store_key`; additional explicit release/version metadata is allowed |
| `exposures` | Per-exposure `input_sha256`, `epoch_id`, `detector`, `extraction: {ra, dec}`; observation/WCS/selection/background metadata supplied by builder |
| `method` | Pinned algorithm, masks, configuration and processing versions; spectrum uses `native_method()` exactly |
| `selection` | Actual discovered/considered/selected/rejected observations, completeness, search bounds and failures, as recorded by builder |
| `outputs` | Expected numerical diagnostics and asset hashes, excluding this record itself |
| `code` | Commit, scoped dirty status, per-source-file hashes and aggregate source content digest |
| `environment` | Python implementation/version, OS family/architecture, explicit package-version whitelist, WCSLIB and WebP versions |

Spectrum exposures must additionally contain `expected_channel`, including
explicit null when no channel could be extracted. Channels are associated with
their exposure index rather than joined by wavelength. They may contain extra
diagnostics, but the comparator checks the supported numerical fields,
measurement flags, eligibility, method labels and reason codes. Input storage
does not manufacture missing channels or observation epochs.

The schema is intentionally an extensible internal envelope. Its validator
checks structural/security requirements and the fingerprint. It does not
certify the truth or completeness of a caller's provenance statements. Builders
must populate the selection, source version, observation and WCS context from
actual processing. Missing historical evidence stays unknown.

## Capturing a record

Use these APIs from the backend, with no discovery inside replay:

```python
from services.provenance import store_input, make_record, native_method, write_record

descriptor = store_input(
    actual_fits_bytes, content_store,
    source_url=actual_cutout_url,
    cutout={"ra": requested_ra, "dec": requested_dec, "size_deg": fetched_size},
    retrieved_at=None,  # unknown unless the actual fetch time was recorded
)
analysis = make_record(
    kind="spectrum", query=query_metadata, inputs=[descriptor],
    exposures=[{
        "input_sha256": descriptor["sha256"], "epoch_id": epoch_id,
        "detector": detector, "extraction": {"ra": extraction_ra, "dec": extraction_dec},
        "expected_channel": extracted_channel,
    }], method=native_method(), selection=selection_metadata,
)
write_record(record_path, analysis)
```

Capture all considered/downloaded bytes required for the claimed replay scope,
including rejected candidates if selection is replayed. Deduplicate identical
content in `inputs`; multiple exposures can reference one retained object.
The content store layout is `sha256/<first-two-hex>/<64-hex-digest>.bin`.
The suffix is deliberately opaque; these are exact FITS bytes, not encoded or
reconstructed observations. Local absolute file paths are not exported.

Source identity includes relevant Python files under backend core/services/
models/routers/app, including untracked source, plus requirements, the replay
and cache-build scripts and Dockerfile. It excludes `.env`, virtual
environments, caches and tests. Commit identity alone never stands in for dirty
source content. This is a scoped source digest, not an archive of the entire
repository. Keep the matching source revision/patch available separately.
The staging script and `backend/core/staged_astrometry.json` are also hashed,
so the corrected astrometric profile cannot change without changing code identity.
The curated-replay and bundle-export scripts are included in this source scope.

## Verification and acquisition

From the repository root (replace paths with the real record/store locations):

```powershell
.\.venv311\Scripts\python.exe scripts/replay_analysis.py verify --record analysis.json --store retained-inputs
.\.venv311\Scripts\python.exe scripts/replay_analysis.py acquire --record analysis.json --store retained-inputs --timeout 120
.\.venv311\Scripts\python.exe scripts/replay_analysis.py replay --record analysis.json --store retained-inputs --output replay-new
```

`verify` checks the record fingerprint and exact input sizes/hashes.
`acquire` downloads only missing pinned objects and checks their bytes before
atomic publication. It never reruns discovery, substitutes a newer file or
silently repairs a corrupt existing object. Corruption fails with the affected
hash; remove/quarantine it explicitly before retrying acquisition. Changed
archive output fails even when its URL is unchanged.

Network acquisition permits only HTTPS IRSA DR1/QR3 and SPHEREx calibration
product paths, with no credentials, redirects, traversal or local-file URLs.
The official `nasa-irsa-spherex.s3.us-east-1.amazonaws.com` host is additionally
allowed only for DR1/QR3 `spectral_wcs` calibration products.
TLS verification stays enabled and ambient proxy/credential environment is
not used. The record is validated before networking. Limits are 128 MiB per
object, 8 GiB total pinned bytes, 10,000 descriptors/exposures and 32 MiB JSON.
Acquisition uses a total elapsed-time check plus finite socket timeouts; a
blocked read can finish after the deadline by at most its current socket
timeout (at most 30 seconds). This is a bounded synchronous command, not a hard
wall-clock process kill. Records needing other catalog hosts require an
explicit reviewed acquisition extension; arbitrary URLs are not followed.

## Replay and comparison

Replay is offline. It reads the pinned bytes, uses the recorded extraction
coordinates and native aperture method, and writes `channels.json` plus
`replay-report.json` into a **new** directory. It refuses existing output
directories and any output beneath the approved golden cache or input store.
It never changes the golden cache. Image records use the explicit
`spherex_pipeline.replay_image_record(record, inputs_by_sha256, output_dir)`
adapter. Without that adapter they are input-verifiable only; successful
rendering alone does not constitute a numerical match. The adapter must return
an explicit `numerical_match` boolean with its comparison evidence.

Native replay uses predeclared `rtol=1e-10`, `atol=1e-10` on finite wavelength,
bandwidth, flux, flux error, clean fraction and aperture-radius values. The
absolute tolerance uses each field's stored units. These tight tolerances are
for rerunning deterministic native extraction in the same implementation,
not a claim about observational precision or calibration accuracy. Nulls,
integers, boolean eligibility, reason lists, field presence and method labels
are exact. Extraction coordinates, method and masks are pinned in the
fingerprint; changing them creates a different record. Extra internal channel
diagnostics do not suppress public-field differences.

By default replay requires the recorded source content digest and full recorded
environment to match. `--allow-code-drift` and `--allow-environment-drift` allow
an explicitly labeled comparison run; drift prevents `verified: true` even if
numbers match. Exit 0 means the requested verification passed; exit 1 means a
completed numerical/strict comparison did not pass; exit 2 means invalid,
unavailable or unsafe inputs prevented execution. Input-only verification is
always labeled as such. A matching replay is not an independent scientific
validation and does not resolve failed static-control or calibration gates.

For an equivalent frozen environment, install the exact versions listed in
`identity.environment.packages`, using the same Python/platform and native
libraries. The broad application requirements are not a replay lock. The
record captures the actually used relevant versions; it is not a complete
portable operating-system or binary archive. Clean-environment reproduction
by someone other than the implementer remains a separate acceptance gate.

## Retention and measured coverage

The code provides a portable content-addressed bundle and acquisition command;
it does **not** establish an externally hosted retained bundle or a retention
SLA. A curated release must publish its actual store manifest, total size,
access location, source revision and retention conditions. Until that exists,
do not claim independent permanent offline reproducibility. Arbitrary live
records whose objects have expired fail as missing inputs and may reacquire
only hash-identical bytes.

`backend/tests/test_provenance.py` inventories its own isolated generated
byte/JSON boundary cases; these are not observations and never ship as product
data. Its real integration cases use retained Phase 3 WISE 0855 and R Draconis
FITS inputs, asserting the source hashes before native extraction. If those
inputs are absent, tests skip explicitly rather than generate replacements.
The R Draconis case checks that null flux remains null. These are implementer
regressions in the current environment, not the independent replay acceptance
required for cache promotion.

## Separate Phase 4 staging

`scripts/stage_phase4.py` runs the production processing functions through an
explicit pinned-archive adapter. It reads the five reviewed corrected profiles
without changing production targets. Its initial inventory is the actual
`artifact_uris` from the old real golden manifests. That is a **partial
historical image-contributor inventory**, not an exhaustive archive query or
the complete old spectrum selection. Every record/report identifies this limit.

```powershell
.\.venv311\Scripts\python.exe scripts/stage_phase4.py --output backend/.cache/phase4/stage-new --target all
```

By default all distinct recorded URIs are attempted. `--max-inputs N` applies
an explicit, evenly spaced manifest-order sampling bound; a bounded probe is
diagnostic, not complete release acceptance. `--deadline`, `--request-timeout`
and `--workers` bound acquisition. The default is 900 seconds per target,
30-second requests and four workers. Each target's successes, metadata failures,
missing requests and resource limits are recorded in `stage-report.json`.

The downloader uses URL-only locators until actual FITS `IMAGE` headers provide
`MJD-BEG`, `MJD-END`, `TIMESYS=UTC`, `DETECTOR` and the observation ID. No
observation date is inferred from a filename or historical mean epoch. Images
use the production padded field; spectra request their own exact cutout size.
Phase 3 cached bytes are reused only when the serialized archive cutout URL
matches and their recorded SHA-256/size verify. Corrected query coordinates
normally require new downloads.

Outputs are under the new stage's `golden/<target_id>`; exact retained inputs
are under `cache/analysis-inputs`. `--input-stage PREVIOUS_STAGE` reuses only
matching-URL, hash-verified content from a previous stage and may be repeated.
An interrupted stage can recover an object only when its exact URL-derived
cache key and matching content-addressed object both exist. `--offline` never
downloads absent objects. After the implementation is frozen, rerun with a new
output and the retained prior stage to obtain current code fingerprints:

```powershell
.\.venv311\Scripts\python.exe scripts/stage_phase4.py --output backend/.cache/phase4/stage-frozen --target all --input-stage backend/.cache/phase4/stage-new --offline
```

If some inputs were not retained, that remains an explicit failure/partial
inventory. The script does not fabricate missing epochs, relax compatibility
gates or replace insufficient measurements with values. It omits old reference
overlays because the corrected WCS needs separately regenerated references.
`all_products_built` describes execution only; `promotion_eligible` remains
false. A completed stage is never automatically copied to the approved cache.
Independent replay, scientific acceptance and migration/rollback review remain
separate gates.

## Curated shared-input comparison

`scripts/curate_phase4_replay.py --output NEW_DIRECTORY` builds the two real
Phase 3 Epsilon Indi D3 inputs entirely offline after checking their recorded
hashes and actual FITS observation headers. It preserves the original fixed
audit query and a 0.2-degree comparison field; it does not pretend these are
new cutouts at the corrected catalog position. The image comparison is
visualization-compatible. No passing independent variability/control claim is
attached to this example.

The accompanying native spectrum uses the **same retained padded FITS bytes**
and fixed query, with `target=None`; it does not substitute those padded bytes
for a request claiming a smaller cutout. The native algorithm remains the
recorded aperture/background extraction. Its selection metadata explicitly
states the padded-input policy and links the image analysis ID. A
`curated-summary.json` gives both record paths, their shared hashes and the
content-store path. Replay both records with the command above. Retain a real
unusable/null case separately; a usable-looking comparison is not evidence
that the independent scientific gates passed.

`scripts/bundle_analysis.py` can export matching records, verified inputs,
source files and a frozen dependency manifest into a new local bundle. This
does not publish the bundle or establish external retention/access. Its own
verification must pass before declaring the exported files a replay bundle.
