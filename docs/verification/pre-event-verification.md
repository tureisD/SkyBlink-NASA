# Pre-event verification — 2026-11-08

**Status:** Pre-event research only. No challenge application code was written at the time of this verification.
**Scope:** Verify the official challenge/FAQ, live IRSA TAP/SIA2/cutout behaviour, the MEF HDU contract, the flag table, target coordinates, and the local toolchain.
**Sources:** Official NASA Space Apps 2026 challenge page and Participant FAQ; IRSA SPHEREx Archive documentation; SPHEREx Explanatory Supplement v2.0 (2026-08-25); live IRSA TAP/SIA2; one real QR2 cutout; Gaia DR3 and CatWISE catalogues via IRSA TAP.

> **Post-implementation update (2026-11-09):** this document records the pre-event verification; several later measurements supersede parts of it.
> - **PSF-wing recovery was tested and dropped.** HDU 5 `PSF` exists as documented, but the 1.2–4.2 px wing annulus is not unsaturated on Barnard’s Star/R Draconis: 0/54 and 0/60 channels pass. See `docs/research/w0-feasibility-report.md`.
> - **R Draconis NEP re-clustering was dropped.** The 2,483 TAP rows are one continuous 520-day season, not 5–6 clean 6-band epochs.
> - **CDS `hips2fits` is unreachable from this environment.** Real overlays use SkyView DSS2 Red + WISE 3.4/4.6 instead; see `golden_cache/w0_overlay_metrics.json`.
> - **2026-11-13 resource recheck:** **DR1 is released** (November 2026) and DR1+QR3 supersede QR2. WISE 0855 has DR1 coverage (258 artifacts, no QR3). DR1 HDU 5 is `EPSF`, not `PSF`. **B10/S7 are complete:** contract 1.2.0 and golden revision 3 (DR1+QR3, **no QR2**) are current. Full details: [`resource-release-2026-11-13.md`](../reference/resource-release-2026-11-13.md).
> - **Current state (2026-11-14):** contract **1.2.0**; golden **revision 3**, 5/5; **83 tests**; five-target card 5/5; `skyblink:final` 844 MB, healthy at 105.7 MiB idle, health version 1.2.0. Normal operation is **real-data only**; development fixtures are explicit opt-in and never automatic. Live arbitrary budget: TAP 60 s, sky 120 s, frontend 130 s, cutout 20 s. See `README.md` and `STATUS.md`.
> - The original “no pre-work” statement was superseded by the Berlin Local Event written confirmation; see `docs/reference/event-compliance.md`.

---

## 1. Result summary

| Item | Result |
|---|---|
| Official dates | November 14–15, 2026. Resources and the Project Submission / Judging guides are released November 13. |
| No pre-work | Confirmed: "Teams are **not allowed** to begin working on the challenges prior to the hackathon." |
| SI disclosure | Confirmed: SI = "Super Intelligence" per the September 29, 2026 Executive Order; each submission must describe how SI tools were used. |
| Five targets | Confirmed: Barnard's Star, Epsilon Indi B, WISE 0855, RW Aurigae, R Draconis. |
| TAP schema | Confirmed: `spherex.artifact` + `spherex.plane`; the columns used by the roadmap query exist. |
| Cutout format | Confirmed: `?center=ra,dec&size=deg` works; `size=degd` also works. 503s are transient. |
| HDU contract | Confirmed on a real QR2 cutout: `PRIMARY` empty; `IMAGE`, `FLAGS`, `VARIANCE`, `ZODI`, `PSF`, `WCS-WAVE` by `EXTNAME`. |
| Spectral WCS | Confirmed: `WCS(..., key="W")` + `sip=None`; `pixel_to_world(6, 6)` → 2.363159 µm. |
| `BIT_SOURCE` | Confirmed: source pixels carry bit 21; `flags != 0` would mask the target. |
| Flag table | **Table 16**, not Table 10. `GHOST_FPA` (bit 23) is defined but currently unused. |
| Coverage | **2026-11-13:** all five targets have DR1; the four non-WISE targets also have QR3. WISE 0855 is **DR1-only** (no QR3). QR2 is superseded. |
| WISE 0855 2025.8 | Corrected to `133.75921°, −7.24216°`; the old value matched 2025.4, not 2025.8. |
| Toolchain | Python 3.11.9 + backend requirements installed; Docker Engine 29.1.3 works in WSL2. Docker Desktop is installed but its service is blocked by admin rights; use the WSL engine. |

