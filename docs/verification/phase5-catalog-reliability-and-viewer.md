# Catalog runtime repair and image-first controls

Verification date: 2026-11-15. API 1.5.0; image processing method 12. This report separates the actual development-service repair, current archive results, retained-data UI checks and remaining limitations. No scientific selection threshold was relaxed, and the five revision-3 saved datasets were not rebuilt.

## Confirmed runtime problem

The user's Vite service on port 5173 proxied API port 8000. That API's worker was started at 00:13 local time and still executed image method **11**, although `spherex_pipeline.py` on disk had method **12**, modified at 01:13. A fresh Barnard request to the stale service took **106.485 seconds**, returning one epoch and `PARTIAL_DOWNLOAD_NO_MATCHED_PAIR`; the same field on a fresh isolated method-12 service took **40.407 seconds**, returning a matched visual pair. Both discovery sets were complete. These are two measured requests, not a controlled latency benchmark or a universal availability claim.

Read-only inspection of the old API parent/worker and Vite process found the expected working directories and no allowlisted backend configuration or HTTP proxy overrides. The loaded code, rather than a demonstrated configuration difference, explains why earlier isolated method-12 tests did not establish that the user's active service had been updated.

The old record also combined `method.version=11` with a fingerprint of the method-12 files then present on disk. Such a disk fingerprint did not prove which code was already imported. This record is retained as diagnostic evidence, not silently rewritten or represented as a valid current-source replay.

Evidence is retained under `backend/.cache/phase5/recurrent-download-diagnosis/` and `backend/.cache/phase5-catalog-reliability/`. The read-only `scripts/inspect_runtime_environment.py` emits only explicitly allowlisted configuration, working directories and redacted proxy host information; it does not save raw environment blocks.

## Durable development behavior

`python scripts/dev_api.py` watches only backend source directories, excluding the large research/input cache. For a hidden/background Windows launch, use **`python scripts/dev_api.py --no-reload`** and restart explicitly after source changes. This investigation reproduced a hidden Windows reload shutdown hang: WatchFiles detected a source change, but Uvicorn did not shut down its worker, even with no active requests. Narrow watch roots alone did not solve it. The exact original stale-process mechanism was not independently proven.

Startup logging now records loaded API version, image method and PID. A processing-source guard rejects new archive work or record publication after source drift, with typed `PROCESSING_SOURCE_CHANGED` restart guidance. It prevents attaching a new disk fingerprint to an old loaded implementation. The frontend explains that a server restart is required; it does not suggest an endless retry loop. Saved products remain explicit historical observations.

An unrelated replacement `uvicorn --reload --port8000` process appeared during verification and occupied the port; its failed intended-server bind and interrupted matrix are retained in `port-race-interrupted`. The final matrix started only after confirming one intended listener, PID 7616, launched with `--no-reload`. No custom supervisor or broad process kill was introduced.

## Fresh verification on the user's API port

All five requests were sequential, `source=archive`, size 0.2 degrees, using corrected target coordinates on the actual API8000. Every final request returned HTTP 200, two real epochs, complete discovery and `matched_visual` method 12 on its first attempt:

| Field | Elapsed seconds | Returned epochs | Fresh retained inputs |
|---|---:|---|---:|
| Barnard's Star | 72.328 | 2025_E2, 2026_E1 | 4 |
| WISE 0855 | 19.531 | 2025_E1, 2026_E1 | 4 |
| Epsilon Indi B | 52.312 | 2025_E1, 2026_E1 | 4 |
| RW Aurigae | 54.454 | 2025_E1, 2026_E1 | 8 |
| R Draconis | 42.188 | 2025_E1, 2025_E2 | 3 |

R Draconis also retained **one failed candidate download**. Its verified pair came from completed inputs; the failure was not hidden or converted into data. A matched field does not prove detection, proper motion or variability of the named target. Background support, spectral compatibility, sparse sampling and existing scientific limitations still apply.

The backend retained full responses, immutable analysis records, acquisition receipts and asset checks in `backend/.cache/phase5/recurrent-download-diagnosis/final/`. An independent `scripts/verify_catalog_receipts.py` pass checked all five current processing-source whitelists, all 23 retained input entries and their fresh receipts, and every response-linked image/difference/telemetry asset against both local bytes and HTTP-served bytes. It made no new archive query. Machine-readable results are in `backend/.cache/phase5-catalog-reliability/independent-integrity.json`.

