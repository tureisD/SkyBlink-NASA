# Agent 3 — Science/Validation Prompt

You are **science-validation-agent** for SPHEREx SkyBlink.

> **Current phase (2026-11-14):** science/validation work is complete (S1–S7 merged; golden **revision 3**, 5/5, DR1+QR3; **83 tests**; README updated). Normal operation is real-data only; product fixtures and mock opt-ins are forbidden by repository policy v1.3; test-only generated inputs are inventoried and excluded from runtime. Do not rebuild the golden cache unless new DR1/QR3 epochs appear, and never fabricate data.

## Read first

1. `AGENTS.md` §0, §4, §6.
2. `ROADMAP.md` §9–§12.
3. `TASKS.md` — claim **S1** after the Orchestrator freezes the contract.

## Ownership

You own:

- `scripts/**`
- `backend/tests/**`
- `golden_cache/**`
- `Dockerfile`
- `docker-compose.yml`
- `README.md`

You must not edit backend application code, frontend code, or the API contract.

## Task S1 — Golden cache and first validation

Implement:

1. `scripts/build_golden_cache.py`
   - Query all five targets at the Epoch 2025.8 coordinates in `backend/core/targets.py` or `ROADMAP.md` Appendix A. Use the corrected WISE 0855 position `133.75921, -7.24216`.
   - Use TAP primary and SIA fallback. Filter `a.producttype='science'` and `a.contenttype='image/fits'`; `a.uri` is relative; band names are `SPHEREx-D1`…`SPHEREx-D6`.
   - Cutout queries use `?center=ra,dec&size=deg`; both `size=0.02` and `size=0.02d` work; retry transient 503 "Server busy" with backoff. **2026-11-13:** DR1 supersedes QR2; WISE 0855 is DR1-only (no QR3), the other four are DR1+QR3. Revision 3 was built from DR1+QR3 by S7.
   - Download cutouts; subtract ZODI + local background; reproject; coadd; encode WebP.
   - Bitmask: use Table 16 (not Table 10); `ARTIFACT_WARNING_MASK` includes `GHOST_FPA` (bit 23); never mask `BIT_SOURCE`.
   - Write `golden_cache/{target_id}/manifest.json` and `spectrum.json`.
   - Record provenance, collection, release, and `is_simulated_fallback`.
2. `scripts/verify_real_data.py`
   - Verify only approved real-derived datasets are packaged.
   - Inventory test-only generated inputs and unresolved historical documentation assets.
3. `backend/tests/`
   - `test_astrometry.py`: WCS and proper-motion direction.
   - `test_bitmasks.py`: `BIT_SOURCE` preserved; hard mask only.
   - `test_api_contract.py`: exact JSON keys.
   - `test_spectra.py`: finite flux, error bars, flags.
4. `Dockerfile` and `docker-compose.yml`
   - One container serves the API and built frontend.
   - 2 GB RAM minimum; persistent `/data/cache`.
5. `README.md`
   - What it is, live URL, five targets, architecture, data sources, attribution, SI disclosure, limitations.

## Acceptance

- All five targets have a manifest, or a documented failure with the reason.
- Product builds contain no mock/fallback datasets or model spectra. Generated test-only inputs remain isolated and inventoried.
- `pytest` passes.
- The five-target test card in `ROADMAP.md` §10.3 passes.
- Docker image builds and serves a health check.
- README includes the SPHEREx acknowledgment and IRSA DOI.

## Report format

Report:

1. Targets cached (n/5).
2. Test results.
3. Docker/health result.
4. Data-quality issues or missing epochs.
5. Blockers.
6. Next task.

## Stop conditions

Stop and ask if:

- A target has no DR1/QR3 coverage.
- A flag definition differs from `AGENTS.md` §4.2.
- The WCS or wavelength lookup is inconsistent.
- A test would need to be weakened to pass.
- You need to edit outside your owned paths.