---

## 2. Official challenge and rules

### 2.1 Challenge page

Source: <https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/>

Confirmed text:

- "Since May 2025, NASA's new SPHEREx mission has been returning unique data... mapping the whole sky once every six months in 102 bands of near-infrared light."
- "Your challenge is to create a public-facing web tool to display images of the sky from the SPHEREx mission, making it easy for anyone to quickly see how they change over time. Users will enter the coordinates of a patch of sky (Right Ascension and declination). Your tool will display a series of images of that patch like a little video, making it easy to spot moving objects."
- "Test your tool on Barnard's Star, Epsilon Indi B (a pair of brown dwarfs orbiting a star), WISE 0855 (a fast-moving brown dwarf Right Ascension 08h55m10.831s, declination -7d14m42.53s), and variable stars RW Aurigae and R Draconis."
- Potential considerations include: easy updates with the latest data releases; display the 102 bands; separately add the six detector arrays; spectra on the fly; add/subtract images at different times; configurable field of view; Gaia/WISE overlays; URL coordinate query; metadata/contamination flags; Astropy/Aladin.
- "Resources will be available on Friday, November 13."

The WISE 0855 coordinates on the page are the **reference** position:

```text
08h55m10.831s = 133.795129°   (RA)
-7d14m42.53s  =  -7.245147°   (Dec)
```

These match `ra_ref`/`dec_ref` (2010.0) in the roadmap, not the 2025.8 propagated position.

### 2.2 Participant FAQ

Source: <https://www.spaceappschallenge.org/resources/participant-faqs>

Confirmed:

- Dates: November 14–15, 2026.
- "A summary of each challenge will be released on September 17, followed by challenge statements on October 28... Resources for each challenge will be published on November 13. Teams **are not allowed** to begin working on the challenges prior to the hackathon."
- Project Submission Guide and Judging and Awards Guide: November 13.
- SI definition and disclosure: "Participants may use SI tools to accelerate innovation... Each team's project submission must include a description of how SI tools were used during the development of their project."
- Universal Event is virtual/asynchronous, November 14–15.

Not yet confirmed by the 2026 FAQ (recheck on November 13):

- Maximum team size.
- Open-source license requirement.
- Whether the 2026 judging weights are still Impact/Creativity/Validity/Relevance at 25% each.
- Exact video/slide deliverables.

---

## 3. IRSA data access

### 3.1 TAP (primary)

Endpoint: `https://irsa.ipac.caltech.edu/TAP`

The live `TAP_SCHEMA.columns` query returned 171 columns across these tables:

```text
spherex.artifact
spherex.obscore
spherex.observation
spherex.plane
spherex.provenance_input
```

Relevant confirmed columns:

```text
spherex.artifact: artifactid, contentchecksum, contentlength, contenttype,
                  planeid, producttype, releasetype, uri
spherex.plane:    planeid, poly, time_bounds_lower, time_bounds_upper,
                  energy_bandpassname, dataproducttype, datarelease,
                  calibrationlevel, quality_flag, position_samplesize
```

`a.uri` is **relative**, for example:

```text
ibe/data/spherex/qr2/level2/2025W19_1B/l2b-v20-2025-241/3/level2_2025W19_1B_0116_1D3_spx_l2b-v20-2025-241.fits
```

Prepend `https://irsa.ipac.caltech.edu/` to build the access URL.