The backend suite passed **293 tests** in 66.73 seconds. Strict offline replay of the final Barnard record (`sha256:6ffb100428b17603a176670eb51110bf11eb5fb8a0cbb342a756d700937c0bd7`) verified source, environment, input hashes and exact numerical results. Its report is retained in `final/replay-barnard/replay-report.json`. Arithmetic replay does not establish astrophysical validity.

The final actual-browser check navigated to **`http://localhost:5173/?source=archive&target=barnards_star`**, using the user's existing Vite proxy and restarted API8000 with **no response interception**. It received HTTP 200 in **39.502 seconds**, method 12, complete discovery and two matched epochs. Blink painted three distinct real renders without replacing the canvas; A/B assets had distinct hashes, paired view rendered and Difference was enabled. Its response/record and independent input/source/served-asset verification are retained in `backend/.cache/phase5-catalog-reliability/user-browser/`.

That run's original harness result remains marked failed because it incorrectly required exactly one request-start event. Development React StrictMode emitted two identical archive requests; the API logged both HTTP 200. The measured behavior checks had already succeeded. `assessment.json` records the scoped acceptance of those checks and the erroneous assertion without rewriting the original result or repeating archive acquisition. Browser request-failure events and separate build counters were not captured in that run, so it does not prove whether the first browser request was aborted or how server work was shared. The reusable script now checks query/source identity and records response/failure events rather than assuming one request event. No saved fallback occurred.

## Viewer behavior and browser evidence

The separate layout toolbar is removed. Open panels contain their own close/hamburger controls; collapsed panels expose edge reopen buttons. Focus image is in the viewer heading. Duplicate central coordinates are hidden only when the visible Fields panel already presents them. The image remains the dominant content.

Essential comparison status remains visible outside the image. Detailed limitations and retry actions open an explicit, nonmodal Inspector notification, never an image-covering banner. Dismiss and Escape restore the trigger's focus; the notification can be reopened. A single epoch still disables blink and observation B; retry repeats the same archive query without switching to saved data.

The 12-case layout matrix covers Chromium, Firefox and WebKit at 1440, 1024, 390 and 320 pixels. All new panel, notification, geometry and persistent-canvas checks passed. All **36 axe scans reported zero violations**, although some contrast/ARIA checks require manual review. The original matrix had **11 complete passes and one WebKit1024 spectrum Home-selection failure**, preserved in `viewer-final/results.json`. This was investigated as a product race, not erased by rerunning: the key reached the focused chart, selected a sample, and a delayed spectrum-reset effect cleared it. Independent frontend tracing reproduced this in 3/12 openings before the fix and confirmed selection followed by reset in the instrumented run. Resetting data-dependent interaction state in a layout effect now completes before paint. The final independent earliest-ready regression passed **36/36** openings (12 each in Chromium, Firefox and WebKit), with one Home key, no added readiness delay and the same two-second bound. No broader layout rerun was needed for this isolated spectrum-state correction.

A separate **9/9** real-product matrix passed across the three engines using unchanged retained matched, single-download and partial-discovery API bodies and their exact real assets. These isolated response routes are QA only, never a product fallback. It verifies same-query retries, preserved source/limitations, disabled single-epoch controls, distinct real A/B assets and enabled matched differences. A protocol-only unit regression verifies typed server-restart guidance and rejects prose-based or unrelated-error classification.

Screenshots and origins are in [the capture directory](../screenshots/catalog-viewer/origins.json). Captures identify the saved observation inputs, all frontend source hashes, build hashes and script hash. Saved examples remain labelled historical/unvalidated. Raw browser receipts are retained under `backend/.cache/phase5-catalog-reliability/`.

Final capture build: `index-BnRUyT2X.js` and `index-HZzVzK05.css`. Nine documentation images cover 1920/1440/1024/390/320 initial views, desktop focus and paired views, and desktop/mobile notifications. The final real-only packaging gate passed with all **288 approved observation assets unchanged**. Development launcher CLI validation passed; frontend typechecking, build guards and the existing view/real-data/WCS/semantics checks passed during integration. Owned QA services on 8176/5176 are stopped after verification; the user's 8000/5173 services remain available.

## Limits

This is one bounded five-field acquisition run plus explicit browser regression evidence. It does not establish all-sky availability, stable upstream performance, target identification, calibrated variability or successful future requests. Old failed and partial results remain intact. No generated observations or automatic fallback were added. Human comprehension studies, screen-reader testing and quantitative flash-safety certification remain unperformed; automated checks are not substitutes.
