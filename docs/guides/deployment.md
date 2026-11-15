# Local release and deployment guide

API 1.6.0, updated 2026-11-15. Publishing, public-host verification and submission are explicitly deferred. Old API 1.2 container size, memory and timing measurements do not certify this package. See [Phase 6 verification](../verification/phase6-verification.md) for completed and open gates.

## One origin, explicit sources

`scripts/serve.py` serves the built frontend at `/` and FastAPI at `/api/v1/`:

```sh
npm --prefix frontend ci
npm --prefix frontend run build
python -m pip install -r backend/requirements.txt
python scripts/verify_real_data.py --require-dist
python scripts/serve.py
```

Use Python 3.11 and Node 24. The listener defaults to `0.0.0.0:8000`; set `HOST=127.0.0.1` for local-only verification and change `PORT` when the development API occupies 8000. This production wrapper does not reload code. Restart after processing-source changes; `PROCESSING_SOURCE_CHANGED` refuses new work until then.

- `source=archive&discovery=live` is the default and needs current IRSA discovery and FITS acquisition. Failure never switches source automatically.
- `source=archive&discovery=known` explicitly uses a bounded verified exposure list for the five catalog targets. It downloads fresh FITS and reruns quality checks, but cannot discover newer observations or support arbitrary coordinates.
- `source=saved` explicitly serves the unchanged revision-3 historical real datasets without archive acquisition. Use coordinates from `/api/v1/targets?source=saved`; corrected archive positions come from `/api/v1/targets?source=archive`.

The spectrum can explicitly use known acquisition while the image retains its existing mode. Finite excluded samples and zero eligible measurements are valid successful results, distinct from retrieval failures.

## Container and storage

```sh
docker build -t skyblink:local .
docker compose up -d
```

The runtime uses UID/GID `10001:10001`, writable `/data/cache` and a 2 GiB memory limit. A new named volume inherits image directory ownership. Existing volumes or bind mounts may be root-owned: back them up and explicitly grant UID/GID 10001 read/write access before starting this image. Do not delete inputs or lineage to repair permissions. Linux ownership, volume persistence and the current image still require execution on a Docker-capable machine; no usable engine was found locally.

| Setting | Default | Meaning |
|---|---|---|
| `CACHE_DIR` | `/data/cache` in container | Runtime files and immutable lineage |
| `GOLDEN_CACHE_DIR` | `/app/golden_cache` | Approved historical observations |
| `SPHEREX_FRONTEND_DIST` | `/app/frontend/dist` | Built frontend |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` | Trusted proxy addresses; configure explicitly for the controlled proxy network |
| `LIVE_MAX_ACTIVE_BUILDS` | `2` | Distinct live builds per process; same-query sharing remains |
| `RUNTIME_STORAGE_BUDGET_BYTES` | `8589934592` | Soft 8 GiB runtime admission threshold |
| `LIVE_BUILD_RESERVATION_BYTES` | `536870912` | Estimated 512 MiB headroom per build |
| `RUNTIME_MIN_FREE_BYTES` | `1073741824` | Additional 1 GiB filesystem free space |
| `LIVE_SKY_DEADLINE_SECONDS` | `120` | Shared best-effort sky acquisition/processing budget |

Deploy one worker until distributed admission exists. Storage checks count `cutouts`, `live`, `analysis-inputs` and `discovery-responses`, rejecting work rather than deleting records. Reservations are estimates, not a filesystem quota: other processes or oversized inputs can consume more space afterward. Monitor usage and arrange retention/export deliberately. TTL invalidates reads; it does not remove files. Browser cancellation can leave shared server work running.

The container health check calls `/api/v1/health`, including a periodically cached upstream reachability probe. A healthy server does not promise that new observations can be acquired. Configure eventual proxy timeouts around the acquisition budgets and verify them on the actual host. Do not blindly add `Content-Encoding: gzip` to already-compressed telemetry.

## Repeatable checks

```sh
python -m pytest backend/tests -q
npm --prefix frontend run test:real-data
npm --prefix frontend run test:wcs
npm --prefix frontend run test:semantics
npm --prefix frontend run test:views
npm --prefix frontend run build
python scripts/verify_real_data.py --require-dist
python scripts/build_golden_cache.py --target all --verify-only --require-telemetry
python scripts/release_smoke.py --base-url http://127.0.0.1:8000 --offline --out release-reports/http.json
```

The HTTP smoke compares served build assets and every returned saved frame, difference, reference and telemetry byte to the repository, exercises all five saved spectra and verifies retired fixture namespaces return 404. `--offline` describes its saved-only requests. Prove independence by starting a dedicated test server with `IRSA_TAP=http://127.0.0.1:9/TAP` and `IRSA_SIA2=http://127.0.0.1:9/SIA`; never apply these overrides to an acquisition server.

The staged `.github/workflows/verify-release.yml` repeats tests/build, constructs the current container and verifies non-root operation and named-volume persistence. It has not been pushed or executed here. A workflow file is not a passing image.

Before a later public release, verify the final image, cold acquisition, proxy timeouts, persistent permissions, resource use and unauthenticated access on the chosen host. Publishing and submission are outside this task. Real origin, matched fields, eligible photometry, measured motion and astrophysical validation remain distinct; see [result meaning](result-meaning.md).