`p.energy_bandpassname` values are `SPHEREx-D1` … `SPHEREx-D6`.

`p.datarelease` is a public-release **date**, not a QR label. Detect the release from `a.uri` (`/dr1/`, `/qr2/`, `/qr3/`); the current build recognizes `/dr1/` and `/qr3/` and labels DR1 as `DR1`/`spherex_dr1`.

Verified query:

```sql
SELECT 'https://irsa.ipac.caltech.edu/' || a.uri
         || '?center={ra},{dec}&size={size}' AS cutout_uri,
       p.time_bounds_lower AS mjd_obs,
       p.time_bounds_upper AS mjd_obs_upper,
       p.energy_bandpassname AS detector_band,
       p.planeid,
       a.uri,
       a.contentlength,
       p.datarelease
FROM spherex.artifact a
JOIN spherex.plane p ON a.planeid = p.planeid
WHERE 1 = CONTAINS(POINT('ICRS', {ra}, {dec}), p.poly)
  AND a.producttype = 'science'
  AND a.contenttype = 'image/fits'
ORDER BY p.time_bounds_lower ASC
```

Without the `a.producttype='science'` / `a.contenttype='image/fits'` filters, calibration artifacts can enter the result set.

### 3.2 SIA2 (fallback)

Endpoint pattern:

```text
https://irsa.ipac.caltech.edu/SIA?COLLECTION=spherex_qr3&POS=circle+{ra}+{dec}+{radius}&RESPONSEFORMAT=json
```

Collections:

```text
spherex_qr3, spherex_qr3_deep, spherex_qr2, spherex_qr2_deep
```

Observed on 2026-11-08:

- QR3 query for WISE 0855 (0.1°): **0 rows**.
- QR2 query for WISE 0855 (0.1°): **297 rows**.
- Response format: VOTable-in-JSON; the results table includes `access_url`, `cloud_access`, `s_pixel_scale`, `s_resolution`, `t_min`, `t_max`, `energy_bandpassname`, `obs_collection`, `calib_level`, and `s_region`.
- A 0.1° QR3 query took about 13.5 s. TAP is the primary path; SIA2 is the fallback.

`access_url` is a full FITS URL. `cloud_access` is a JSON string with the AWS bucket/key/region.

### 3.3 Cutout

Pattern:

```text
{access_url}?center={ra},{dec}&size={size_deg}
```

Observed on 2026-11-08 with the QR2 file `2025W19_1B_0116_1D3`:

| Request | HTTP | Bytes | Content-Type |
|---|---|---|---|
| `size=0.02` | 200 | 5,060,160 | `application/fits` |
| `size=0.02d` | 200 | 5,060,160 | `application/fits` |

Both forms work. Earlier `503` responses returned the 25-byte body `"Server busy, retry later."`; they were transient, not a format error. Use timeouts, retries with backoff, and cache successful cutouts.

The cutout contains the **unmodified PSF cube**, so even a tiny spatial cutout is ~5 MB. Budget ~6 MB per cutout.

---

## 4. MEF HDU contract (verified)

Test file: QR2 cutout of `2025W19_1B_0116_1D3`, `center=133.75921,-7.24216`, `size=0.02`.

```text
HDU 0  PRIMARY    empty; data is None; 5 header cards
HDU 1  IMAGE      (12, 12) float32   MJy/sr
HDU 2  FLAGS      (12, 12) int32     bitmask
HDU 3  VARIANCE   (12, 12) float32   (MJy/sr)^2
HDU 4  ZODI       (12, 12) float32   MJy/sr
HDU 5  PSF        (121, 101, 101) float32; unmodified cube
HDU 6  WCS-WAVE   1 row x 3 columns (X, Y, VALUES)
```

> **DR1 update (2026-11-13):** the same cutout test on a DR1 file returned
> `IMAGE`, `FLAGS` (decompressed int32), `VARIANCE`, `ZODI`, **`EPSF`**
> (451-row binary table, 33 × 33, 5× oversampled), and `WCS-WAVE`. Full DR1
> MEFs store `FLAGS` as a Rice-compressed `CompImageHDU`. See §11.

