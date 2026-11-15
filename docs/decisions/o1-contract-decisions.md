# Contract decisions — O1 1.0.0, O2 1.1.0, and B10 1.2.0

**Audit Phase 3 update:** API 1.3.0 supersedes the original eligibility predicate below: unsupported local background produces null flux/error and false `is_used_in_photometry`, even with positive pixel-based `clean_fraction`. Other field types and hard-mask semantics are unchanged. See [the approved Phase 3 decision](phase3-contract-decision.md). Historical definitions below describe saved revision-3 products.

**Status:** Frozen and implemented. `1.0.0` was the O1 freeze; `1.1.0` is the additive Phase 2 freeze (2026-11-09); `1.2.0` is the B10 DR1 release-value addition (2026-11-13; schema unchanged). The models, `openapi.json`, development fixtures, backend, frontend, tests, and golden cache revision 3 all use the current contract.

**Historical note:** the pre-event plan originally held application code until H+0. The Berlin Local Event confirmed in writing that registered participants may start early (see `docs/reference/event-compliance.md`), so O1/O2 and the implementation were completed before the event weekend. Attendance both days and timely submission remain required.

**Why the contract is documented here:** `AGENTS.md` §3 is the consumer-facing contract; this file records the reasoning, the rejected alternatives, and the measured Phase 2 additions (telemetry sidecars, LVF geometry, optional candidates, photometry provenance).

**Contract version:** `1.0.0` was the initial O1 freeze. `1.1.0` is the additive Phase 2 freeze (2026-11-09): telemetry sidecars, LVF geometry, optional candidates, and per-channel photometry/aperture provenance. `1.2.0` (2026-11-13) extends the accepted `collection`/`release` values to DR1/QR3/DR1+QR3 with no schema change. No 1.0.0 field changed type or meaning. `psf_wing_fit` is intentionally absent (W0 measured 0/54 and 0/60 passing channels; see `docs/research/w0-feasibility-report.md`).

**DR1 update (2026-11-13):** IRSA serves **DR1 + QR3** and recommends them over QR2. B10 (`3c642ef`) implemented the extended values as contract **1.2.0**; S7 (`664977e`) rebuilt the golden cache as revision 3 from DR1+QR3. QR2 remains only in the revision-2 rollback cache. See `docs/reference/resource-release-2026-11-13.md`.

---

## 1. DICHROIC (bit 7) and `/spectrum`

**Conflict:** §4.2 says DICHROIC is low-throughput and should be excluded/corrected for photometry, while §3.5/§4.8 say warning bits never make a channel bad.

**Decision:** Keep `is_flagged_bad` strictly hard-bad, and add two diagnostic fields per channel:

```json
{
  "detector": 6,
  "wavelength_um": 4.682,
  "bandwidth_um": 0.037,
  "flux_ujy": 142.5,
  "flux_err_ujy": 8.4,
  "flags": 2097152,
  "is_flagged_bad": false,
  "clean_fraction": 0.86,
  "is_used_in_photometry": true
}
```

Definitions:

- `PHOTOMETRY_EXCLUDE_MASK = HARD_BAD_MASK | ARTIFACT_WARNING_MASK`. It includes DICHROIC, TRANSIENT, OVERFLOW, PERSIST, OUTLIER, CROSSTALK, GHOST, GHOST_EXT, STREAK, and the unused GHOST_FPA. It does **not** include `BIT_SOURCE`.
- `N_aperture` = number of native-grid pixels within the **fixed 12.3″ (2.0 native-pixel) aperture**, centered on the channel's extraction center. The MVP has no `aperture_arcsec` query parameter; a larger aperture would overlap the 3.0–5.0 px annulus.
- `N_clean` = number of those pixels that are finite and not in `PHOTOMETRY_EXCLUDE_MASK`.
- `clean_fraction = N_clean / N_aperture`, in `[0, 1]`.
- `is_used_in_photometry = (clean_fraction >= 0.5) and not is_flagged_bad`. The threshold is `0.5`; it is a data-quality threshold, not a probability.
- `flags` is the `FLAGS` value at the **channel's extraction center**: the native pixel at the target coordinate in that channel's exposure/epoch, along the source trace. It is **not** one pixel for all channels and **not** an aperture OR. The WCS-WAVE wavelength is evaluated at that center; across epochs, use the propagated target coordinate for that epoch.
- `is_flagged_bad = ((flags & HARD_BAD_MASK) != 0)` for a present channel. Missing channels are **omitted** from `channels[]`; they are not represented as `is_flagged_bad=true`. A DICHROIC-only extraction center remains `false`; warning bits never make a channel bad.
- `flux_ujy` / `flux_err_ujy` are measured from the clean pixels. If `N_clean == 0`, both are `null`; if `clean_fraction < 0.5`, the flux may be present but `is_used_in_photometry` is `false` and the frontend shows a caution. No blind aperture correction is applied; when `clean_fraction < 1`, the flux is a clean-pixel measurement, not a calibrated total. Label it relative photometry.
- The background annulus (3.0–5.0 native px) uses `HARD_BAD_MASK | ARTIFACT_WARNING_MASK | BIT_SOURCE`; `BIT_SOURCE` is excluded from the background, never from the source aperture.

