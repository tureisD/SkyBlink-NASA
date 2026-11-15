# Reproduce a recorded analysis

> **Known-exposure acquisition (API 1.6, 2026-11-15):** explicit recovery uses
> a hash-identified historical metadata index, then downloads FITS inputs anew.
> The index bytes are part of source identity; discovery lineage records the
> original source analysis and bounded selection. This is distinct from
> offline replay, which intentionally uses exact retained input bytes. Do not
> describe either operation as a complete current archive search. See the
> [contract](../decisions/known-exposure-contract-decision.md) and
> [current verification](../verification/phase5-discovery-outage-verification.md). Earlier
> source-specific replay checkpoints below retain their historical meaning.
>
> The API 1.6 known-exposure Barnard record
> `sha256:6ac557e948a283957ce4a400bfabbab6b514c43fd59d4f1badd4820598bd096b`
> passed strict local replay with matching source, environment, input hashes,
> numerical results and generated assets. Its two retained exposures were
> downloaded fresh during acquisition. Replay is arithmetic/integrity evidence,
> not independent validation of astrophysical interpretation.

> **Runtime/source consistency repair (2026-11-15):** a stale development
> worker was found executing image method 11 while recording newer files from
> disk. Those diagnostic records are retained as mismatched-runtime evidence,
> not valid pinned-replay examples. The application now freezes source identity
> after imports and rejects changes before archive acquisition and before
> analysis-record creation. A source-change response requires an API restart;
> retrying the unchanged stale process cannot repair it. This guard does not
> certify historical records or simultaneous edits during initial imports.
> See [diagnosis and source policy](../research/catalog-acquisition-source-review.md)
> and [current verification](../verification/phase5-catalog-reliability-and-viewer.md).
>
> The corrected-server Barnard record
> `sha256:6ffb100428b17603a176670eb51110bf11eb5fb8a0cbb342a756d700937c0bd7`
> passes strict local replay: four retained inputs and all twelve generated
> image/difference/telemetry assets match, with matching source, environment
> and numerical outputs. Acquisition remains a fresh online operation; this
> replay deliberately uses the exact retained bytes.