Confirmation:

- `hdul[0].data is None` → never access `hdul[0].data`.
- `hdul["IMAGE"]`, `hdul["FLAGS"]`, `hdul["VARIANCE"]`, `hdul["ZODI"]`, `hdul["PSF"]`, `hdul["WCS-WAVE"]` all resolve by `EXTNAME`.
- `FLAGS` contained `2097152` (bit 21, `BIT_SOURCE`) on source pixels. Some pixels were `2097157` = `2097152 + 4 + 1` (`SOURCE | SUR_ERROR | TRANSIENT`). A `flags != 0` mask would have removed the target.
- `WCS(hdul["IMAGE"].header, fobj=hdul, key="W")` works. With `spectral_wcs.sip = None`, `pixel_to_world(6, 6)` returned **2.363159 µm** with bandwidth **0.058551 µm** for this D3 cutout.
- The cutout IMAGE/WCS carries SIP; the spectral WCS lookup is a `WAVE-TAB` table. Setting `sip=None` before `pixel_to_world` is mandatory.
- The PSF header has `XCTR_i`/`YCTR_i` (0-based original-image coordinates) for the 121 zones. Use the IRSA formula to select the plane:

```text
xpix_orig = 1 + xpix_cutout - CRPIX1A
ypix_orig = 1 + ypix_cutout - CRPIX2A
```

Then pick the nearest `XCTR_i`/`YCTR_i` and index the cube at `i - 1`.

---

## 5. Bitmask: Table 16, not Table 10

The Explanatory Supplement v2.0 (2026-08-25), **Table 16** ("Image pixel flags used in spectral images at Level 2") is the correct source. **Table 10** is "Non-Overflow Bloom Pixel Candidates" and is unrelated.

| Bit | Value | Name | Policy |
|---|---|---|---|
| 0 | 1 | `TRANSIENT` | Warn |
| 1 | 2 | `OVERFLOW` | Warn |
| 2 | 4 | `SUR_ERROR` | Hard |
| 6 | 64 | `NONFUNC` | Hard |
| 7 | 128 | `DICHROIC` | Warn (display); exclude/correct for photometry |
| 9 | 512 | `MISSING_DATA` | Hard |
| 10 | 1024 | `HOT` | Hard |
| 11 | 2048 | `COLD` | Hard |
| 12 | 4096 | `FULLSAMPLE` | Info only |
| 14 | 16384 | `PHANMISS` | Hard |
| 15 | 32768 | `NONLINEAR` | Hard |
| 17 | 131072 | `PERSIST` | Warn |
| 19 | 524288 | `OUTLIER` | Warn |
| 20 | 1048576 | `CROSSTALK` | Warn |
| 21 | 2097152 | `SOURCE` | **Never mask**; only exclude from background estimation |
| 22 | 4194304 | `GHOST` | Warn |
| 23 | 8388608 | `GHOST_FPA` | Warn (currently unused; subsumed into `GHOST_EXT`) |
| 24 | 16777216 | `GHOST_EXT` | Warn |
| 25 | 33554432 | `STREAK` | Warn |
| 26 | 67108864 | `BLOOM` | Hard |
| 27 | 134217728 | `SNOWBALL` | Hard |
| 28 | 268435456 | `HALO` | Hard |
| 29 | 536870912 | `SATELLITE_HALO` | Hard |

Updated constants:

```python
HARD_BAD_MASK = (
    (1 << 2) | (1 << 6) | (1 << 9) | (1 << 10) | (1 << 11) |
    (1 << 14) | (1 << 15) | (1 << 26) | (1 << 27) | (1 << 28) | (1 << 29)
)

ARTIFACT_WARNING_MASK = (
    (1 << 0) | (1 << 1) | (1 << 7) | (1 << 17) |
    (1 << 19) | (1 << 20) | (1 << 22) | (1 << 23) | (1 << 24) | (1 << 25)
)

BIT_SOURCE = 1 << 21
BIT_FULLSAMPLE = 1 << 12
```