Frontend behavior: plot all channels; render `is_used_in_photometry == false` or `clean_fraction < 0.8` with an open/amber marker and a tooltip ("DICHROIC / warning pixels excluded; N% clean aperture"). Do not label these as "bad" or "artifact probability."

`/spectrum` channels may therefore contain `null` flux/error fields. The Pydantic model must allow `float | None`.

---

## 2. `flag_summary` aggregation across bands

`flag_summary` is one object per epoch. Aggregate over all bands that have data for that epoch (bands missing from `frames` are excluded; do not treat missing as nominal):

| Field | Aggregation |
|---|---|
| `status` | Worst **target-aperture** status across bands. **ALERT** if the aperture union contains `TRANSIENT`, `OVERFLOW`, `PERSIST`, `CROSSTALK`, `GHOST`, `GHOST_FPA`, `GHOST_EXT`, or `STREAK`. **CAUTION** if the aperture union contains `DICHROIC` or `OUTLIER`, if `artifact_pixel_fraction > 0.01`, or if `HALO` is active in the target's display-only mode (see §9). **NOMINAL** otherwise. |
| `artifact_pixel_fraction` | **Maximum** per-band fraction of finite **frame** pixels with any `ARTIFACT_WARNING_MASK` bit after reprojection. The worst band drives the number. |
| `active_warning_flags` | Sorted **union** of warning flag names **inside the target aperture** across bands (unique). |
| `source_bit_set` | `true` if `BIT_SOURCE` is set in the target aperture (r = 12.3″) in **any** band; for arbitrary positions, use the same aperture centered on the query position. |
| `human_explanation` | Generated from the aperture union/status; if multiple bands, say "multiple bands"; name the worst flags. Do not invent probabilities. |

`frames.flag_overlay` is a single image per epoch showing the **union** of `ARTIFACT_WARNING_MASK` pixels across bands on the common WCS, plus `(1 << 28)` when the target's display-only HALO mode is active (see §9). Per-band overlays are out of scope for the MVP.

Status and `active_warning_flags` are **target-aperture-centric**; `artifact_pixel_fraction` and `flag_overlay` are **frame-wide**. This keeps unrelated frame artifacts from forcing `ALERT` while still surfacing them.

The `bands` query filter changes only the six band keys `"1"`–`"6"`. `frames.all`, `frames.thermal`, and `frames.flag_overlay` are always returned when available. `flag_summary`, `source_bit_set`, and `artifact_pixel_fraction` are computed over all bands with data for the epoch and are independent of `bands`.

Hard-bad pixels are not part of `artifact_pixel_fraction`; they are already `NaN` in the frames. The frontend may show a separate data-quality note.

---

## 3. Provenance for DR1/QR3 and mixed responses

> **2026-11-13 DR1 update:** IRSA now serves **DR1 + QR3** and recommends them over QR2. The accepted release vocabulary is `DR1`/`QR3`/`DR1+QR3`; `QR2`/`QR2+QR3` remain valid only for revision-2 saved data. B10 implements this as contract **1.2.0** (data values only; schema unchanged). The historical QR2 wording below is retained for revision-2 context.

Add per-epoch release fields and define the top-level rule:

- `epochs[].collection` = `"spherex_dr1"`, `"spherex_qr3"`, or `"mixed"` (historical: `"spherex_qr2"`); `epochs[].release` = `"DR1"`, `"QR3"`, or `"DR1+QR3"` (historical: `"QR2"`, `"QR2+QR3"`).
- Rule: if every frame/channel in that epoch comes from one release, use that collection/release. If any band falls back to a different release, the epoch is `collection="mixed"`, `release="DR1+QR3"` (or historical `"QR2+QR3"`). `/sky.frames` is per band, so this can happen within one epoch.
- Top-level `provenance.collection` / `provenance.release`:
  - All epochs share a release → that collection/release (`spherex_dr1`/`DR1`, `spherex_qr3`/`QR3`, or historical `spherex_qr2`/`QR2`).
  - Mixed releases → `collection = "mixed"`, `release = "DR1+QR3"` (historical `"QR2+QR3"`).