> **Previous replay checkpoint (2026-11-15):** the method-12 Barnard comparison passed
> strict local replay: nine retained input hashes and all twelve generated
> asset hashes matched, with matching source/environment and numerical outputs.
> See [the current replay evidence](../verification/phase5-live-comparison-verification.md#regression-and-exact-replay).
> The method-11 and earlier bundles below are historical, source-specific
> examples. The existing photometry method now has restricted independent
> support; the proposed exact/SAPM refinement remains unadopted. Neither replay
> nor those controls establish all-sky validity. See
> [remaining limitations](../current-limitations-and-next-steps.md).

> **Current continuation:** Current API 1.5 uses fresh upstream acquisition by default; pinned replay remains a separate operation. Current records and independent reacquisition/replay results are linked from the continuation report. The API 1.4 bundles below retain their original source and are historical evidence. [Details](../verification/phase4-online-verification.md).

SkyBlink now has a pinned numerical replay path. It verifies the exact real input
bytes, source files and recorded environment before repeating image processing
or native spectral extraction. This is narrower than proving that a residual is
astrophysical. Scientific promotion remains blocked; see
[Phase 4 verification](../verification/phase4-verification.md) and [the science report](../verification/phase4-science-verification.md).

The analysis format is [documented separately](../reference/phase4-replay-schema.md).
The [worked examples](phase4-evidence-walkthrough.md) explain the actual numbers,
and [result meaning](result-meaning.md) defines units, methods and reason codes.

## Obtain the exact materials

For the current online continuation, start with
[the source-specific records](../evidence/phase4/records) and
[independent results](../evidence/phase4/phase4-online-independent-replay.json). The final NGP
image record uses image method 11 and content-addressed output names. WISE and
R Draconis records precede that publication correction and must use their own
frozen source. Do not mix these environments or claim a drift override is a
strict replay.

From a checkout matching the NGP record's source hashes, with the recorded
Python/package/platform environment, the upstream-input route is:

```powershell
python scripts/replay_analysis.py acquire --record docs/evidence/phase4/records/north_galactic_pole-sky.json --store .replay-ngp-inputs --timeout 600
python scripts/replay_analysis.py replay --record docs/evidence/phase4/records/north_galactic_pole-sky.json --store .replay-ngp-inputs --output .replay-ngp-output
```

Use a new store to demonstrate independent acquisition and a new output directory
for each replay. A retry of `acquire` verifies already retained inputs and tries
the exact remaining URLs. Changed bytes fail; no substitute observation is
allowed. The independent check encountered transient HTTP 503s before complete
reacquisition, although four independently fetched inputs matched. Availability
is separate from repeatable arithmetic. For guaranteed input retention, export
and distribute the approved bundle rather than promising the archive is always
reachable. Bundles record their pinned requirements and source; strict replay
currently checks the recorded operating system/architecture too.

Current local bundles are `backend/.cache/phase4/online-replay-bundle/` (WISE),
`online-null-replay-bundle/` (R Draconis) and
`online-publication-replay-bundle/` (final NGP image). They are not public download
links. The paths and commands below describe the earlier API 1.4 bundle.

Checked-in file inventories are available for the
[WISE bundle](../evidence/phase4/phase4-online-replay-bundle-index.json),
[null bundle](../evidence/phase4/phase4-online-null-replay-bundle-index.json), and
[final publication bundle](../evidence/phase4/phase4-online-publication-replay-bundle-index.json).
An inventory is not a substitute for distributing its actual payload files.

The local curated export is retained outside Git at
`backend/.cache/phase4/replay-bundle/`. The bundle includes:

- `bundle.json`: record IDs, every payload file's SHA-256 and size, total bytes.
- `records/`: immutable scientific records, including exact upstream cutout URLs.
- `inputs/sha256/`: the real input bytes, addressed by their content hash.
- `source/`: the exact relevant implementation, including uncommitted source.
- `requirements-frozen.txt`, `environment.json`, `REPLAY.txt`: resolved package
  versions, runtime/platform identity and replay instructions.

The corresponding real null-spectrum export is
`backend/.cache/phase4/null-replay-bundle/` (142,693,784 payload bytes).
It follows the same procedure and retains the 34 exact corrected-position
R Draconis inputs. Tracked indices for the [finite/image bundle](../evidence/phase4/phase4-curated-bundle-index.json)
and [null bundle](../evidence/phase4/phase4-null-bundle-index.json) record all payload hashes and
sizes. The first bundle is 9,447,256 payload bytes. Neither index includes raw
observations in Git.

**Access and retention:** this is a local, unpublished bundle. A maintainer must
provide the directory to another reviewer; a repository clone alone does not
contain it. Keep it intact through review and submission, and copy it to a
managed release location before promising judge access or long-term availability.
There is no public hosting URL, automatic backup or retention SLA. The tracked
verification report identifies the exported bundle and its measured size.
Archive acquisition is a recovery path, not a guarantee that upstream bytes will
remain available forever.

For existing revision-3 saved products, only artifact/input evidence recorded at
that time is available. They do not retroactively acquire these new analysis
records. Their unchanged hashes do not constitute complete processing replay.

## Clean-environment replay

Use the Python version, operating-system family and architecture recorded in
`environment.json`. Run the following from the supplied bundle directory on
Windows; replace `RECORD_ID` with a full digest from `bundle.json`.

```powershell
py -3.11 -m venv replay-env
.\replay-env\Scripts\python.exe -m pip install -r requirements-frozen.txt
.\replay-env\Scripts\python.exe source/scripts/replay_analysis.py verify --record records/RECORD_ID.json --store inputs
.\replay-env\Scripts\python.exe source/scripts/replay_analysis.py replay --record records/RECORD_ID.json --store inputs --output results/RECORD_ID
```

Package installation may use the network. The `replay` operation does not query
the observation archive. It uses only the supplied content-addressed store and
writes to a new output directory. An existing output or an output inside approved
assets/input storage is rejected. Do not add drift overrides to a run described
as a strict replay.

Inspect `results/RECORD_ID/replay-report.json`. A strict pass requires verified
input hashes, matching processing source and environment, and matching numerical
results. Native channel floats use the predefined `rtol=1e-10, atol=1e-10`; nulls,
eligibility, flags and methods must agree. This tolerance checks repeated
arithmetic; it is not claimed instrumental precision. Image science arrays and
normalization use exact hashes in the recorded environment. Encoded asset hashes
are reported separately so a rendering difference cannot be hidden as a scientific
agreement. Image replay repeats the pinned selection and checks its dense
wavelength gate; it does not claim to reproduce a later archive discovery query.

The source digest covers relevant tracked and untracked files. Git commit and
dirty-state information provide context, but a commit alone cannot identify an
uncommitted implementation. A supplied source snapshot can pass without `.git`
when its file-content digest matches. Package pins do not archive Python, binary
wheels or the operating system; cross-platform numerical reproducibility remains
a separate, unverified scope.

## Missing or changed inputs

To explicitly acquire missing inputs from the exact recorded upstream URLs:

```powershell
.\replay-env\Scripts\python.exe source/scripts/replay_analysis.py acquire --record records/RECORD_ID.json --store inputs --timeout 120
```

Acquisition is bounded and restricted to supported HTTPS IRSA product/calibration
locations. A different hash, corrupt retained file, timeout or unavailable product
fails explicitly. Do not substitute a nearby exposure or change the record's
expected hash to make a historical replay pass. To analyze different data, create
a new analysis record with a different identity.

Only product creation time is returned as `provenance.generated_at`; subsequent
requests do not reset it. Retrieval timestamps are separate and may be unknown
for previously cached bytes. Observation time comes from the exposure metadata.
An unavailable historical timestamp is not reconstructed from file modification
time. Public lineage links name the analysis fingerprint; an internal current
alias may change, so save the immutable record when exporting evidence.

## Create a new export or staged build

With the recorded source and environment active in the repository:

```powershell
.\.venv311\Scripts\python.exe scripts/bundle_analysis.py --record PATH_TO_IMAGE_RECORD --record PATH_TO_SPECTRUM_RECORD --store PATH_TO_INPUT_STORE --output NEW_BUNDLE_DIRECTORY
```

The exporter rejects an existing destination, changed source/environment or
missing/corrupt inputs. It copies package names and versions, not credential-bearing
environment variables or package download URLs. A bundle is a local export, not
an automatic publication or promotion.

For corrected catalog staging, use `scripts/stage_phase4.py`; the full procedure
and bounds are in [the staging section](../reference/phase4-replay-schema.md#separate-phase-4-staging).
The current stage searches only the recorded historical image-URI inventory.
Its reference overlays are deliberately absent pending a real rebuild in the
corrected WCS. `promotion_eligible` remains false even if a stage builds products.

The local live input store is `backend/.cache/analysis-inputs`; isolated stages
use their own `cache/analysis-inputs`. Per-record retention/acquisition is bounded
to 128 MiB per input and 8 GiB total. There is no automatic global quota or expiry
worker yet. Operators must manage storage and export important records before
removing a cache. Removed inputs lead to explicit missing-input errors; immutable
IDs and URL names are not promises of permanent storage.

## What this settles, and what it does not

The supported replay cases can establish that another environment repeats the
recorded calculations and preserves missing measurements. That addresses hidden
input/source state for those cases. It does not settle control-star stability,
all-five scientific acceptance, archive completeness, public artifact availability,
or whether a new user can correctly interpret the results. Those are separately
recorded gates; Phase 5 must test comprehension and navigation with people.