Notes:

- Bit 23 (`GHOST_FPA`) is currently unused and "will be removed in Year 2 processing." It is included in the warning mask for forward compatibility; no current data should set it.
- `DICHROIC` is a warning for the displayed image, but for coadds and spectrophotometry the pixels should be excluded or throughput-corrected.
- The background-estimation mask remains `HARD_BAD_MASK | ARTIFACT_WARNING_MASK | BIT_SOURCE`.

---

## 6. Coverage on 2026-11-08

Counts are **science artifacts** (one row per detector/plane), not unique exposures. Query: TAP `CONTAINS(POINT(...), p.poly)` with `a.producttype='science'`.

| Target | QR2 | QR3 | Total | MJD range | Months observed |
|---|---:|---:|---:|---|---|
| `wise_0855` | 256 | **0** | 256 | 60800.700–61174.287 (2025-05-05–2026-05-14) | 2025-05, 2025-10, 2025-11, 2025-12, 2026-04, 2026-05 |
| `barnards_star` | 240 | 119 | 359 | 60902.865–61305.628 (2025-08-15–2026-09-22) | 2025-08/09/10, 2026-03/04/05, 2026-08/09 |
| `eps_indi_b` | 325 | 120 | 445 | 60789.856–61315.478 (2025-04-24–2026-10-02) | 2025-04/05/06/09/10/11, 2026-04/05/09/10 |
| `rw_aurigae` | 224 | 109 | 333 | 60919.420–61299.896 (2025-09-01–2026-09-16) | 2025-09, 2026-02/03, 2026-09 |
| `r_draconis` | 1760 | 723 | 2483 | 60789.880–61310.291 (2025-04-24–2026-09-27) | 2025-04 through 2026-09 (near-NEP deep coverage) |

Implications:
- **Historical (2026-11-08, superseded by §11):** do not assume QR3 for every target. WISE 0855 used QR2 in revision 2; revision 3 now uses **DR1** for all three WISE epochs and no QR2.
- All five have at least two epochs. Compute the 6-month grouping from `p.time_bounds_lower` at runtime; do not hardcode four epochs.
- R Draconis has very deep coverage near the North Ecliptic Pole; expect many visits and possible saturation.

---

## 7. Target coordinate validation

Propagation used `astropy.coordinates.SkyCoord.apply_space_motion` to decimal year **2025.8**, with `pm_ra_cosdec`/`pm_dec` in mas/yr and the reference epoch in the table. Δ is (astropy − documented) in arcseconds; RA Δ includes `cos(dec)`.

| Target | Reference (epoch) | Documented 2025.8 | Astropy 2025.8 | Δ (″) | External check |
|---|---|---|---|---|---|
| `wise_0855` | 133.79513, −7.24515 (2010.0) | 133.76010, −7.24220 | **133.759214, −7.242164** | **−3.16, +0.13** | CatWISE moving detections with PM ≈ −8.0, +0.5…+1.0 arcsec/yr; Gaia DR3 has no source (expected). The documented value matches 2025.4, not 2025.8. |
| `barnards_star` | 269.4521, +4.6934 (J2000) | 269.4463, +4.7676 | 269.446335, +4.767668 | +0.13, +0.25 | Gaia DR3 `4472832130942575872`: PM −801.551, +10362.394 mas/yr; parallax 546.976 mas; G = 8.194; ref epoch 2016.0. Confirmed. |
| `eps_indi_b` | 331.04415, −56.78284 (J2000) | 331.0962, −56.8005 | 331.096271, −56.800509 | +0.14, −0.03 | No Gaia DR3 source within 0.01° of the B coordinates. Gaia A `6412595290592307840`: PM +3966.661, −2536.192 mas/yr; parallax 274.843 mas. Close to the documented B PM (+3982.0, −2466.8); confirm B's PM with the discovery paper. |
| `rw_aurigae` | 76.95607, +30.40133 (J2000) | 76.9561, +30.4011 | 76.956092, +30.401134 | −0.03, +0.12 | Gaia DR3 `156430822114424576`: PM +2.641, −27.398 mas/yr; parallax 6.406 mas; G = 12.184. Confirmed. |
| `r_draconis` | 248.1676, +66.7550 (J2000) | 248.1674, +66.7548 | 248.167351, +66.754778 | −0.07, −0.08 | Gaia DR3 `1648328016354496384`: PM −20.643, +6.149 mas/yr; parallax 1.251 mas; G = 6.374. Position confirmed; PM differs from the documented −13.7, −31.0. Mira astrometry is pulsation-sensitive; treat the PM direction as low-confidence. |