- `provenance.source` reflects the actual releases, e.g. `"NASA/IPAC IRSA SPHEREx DR1"`, `"NASA/IPAC IRSA SPHEREx QR3"`, `"NASA/IPAC IRSA SPHEREx DR1/QR3"`, or the historical QR2/QR3 strings.
- WISE 0855 as of 2026-11-08 (revision 2): all epochs QR2 → `collection = "spherex_qr2"`, `release = "QR2"`, `source = "NASA/IPAC IRSA SPHEREx QR2"`.
- The same fields go into the golden-cache `manifest.json` and `spectrum.json` per epoch.
- `/spectrum.epochs[]` also gets `collection`/`release`. If any channel in that spectrum epoch comes from a different release, the spectrum epoch is `collection="mixed"`, `release="DR1+QR3"` (or historical `"QR2+QR3"`). The top-level `/spectrum.provenance.collection`/`release` follows the same common/mixed rule; `source` reflects the actual releases.

**`provenance.is_simulated_fallback`:** the boolean wire field is retained in API **1.2.0**. Audit Phase 1 / repository contract v1.3 removes all product mock opt-ins and requires an explicit `false` value in served/accepted observation payloads. Historical fixture payloads remain representable by the schema but are rejected by the application. Generated test-only inputs are inventoried and excluded from runtime; see `real-data-policy.md`.

This is a schema addition to `/sky` and `/spectrum`; at O1 it is part of `1.0.0`.

---

## 4. Asset paths for arbitrary RA/Dec

Keep the URL shape `/api/v1/assets/{target_id}/{filename}`, but define the first segment as a **catalog ID or an opaque live cache key**:

- Catalog: the five IDs (`wise_0855`, …). Catalog assets are size-independent (full 240×240, 0.205° golden grid); `size` is a client-side crop. `target_id` requires `ra`/`dec` within 1.0″ of the target's 2025.8 coordinate, otherwise 422.
- Live: `live_<sha256(canonical_query)[:16]>`.
- Canonicalize **before** hashing:
  - Treat `all` case-insensitively; reject other non-numeric band values.
  - Validate `ra` in `[0, 360)` and `dec` in `[-90, 90]`; out-of-range → 400 `INVALID_COORDINATES`. Do **not** wrap `ra`; the cache key uses the validated value.
  - Clamp `size` to `[0.05, 0.2]`.
  - `bands_key`: empty or `all` → `"all"`; otherwise parse ints 1–6, dedupe, sort numerically, join with `-` (e.g. `1-5-6`). `all` must be alone; mixing `all` with explicit bands is a 422.
  - `epochs_key`: empty or `all` → `"all"`; otherwise split, strip, sort lexicographically, join with `-` (e.g. `2025_E1-2025_E2`). `all` must be alone.
  - `include_diff`: `0` or `1`.
  - `canonical_query = f"{ra:.6f}_{dec:.6f}_{size:.4f}_b{bands_key}_e{epochs_key}_d{include_diff}"`.
  - Hash the UTF-8 string with SHA-256 and take the first 16 hex chars.
- Examples: `bands=all&epochs=all` → `..._ball_eall_d1`; `bands=5,6&epochs=2025_E2,2025_E1` → `..._b5-6_e2025_E1-2025_E2_d1`.
- Example URL: `/api/v1/assets/live_4f3c2a1b9e8d7c60/2025_E1_D6.webp`.
- Validate the key with `^[A-Za-z0-9_-]{1,64}$`; validate the filename with `^[A-Za-z0-9_.-]+$`; reject any path separators or `..`.
- `reference_overlays` for live positions: attempt HiPS2FITS on the same WCS and return `ref_optical.webp` / `ref_wise.webp` under the same key. If the service fails or is not attempted, return `{}` or omit the keys; the frontend hides the curtain. Catalog targets use the precomputed golden-cache overlays.
- Cache-Control: golden/cached assets `public, max-age=3600`; live-generated assets `no-store` or a short max-age, per `AGENTS.md` §3.1.

No URL shape change is required; this is a documented convention. Renaming `{target_id}` to `{asset_key}` is optional and can be done at O1 if both agents prefer it.

---

## 5. LAW 8 normalization

Add to `/sky.provenance`:

```json
"flux_normalization": {
  "method": "static_source_p99_5",
  "scope": "per_band_across_epochs",
  "reference_epoch": "2025_E1",
  "applied": true,
  "status": "ok",
  "clamped": false,
  "raw_stats_location": "server_only"
}
```

Decision: **frames are pre-normalized**; raw statistics stay server-side. The frontend must not re-normalize; its contrast/stretch controls operate on the normalized frames.

**Why not the median:** the background-subtracted field is centered near zero; its median is ≈0 (or negative) and is not a star-based scale. Use a high percentile of **static source pixels** instead.

Algorithm (backend, per band):

1. Start from the reprojected, ZODI-subtracted, local-background-subtracted frame.
2. Build the **static-source mask**:
   - `BIT_SOURCE` is set (known catalog star/galaxy).
   - `FLAGS & (HARD_BAD_MASK | ARTIFACT_WARNING_MASK) == 0`.
   - Finite pixel.
   - Outside the target aperture **and its PSF wings**: `r > 5 × aperture_radius` (61.5″ = 10 native px); for arbitrary positions, use the query center.
   - Do **not** exclude `BIT_SOURCE` here: the static sources are the normalization reference. (`BIT_SOURCE` is still excluded from the background estimate, per §4.5.)
3. If `N_static >= 50`, compute `P_epoch = percentile(frame[static_mask], 99.5)`.
4. Choose a **global reference epoch**: the earliest epoch by `mjd_mean` for which every band with data (at least one finite pixel in that epoch) has `N_static >= 50`. If no epoch satisfies all bands, choose the epoch that satisfies the most bands (tie-break: earliest `mjd_mean`). For each failing band, use the earliest epoch by `mjd_mean` with `N_static >= 50` for that band. If a band has `N_static < 50` in every epoch, use the all-pixel fallback for that band: choose the earliest epoch with `N_fallback >= 100` as the band reference, set `P_ref` from the all-pixel 99.5th percentile, and use the all-pixel 99.5th percentile for all epochs in that band; if no epoch has `N_fallback >= 100`, that band cannot be normalized (step 7). Record the per-band references. If any band uses a different reference than the global one, set `reference_epoch="mixed"` in the API. The reference scale is `1.0` in the reference epoch for each band.
5. For each epoch: `raw_scale = P_ref / P_epoch`; `scale = clamp(raw_scale, 0.5, 2.0)`; apply `frame_normalized = frame_raw * scale`.
   - When scaling a frame by `scale`, also scale its variance by `scale²` (and inverse-variance weights by `1/scale²`) before the coadd, so the inverse-variance weighting stays consistent.
   - If `raw_scale` is outside the clamp, record `clamped=true` and `status="clamped"`; still use the clamped value.
   - If `P_epoch` is non-finite or ≤ 0, fall back.
6. Fallback when `N_static < 50`: use the 99.5th percentile of all finite, non-hard-bad, non-warning pixels outside the target aperture **and wings** (background + sources). If `N_fallback >= 100`, use that percentile; `method="all_pixels_p99_5_fallback"`, `status="fallback_all_pixels"`.
7. If both are insufficient: `applied=false`, `scale=1.0`, `status="insufficient_static_pixels"`; do not normalize that band/epoch and surface the status.
8. Store in the golden-cache `manifest.json`:
   - `normalization.method`, `reference_epoch` (or per-band reference), `reference_percentile_by_band`, `raw_scale_by_epoch_band`, `scale_by_epoch_band`, `clamp`, `status`.
9. If the **full available-epoch set** has only one epoch: `applied=false`, `method="not_needed_single_epoch"`, `status="not_needed_single_epoch"`, `reference_epoch=<that epoch_id>`, no scaling. A filtered single-epoch response from a multi-epoch set still reports the global normalization (`applied=true`, global reference).

`flux_normalization.status` is the worst per-band status; severity order is `insufficient_static_pixels` > `clamped` > `fallback_all_pixels` > `ok` (`not_needed_single_epoch` is used only for single-epoch responses). Status enum: `ok`, `fallback_all_pixels`, `clamped`, `insufficient_static_pixels`, `not_needed_single_epoch`. `applied` is true if at least one non-reference epoch/band was scaled; `clamped` is true if any scale hit the clamp. If per-band references differ, set `reference_epoch="mixed"` and record the per-band references in the manifest. `method` is the primary method (`static_source_p99_5`) or `"mixed"` if fallbacks were used; per-band methods are in the manifest.

