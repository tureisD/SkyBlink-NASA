# Real-data product policy — Phase 1

Effective 2026-11-14, authorized by the user's request to implement audit Phase 1 and approved by the Orchestrator in repository contract v1.3. API schema 1.2.0 is unchanged.

## What belongs in the product

The five catalog datasets under `golden_cache/{target_id}` contain saved SPHEREx observations and their derivatives, plus measured SkyView DSS2/WISE and Gaia reference products. Live results must come from the IRSA pipeline. Derived images, normalization, and reprojection remain allowed; these are not newly invented observations. Trial-motion overlays are explicitly user-selected geometric hypotheses, not measured motion or replacement sky pixels.

Product mock datasets, synthetic fallback observations, fixture generators, mock environment modes, and illustrative model spectra are removed. The Planck-curve comparator and its known screenshot are retired. The former `/mock` and `/api/v1/assets/fallback_*` namespaces return 404, including when a stale volume contains files there. Asset serving allows only the five catalog IDs and canonical live-query keys.

The `is_simulated_fallback` boolean remains in the API schema for wire compatibility. Product consumers and cache loaders require it to be explicitly `false`. This marker is a rejection check, not proof of authenticity: recorded upstream references, hashes, and the reviewed inventory supply additional evidence.

API 1.6 adds an approved metadata-only catalog exposure index at
`data/catalog-exposure-index.json`. It copies addresses and observation metadata
from verified real analysis records; it contains no image pixels or model
spectra. Explicit known-exposure mode uses it to download observations afresh,
with the same quality gates and partial historical-discovery labeling. Its
approved hash is checked by packaging and its bytes enter runtime source
identity. It is not an automatic fallback or a current all-sky inventory.

## Inventory and packaging

`phase1-data-inventory.json` lists data/binary assets, hashes, origin classifications, source evidence, unresolved historical assets, and generated test-input locations. It describes existing data/binary files in the tracked working tree; deleted historical files do not remain approved. New data must be reviewed, tracked, and inventoried before packaging. The inventory excludes its own hash. Generated test-input locations are listed separately, including the new rejection tests. The inventory is not a scientific accuracy certification.

The Python packaging gate is `scripts/verify_real_data.py`. The frontend build also checks its product inputs/output. Docker copies only the five approved catalog datasets and runs the packaging gate against the assembled runtime contents. Tests, QA captures, research documents, and the remaining historical screenshots are not runtime datasets and are excluded from Docker. Unknown documentation provenance stays explicit in the inventory rather than being silently classified as NASA observations.

The five real target datasets must remain byte-for-byte unchanged by Phase 1. Later scientific corrections require the staged rebuild and validation described in audit Phases 3–4.

## Remaining generated test inputs

The product removal does **not** justify saying that there is no synthetic data anywhere in the repository or Git history. Deterministic test inputs remain necessary for exact edge cases: flag combinations, known flux/unit conversions, invalid metadata, deadlines, bad telemetry encodings, and rejection of simulated responses. These are generated in test code, never served as observations, and excluded from runtime packaging. Tests that previously depended on the shipped mock datasets now use the saved real target data where practical.

Replacing a known-value unit test with an arbitrary observed cutout would remove its independent expected result; this cleanup preserves that coverage and inventories the inputs instead. Protocol mutation tests deliberately alter real-derived response copies to verify rejection. Historical documentation captures of unresolved origin are also recorded. The obsolete known model-spectrum screenshot is removed. Git history and the user's existing local virtual environment are not rewritten or deleted.

The accurate claim after this phase is: **the product ships approved real-derived observation datasets, with no mock/fallback datasets or illustrative model spectra; test-only generated inputs and unresolved historical documentation are explicitly inventoried.**

## Verification and limits

Run backend tests, frontend typecheck/build, the real-data packaging gate, and saved-cache verification before release. Regression checks must prove that retired namespaces stay blocked even if files reappear, all five catalog endpoints/assets work without IRSA, and simulated or missing-provenance responses are rejected.

Verified on 2026-11-14:

- Backend suite: **93 passed**, including real catalog/asset access with upstream queries disabled, stale static-file blocking, and golden/live cache provenance rejection.
- Frontend: `npm run test:real-data` and `npm run build` pass. The build includes TypeScript checking plus source/output packaging gates. All five saved real payloads are accepted; deliberately invalid provenance and retired asset URLs are rejected.
- `python scripts/verify_real_data.py --require-dist`: passes for the workspace and a temporary runtime-shaped tree containing the files selected by Docker COPY instructions.
- `python scripts/build_golden_cache.py --target all --verify-only --require-telemetry`: five targets pass, no failures.
- All **288** original real-cache files retain their baseline SHA-256 hashes. Approved runtime static artwork is limited to the favicon and workflow SVG.
- `git diff --check`: passes. No new full browser interaction run was performed; package/rejection tests do not substitute for the Phase 5 browser matrix.

This environment does not expose a usable Docker CLI or WSL distribution, so a new container build/run cannot be certified here. The Dockerfile is hardened and its package gate can be exercised locally; the old `skyblink:final` metrics in historical docs predate this change. Rebuild and run the container checks on a Docker host before deployment.

Audit Phases 2–5 remain open: arbitrary-coordinate temporal retrieval, exact frontend TAN projection, spectral comparability and measurement masks, stronger science validation/provenance, and public release checks. Phase 1 does not claim those issues are fixed.