**Decision:** use `133.75921, −7.24216` for WISE 0855's 2025.8 query center. The correction is 3.2″ (about half a native 6.15″ pixel); it matters for the reticle and the "2025.8" contract, even though the 0.2° field still covers the old position.

---

## 8. Local toolchain

### 8.1 Python

- Python 3.11.9 installed via `winget` (per-user).
- Shared venv: `<local-project-parent>/.venv311` (outside the repo; all four worktrees can use it).
- `backend/requirements.txt` installed successfully with:
  - `astropy 8.0.2`, `numpy 2.4.6`, `scipy 1.17.1`
  - `reproject 0.21.0`, `photutils 3.0.0`, `sep 1.4.1`
  - `fastapi 0.162.2`, `uvicorn 0.54.0`, `pydantic 2.14.3`
  - `pyvo 1.10.0`, `httpx 0.28.1`, `diskcache 5.6.3`, `pillow 13.0.0`
  - `pytest 9.2.0`, `pytest-asyncio 1.4.1.post1`
- The system default `python` is 3.14 and does **not** have Astropy. Use the venv explicitly:

```powershell
..\.venv311\Scripts\python.exe -m pytest backend/tests -v
```

### 8.2 Docker

- Docker Desktop 4.98.0 is installed, but `com.docker.service` cannot be started without administrator rights (`Access is denied`). The Windows CLI exists at `C:\Program Files\Docker\Docker\resources\bin\docker.exe`.
- Docker Engine **29.1.3** was installed inside WSL2 Ubuntu 26.04; Docker Compose **2.40.3** is available. Use the WSL engine for builds.
- Tested: `docker build`, `docker run`, and mounting the repo at `/mnt/c/...`.
- Use:

```powershell
wsl -d Ubuntu -u root -- docker build -t skyblink .
wsl -d Ubuntu -u root -- docker compose up
```

- The WSL engine uses the legacy builder by default; install `docker-buildx` inside WSL if BuildKit is needed.

### 8.3 Frontend

- Node **24.13.0**, npm **11.6.2**.
- No `package.json` yet; dependencies are installed at H+0.

---

## 9. Open questions to freeze at O1

The backend agent expanded these into 12 questions. Full decisions: `docs/decisions/o1-contract-decisions.md`.