**All/thermal coadds:** build them **after** per-band normalization, using the same per-band scales for every epoch. Do not compute a separate coadd scale. The `all` coadd combines the normalized band 1–6 frames; the `thermal` **frame** uses the normalized bands 5 and 6, or whichever of the two is available. If a band is missing, the coadd uses the available normalized bands and the manifest records which bands were used. This keeps the relative band weights consistent across epochs. The **difference** `thermal` key requires both bands 5 and 6 to be common (see §8).

Difference mode: use the **un-normalized** but ZODI/background-subtracted frames for the server-side subtraction; the API returns the difference frames. Raw statistics are not exposed in `/sky`.

This is a schema addition to `provenance`; at O1 it is part of `1.0.0`.

---

## 6. `/spectrum.provenance.zodi_subtracted`

Yes. Add `"zodi_subtracted": true` to `/spectrum.provenance`, matching `/sky.provenance`. The pipeline subtracts `ZODI` before extraction; if a live path cannot subtract it, set `false` and surface the limitation. Keep `background_subtracted: true`.

**Parameters and data source:** `/spectrum` uses the same `target_id` 1.0″ check as `/sky`; `target_id` is `str | null`; `epoch_id` must be a full-set epoch ID (unknown → 422) and filters `epochs[]` only. Extract from **un-normalized**, ZODI/background-subtracted frames; do not apply the blink normalization.

No other spectrum provenance changes are required. `confidence` remains `"high"` for precomputed target spectra and `"low"` for best-effort live clicks; it is not a discovery probability.

---

## 7. `API_CONTRACT_VERSION` ownership and bump

- Put the version in an **Orchestrator-owned** module: `backend/models/version.py`:

```python
API_CONTRACT_VERSION = "1.2.0"
```

- Phase 2 froze **1.1.0** on 2026-11-09 with the additive fields in §12; B10 froze **1.2.0** on 2026-11-13 with the DR1 release values (schema unchanged). The `1.0.0` example above is the historical O1 value; the current model is `1.2.0`.

- The backend imports `from models.version import API_CONTRACT_VERSION`; `backend/core/config.py` may re-export it for convenience. This avoids the current ownership wrinkle where the version lives in backend-owned config but the contract is Orchestrator-owned.
- **Canonical import path:** run the app from `backend/` (or set `PYTHONPATH=backend`) and import `from models.version import API_CONTRACT_VERSION`. `backend.models.version` is **not** canonical unless `backend/__init__.py` is added and the repo root is the working directory; that is not the chosen layout. The tests' `conftest.py` adds `backend/` to `sys.path` so the same import works under pytest.
- O1 froze **1.0.0**; Phase 2 later froze **1.1.0** (§12); B10 froze **1.2.0** (DR1 values). The O1 statement below is historical: the pre-O1 coordinate correction, Table 16/GHOST_FPA correction, and the schema additions in this document were all part of the initial freeze.
- Any schema change after 1.2.0 follows `AGENTS.md` §3.8 and bumps the version again.
- The coordinate/bitmask corrections alone would not require a bump; they are values/policy, not schema.

---

## 8. Epoch IDs, differences, `mjd_mean`, and `wcs.crval`

**Epoch IDs**

- Format: `{start_year}_E{index}`, e.g. `2025_E1`, `2025_E2`, `2026_E1`.
- `start_year` is the calendar year of the epoch start; for an epoch spanning a year boundary (e.g. Nov 2025–Apr 2026), use the start year (`2025_E2`).
- `index` is the 1-based chronological index within that start year in the **full available-epoch set**, not the filtered response.
- IDs are response-stable across filters, not globally permanent. A shared URL whose epoch ID is no longer present falls back to the nearest available epoch and shows a non-blocking warning. The authoritative time is `mjd_mean`/`date_iso`.
- `label` is human-readable and includes the date range.

**Filtering**

- Compute the full available-epoch set for the target/field first. Assign epoch IDs, the reference epoch, and adjacent difference pairs on the full set.
- The `epochs` query parameter filters only the returned `epochs[]` and `differences`; it does not renumber IDs or change normalization.
- Unknown epoch IDs → 422 `VALIDATION_ERROR`.
- `differences` includes only full-set adjacent pairs whose two epochs are both in the filtered list; a non-adjacent selection yields `{}`.

**Differences**

- Generate **adjacent pairs only** in the full available-epoch list: `E1−E0`, `E2−E1`, ….
- Key format: `{later_epoch_id}_minus_{earlier_epoch_id}` (e.g. `2025_E2_minus_2025_E1`).
- Include a band key only if that band has data in **both** epochs. `all` is built from the common bands; `thermal` is included only when both bands 5 and 6 are common. Omit a pair with no common bands. Do not generate `flag_overlay` for differences. The `all`/`thermal` difference frames sum the per-band raw differences (after PSF matching) with the same per-band weights as the corresponding frame coadd; do not reweight per epoch.
- `include_diff=false` → `differences = {}`. One epoch → `{}`. Do not generate non-adjacent pairs in the MVP; a future query parameter can request a specific pair.
- The `bands` filter restricts only the six band difference keys; `all`/`thermal` are always returned when available.

**`mjd_mean`**

- Exposure-time-weighted mean of the midpoints `(time_bounds_lower + time_bounds_upper) / 2` of the science artifacts contributing to the epoch's displayed frames, across all bands/visits.
- If `time_exposure` is unavailable, use the unweighted mean of the midpoints.
- `date_iso` is the UTC date of `mjd_mean`. `label` may include the full range.

**`wcs.crval`**

- For a catalog target (`target_id`), `query.ra`/`dec` and `crval1`/`crval2` are the target's 2025.8 coordinates; the request's `ra`/`dec` must match within 1.0″ or the request is rejected with 422. For an arbitrary position, `query.ra`/`dec` and `crval` are the query center.
- Catalog target assets are precomputed on the fixed 240 × 240 / 0.205° golden grid; `size` is a client-side crop and does not change the assets. Live positions use `size` for the cutout and for the live cache key.

**Grid and size:** the canonical grid is 240 × 240 at 3.075″/px = 0.205°. `wcs` always describes this full grid. `query.size_deg` echoes the clamped request (0.05–0.2). For catalog targets, `size` is a client-side crop of the golden grid. For live positions, `size` sets the cutout size; the cutout is reprojected onto the full grid and pixels outside it are blank/NaN; `size` is part of the live cache key.
- `crpix1 = crpix2 = 120.5` (FITS 1-based center of the 240 × 240 grid).
- `cdelt1 = -0.0008541667`, `cdelt2 = +0.0008541667` (3.075″/px).
- `width = height = 240`; plain TAN grid, no SIP.
- The original cutout WCS is not exposed; the common grid WCS is the contract. `pixel_scale_arcsec = 3.075`; `native_pixel_scale_arcsec = 6.15`.

---

## 9. HALO (bit 28)

**Decision for the MVP:** keep `HALO` in `HARD_BAD_MASK` and set it to `NaN` **everywhere** (display and photometry) by default. Rationale:

- The supplement says "caution is recommended," not "unusable"; a display-only warning would be defensible.
- But a second display mask adds complexity and weakens the single `HARD_BAD_MASK → NaN` invariant during a 48-hour build.
- The Artifact Shield still surfaces the warning flags that are not hard-masked; by default HALO is a hard-mask condition, so it appears as a data-quality hole, not as a `CAUTION` badge.

**Measurement (S2-owned):** B1 exposes per-band HALO counts in the manifest; **S2 runs the gate for R Draconis** (and optionally all five) per band on the reprojected frame:

- `halo_fraction = count(FLAGS & (1 << 28) != 0) / count(finite pixels)`;
- `halo_aperture_fraction = count(FLAGS & (1 << 28) != 0 in the target aperture) / count(aperture pixels)`.

Record both in the golden-cache manifest/validation report. B1's WISE 0855-only scope is unchanged; S2 owns the all-five acceptance.

**Gate (per target, per band):** if `halo_fraction > 0.05` in any band or `halo_aperture_fraction > 0` for a target:

- Use `DISPLAY_BAD_MASK = HARD_BAD_MASK & ~(1 << 28)` for that target/response's displayed frames.
- Include `(1 << 28)` in `frames.flag_overlay`.
- Add `HALO` to `flag_summary.active_warning_flags`; status is at least `CAUTION` (do not use `ALERT` solely for HALO).
- Keep `HALO` in `PHOTOMETRY_EXCLUDE_MASK` and in the `HARD_BAD_MASK` used by `is_flagged_bad`; it reduces `clean_fraction` and, if present at a channel's extraction center, sets `is_flagged_bad`. The display-only mask affects only the displayed frame; photometry remains conservative.
- Otherwise keep NaN everywhere; HALO is not in `flag_overlay` or `active_warning_flags`.

The gate is evaluated once per target during S2 and recorded in the target manifest; the API reads that decision for the target. This is a display-only refinement, not an API schema change.

---

## 10. R Draconis and Epsilon Indi B proper motions

Use the **documented target-catalog PM values** in `backend/core/targets.py` for all five; they are the values used to derive the 2025.8 coordinates and the reticle.