1. **DICHROIC/spectrum:** add `clean_fraction` + `is_used_in_photometry`; `flags` is the extraction-center flag; `is_flagged_bad` stays hard-only; aperture fixed at 12.3″.
2. **`flag_summary` aggregation:** union of warning flags, max per-band artifact fraction, any-band source bit.
3. **Release-specific/mixed provenance:** per-epoch collection/release on `/sky` and `/spectrum`; top-level `mixed`/`QR2+QR3` at O1 (historical; now `mixed`/`DR1+QR3`).
4. **Arbitrary-coordinate asset URLs:** `live_<hash>`; `bands`/`epochs` `all`/empty sentinels; overlays optional.
5. **LAW 8 normalization:** static-source p99.5 normalization with a global reference epoch, per-band earliest fallback, `reference_epoch="mixed"` when refs differ, positive clamp, and fallback; coadds share the per-band scales.
6. **`/spectrum.provenance.zodi_subtracted`:** add.
7. **`API_CONTRACT_VERSION`:** Orchestrator-owned `backend/models/version.py`; canonical import `models.version`; O1 = 1.0.0; current = 1.2.0 (1.1.0 was the additive Phase 2 freeze; 1.2.0 added DR1 release values).
8. **Epoch IDs/differences/`mjd_mean`/`crval`:** `{year}_E{n}` on the full set; adjacent-only differences; exposure-weighted midpoints; `crval` = target/query center; `epochs` filters only output; catalog `size` is a client-side crop.
9. **HALO:** hard/NaN default; S2 measures R Draconis `halo_fraction`; if >0.05 or the target aperture is affected, use the display-only mask with HALO in the overlay/CAUTION while keeping it in `PHOTOMETRY_EXCLUDE_MASK`.
10. **R Dra/Eps Indi B proper motions:** documented catalog values; Gaia caveats in §10 above.
11. **Native pixel box:** on the 3.075″/px canvas, the 6.15″ native pixel is **2 × 2 canvas pixels**, not 1 × 1.
12. **O1 models and development fixtures (historical plan):** originally planned for H+0 under the no-pre-work rule; the Berlin Local Event exception allowed earlier work. The fixtures are explicit opt-in only and are never loaded automatically.

---

## 10. November 13 checklist

- [x] Inspect the challenge Resources tab; capture any data links NASA adds. **Done 2026-11-13**; four NASA + four CSA resources, in [`resource-release-2026-11-13.md`](../reference/resource-release-2026-11-13.md).
- [ ] Read the Project Submission Guide and Judging and Awards Guide. **Announced for Nov 13; files not publicly retrievable at check time.**
- [ ] Confirm the open-source license requirement (MIT/BSD-3-Clause).
- [ ] Confirm the video/slide deliverable and the exact SI disclosure template.
- [ ] Confirm team-size and Local Event rules.
- [ ] Confirm judging weights (the 25% × 4 structure is a 2025 reference).
- [x] Re-run TAP coverage for all five targets; recheck WISE 0855 QR3. **Done:** QR3 still absent for WISE 0855, but **DR1 now covers it** (258 artifacts); TAP returned DR1+QR3 only.
- [x] Compute and record the 6-month epoch grouping per target. **Done in revision 2; re-measured in revision 3 (same epoch sets, DR1+QR3 labels).**
- [ ] Confirm venue internet, deployment platform, and admin/Docker access.
- [x] Recheck the cutout service and the IRSA TAP/SIA endpoints. **Done 2026-11-13:** DR1 cutout works; `EPSF` replaces `PSF`; SIA `COLLECTION=spherex_dr1` works.
- [x] Lock scope and freeze the API contract at O1. **Scope locked; contract 1.1.0 frozen; B10 bumped it to 1.2.0 and is implemented.**

---

## 11. 2026-11-13 recheck — DR1 and official resources

**Status:** completed. Full source list and decisions: [`resource-release-2026-11-13.md`](../reference/resource-release-2026-11-13.md).

### 11.1 Official Resources tab

The challenge page was last published **2026-11-13 03:46 UTC**. It lists:

- **NASA:** IRSA SPHEREx, SPHEREx Tutorial Notebooks (now DR1-based), WiseView, Gaia DR3.
- **CSA:** NEOSSat overview, CADC, NEOSSat Data Tutorial, NEOSSat Dataset.

The CSA block is the main new partner material. It is optional context for SkyBlink; the core challenge and the five targets are unchanged.

### 11.2 DR1 coverage and structure

TAP on 2026-11-13 returned **DR1 + QR3 only** (no `/qr2/` rows in the five-target query):