| Target | `pm_ra_mas_yr` | `pm_dec_mas_yr` | Note |
|---|---:|---:|---|
| `wise_0855` | −8118.0 | +680.0 | CatWISE moving detections are consistent; Gaia DR3 has no source. |
| `barnards_star` | −801.6 | +10362.4 | Gaia DR3 `4472832130942575872` confirms (−801.551, +10362.394). |
| `eps_indi_b` | +3982.0 | −2466.8 | Gaia DR3 has no B source; Gaia A is +3966.661, −2536.192, close. Keep the B catalog values. |
| `rw_aurigae` | +2.6 | −27.4 | Gaia DR3 `156430822114424576` confirms (+2.641, −27.398). |
| `r_draconis` | −13.7 | −31.0 | Gaia DR3 `1648328016354496384` gives (−20.643, +6.149), low-confidence for a Mira. Keep the catalog PM for consistency; the vector is ~1″ over 25.8 yr. |

Do not add a `pm_source` field to the API for the MVP; put the note in the target story/docs. The reticle uses the stored PM values and the ref/2025.8 coordinates.

---

## 11. Validation wording

Replace "the other four validated with Gaia DR3" with:

> The other four targets were **checked against Gaia DR3**: Barnard's Star and RW Aurigae confirm the catalog PM; Epsilon Indi B has no Gaia B source (Gaia A is close); R Draconis's Gaia PM is low-confidence due to Mira pulsation.

Update `STATUS.md`, `ROADMAP.md` §6.11/§14.1, and the verification report summary accordingly.

---

## 11.1 O1 publication timing (historical plan)

- **Historical plan: no models or challenge code before H+0.** The official FAQ and `ROADMAP.md` §9.1 stated that rule; the Berlin Local Event later confirmed that registered participants may start early (see `docs/reference/event-compliance.md`).
- At **H+0 (O1)**, the Orchestrator planned to:
  1. Publish `backend/models/**` with the fields in this document.
  2. Add `backend/models/version.py` with `API_CONTRACT_VERSION = "1.0.0"`.
  3. Generate `backend/openapi.json`.
  4. Create explicit development-fixture manifests and placeholder WebP frames in `frontend/public/mock/`.
  5. Update `AGENTS.md` §3/§4 and the roadmap appendix to match this document.
  6. Tell B1/F1/S1 to start.
- The backend agent can review this document now and immediately start B1 after O1.

**Current behavior (2026-11-14):** normal operation is real-data only; the development fixtures are explicit opt-in and are never loaded automatically.

---

## 11.2 Roadmap/AGENTS updates

Applied as prose now; the Pydantic models/openapi are updated at O1:

- `ROADMAP.md` §6.4: DICHROIC photometry nuance (present).
- `ROADMAP.md` §6.5: `PHOTOMETRY_EXCLUDE_MASK` note in step 7; static-source p99.5 normalization in step 10; coadd scale consistency.
- `ROADMAP.md` §10.2: DICHROIC/`clean_fraction` bullet.
- `AGENTS.md` §3.5: extraction-center `flags`/`is_flagged_bad` and the O1 field pointers.
- `AGENTS.md` §4.8: DICHROIC/warning `clean_fraction` rule.
- `AGENTS.md` §3.8: canonical import path `models.version`.

---

## Summary of schema additions for O1

| Location | Field | Type | Notes |
|---|---|---|---|
| `/spectrum.channels[]` | `clean_fraction` | `float` 0–1 | Clean aperture fraction; DICHROIC/warnings reduce it. |
| `/spectrum.channels[]` | `is_used_in_photometry` | `bool` | `clean_fraction >= 0.5` and not hard-bad. |
| `/spectrum.channels[]` | `flux_ujy`, `flux_err_ujy` | `float \| null` | Null when no clean pixels. |
| `/spectrum.provenance` | `zodi_subtracted` | `bool` | Consistent with `/sky`. |
| `/spectrum.epochs[]` | `collection`, `release` | `string` | Per-epoch; `mixed`/`DR1+QR3` (historical `QR2+QR3`) if a band falls back. |
| `/spectrum.provenance` | `collection`, `release` | `string` | Common/mixed rule; `source` reflects actual releases. |
| `/sky.epochs[]` | `collection` | `string` | `spherex_dr1` / `spherex_qr3` / `mixed` (historical `spherex_qr2`). |
| `/sky.epochs[]` | `release` | `string` | `DR1` / `QR3` / `DR1+QR3` (historical `QR2` / `QR2+QR3`). |
| `/sky.provenance` | `flux_normalization` | `object` | Method/scope/reference/applied/status/clamped; p99.5 static-source normalization. |
| `/sky.provenance` | `collection`, `release` | `string` | `mixed` / `DR1+QR3` (historical `QR2+QR3`) when needed. |
| `/api/v1/assets/{target_id}/...` | — | convention | `target_id` may be `live_<hash>`; overlays optional. |

No other fields change. `is_flagged_bad` remains hard-only; `flags` is the extraction-center flag (not an aperture OR); `status` remains NOMINAL/CAUTION/ALERT.

---

## 12. Contract 1.1.0 — additive Phase 2 fields (frozen 2026-11-09)

> **Current:** contract **1.2.0** (B10, 2026-11-13) extends only the `collection`/`release` data values documented in §3. The fields below are unchanged and remain part of 1.2.0.

All fields are optional additions; existing 1.0.0 payloads and golden manifests remain valid.

| Location | Field | Type | Notes |
|---|---|---|---|
| `/sky.epochs[]` | `telemetry` | `{url, format, width, height, byte_size, flux_band} \| null` | `format="float16_uint32_le_gzip"`; `240×240 float16` MJy/sr + `240×240 uint32` flags, gzipped; separate from `frames`. `flux_band` is `thermal` or `all`. |
| `/sky.epochs[]` | `lvf_geometry` | `list[{detector, pa_deg, grad_um_per_arcsec}] \| null` | Per-detector LVF dispersion geometry for the visualizer. |
| `/sky.epochs[]` | `candidates` | `list[{id, ra, dec, x_px, y_px, kind, snr, delta_flux_mjy_sr, is_artifact_clean, label}] \| null` | Objective SNR/flux only; `kind` is `dipole` or `variable`; never a confidence score. |
| `/sky.epochs[]` | `core_inpainted` | `bool` (default `false`) | Display-only core inpainting; never alters science arrays. |
| `/sky.reference_overlays` | `optical_dss2_red`, `mid_ir_wise_w1`, `gaia_sources_url`, `attribution` | `string` | String map; 1.0.0 keys remain valid. |
| `/spectrum.epochs[].channels[]` | `photometry_method` | `"aperture_12.3" \| "crowded_diff_6.8"` | Default `aperture_12.3`. |
| `/spectrum.epochs[].channels[]` | `aperture_mode` | `"standard_12.3" \| "crowded_diff_6.8"` | Default `standard_12.3`. |
| `/spectrum.epochs[].channels[]` | `aperture_radius_arcsec` | `float` (default `12.3`) | Explicit per-channel aperture. |

**Not in 1.1.0:** `psf_wing_fit`. The W0 spike measured 0/54 Barnard’s Star and 0/60 R Draconis channels passing `f_wing ≥ 0.12` with ≥8 clean wing pixels; the annulus is not unsaturated. Adding it later requires a new contract decision and measured data.

**Telemetry budget:** measured revision-3 240×240 float16 + uint32 sidecars are **82.6–111.4 KiB gzipped** (WISE 0855 100.0–102.3 KiB), 104–134 KiB base64 JSON. The earlier W0 estimate was 78.5–101.0 KiB. Do not claim `<45 KB`.

---

## Open items deferred to November 13

- Submission/Judging guide: license, team size, video/slides, SI wording, judging weights.
- Recheck WISE 0855 QR3 coverage; exact epoch grouping per target.
- Decide whether to rename `{target_id}` to `{asset_key}` in the OpenAPI path parameter (cosmetic).
- Confirm deployment platform and admin access for Docker Desktop; WSL2 Docker Engine is the fallback.
- **Resolved by 1.1.0:** per-epoch `telemetry` sidecars now expose MJy/sr and Table 16 flags to the cursor loupe; 8-bit WebP display frames remain the rendered product.
- P1 (F1 follow-up): arbitrary multi-band coadds require server-side support or a new contract field; F1 collapses multi-band URLs to the first valid band to avoid client-side coadds of normalized frames (LAW 8).
- P1 (F3): the spectrum drawer and per-bit flag loupe need `/spectrum` (B3) and optional bitmask assets; the current overlay/summary is the honest fallback.
- B2 simplification: `all`/`thermal` multi-band weights are equal (per-band coadds are inverse-variance); inverse-variance across bands is a B3 optimization.
- B2 simplification: difference frames are direct subtraction of un-normalized coadds; PSF matching is a B3/P1 improvement.
- Golden-cache precedence: `/assets` serves `golden_cache/` before live assets; S1/S2 must not shadow B2 filenames unless their frames are equivalent.