| Target | DR1 | QR3 | DR1 MJD | QR3 MJD |
|---|---:|---:|---|---|
| WISE 0855 | 258 | 0 | 60800.7–61174.3 | — |
| Barnard's Star | 239 | 119 | 60902.9–61165.1 | 61268.6–61305.6 |
| Epsilon Indi B | 338 | 120 | 60789.9–61164.1 | 61305.2–61315.5 |
| RW Aurigae | 226 | 109 | 60919.4–61111.0 | 61285.1–61299.9 |
| R Draconis | 1,638 | 855 | 60789.9–61173.2 | 61176.4–61310.3 |

DR1 is the reprocessed QR2 set, intended to be used with QR3. DR1 also includes an all-sky **102-channel** cube. Revision 3 (**S7**) now uses **DR1+QR3** for all five targets; no QR2 remains in the current cache.

### 11.3 DR1 file-layout changes

- HDU 5 is **`EPSF`** (binary table, 441 rows full frame; 451 in the tested cutout; 33 × 33, 5× oversampled) instead of the QR2 `PSF` cube.
- Full DR1 MEFs store `FLAGS` as a Rice-compressed `CompImageHDU`; Astropy reads it transparently. The IRSA cutout service returns `FLAGS` decompressed as int32.
- DR1 URIs contain `/dr1/`. At check time the release detector did not recognize them and labelled DR1 as `release="unknown"`; **B10** fixed this before the revision-3 rebuild.
- SIA collections: `spherex_dr1`, `spherex_dr1_deep`, `spherex_qr3`, `spherex_qr3_deep`.

A real DR1 cutout (0.02°, WISE 0855) was 4,037,760 bytes and returned in 8.6 s with `IMAGE`, `FLAGS`, `VARIANCE`, `ZODI`, `EPSF`, `WCS-WAVE`.

### 11.4 Current state after B10/S7 (2026-11-13)

- **B10 (`3c642ef`)** implements `/dr1/` detection and contract **1.2.0**; DR1 responses are `release="DR1"`, `collection="spherex_dr1"`, and mixed epochs are `DR1+QR3`. **79 tests passed at B10 merge; the current suite is 83.**
- **S7 (`664977e`)** rebuilt the golden cache to **revision 3** from live **DR1+QR3**: 5/5 targets, 17/17 telemetry sidecars, 0 failures, 38 min 41 s, 170 transient IRSA 503 retries. **12,870,733 bytes / 442 files**; no QR2.
- **Measured used/total spectra:** WISE 0855 **158/164**; Barnard's Star **2/215**; Epsilon Indi B **228/246**; RW Aurigae **102/216**; R Draconis **0/240**.
- **Per-epoch releases:** WISE 0855 DR1×3; Barnard's Star DR1, DR1, DR1+QR3; Epsilon Indi B DR1, DR1, DR1, DR1+QR3; RW Aurigae DR1, DR1, QR3; R Draconis DR1, DR1, DR1, DR1+QR3.
- **Container:** `skyblink:final` 844 MB, healthy at 105.7 MiB idle, health version **1.2.0**, five-target smoke **5/5**.

---

## 12. References

- NASA Space Apps 2026 — Planet X and SPHEREx: <https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/>
- NASA Space Apps 2026 Participant FAQs: <https://www.spaceappschallenge.org/resources/participant-faqs>
- SPHEREx Archive at IRSA — Data Access: <https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access>
- SPHEREx Archive at IRSA — Data Products: <https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products>
- SPHEREx Explanatory Supplement v2.0 (2026-08-25), Table 16: <https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp_QR.pdf>
- IRSA TAP: <https://irsa.ipac.caltech.edu/TAP>
- IRSA SIA2: <https://irsa.ipac.caltech.edu/SIA?>
- IRSA cutouts: <https://irsa.ipac.caltech.edu/ibe/cutouts.html>
- Gaia DR3 and AllWISE/CatWISE tables via IRSA TAP (`gaia_dr3_source`, `allwise_p3as_psr`, `catwise_2020`).
- Astropy: <https://docs.astropy.org/>
