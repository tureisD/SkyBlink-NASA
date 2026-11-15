# AGENTS.md — SPHEREx SkyBlink Multi-Agent Contract

**Project:** SPHEREx SkyBlink — NASA Space Apps Challenge 2026, *Planet X and SPHEREx*  
**Repository:** Monorepo — `backend/` (Python 3.11, FastAPI), `frontend/` (React 18, TypeScript, Vite), `scripts/` (data precomputation), `golden_cache/` (offline frames)  
**GitHub:** <https://github.com/tureisD/SkyBlink> (account `tureisD`) — **private** as of 2026-11-14; make it public or grant judge access before judging if required.
**Document:** v1.17 (2026-11-15 illustrated documentation and help; API contract 1.6.0)
**Companion:** `ROADMAP.md` — product, science, scope, and 48-hour plan.
**Status:** Execution contract. Changes require Orchestrator approval and a contract version bump.

**v1.17 decision:** The user requests a refreshed README, video guide and illustrated in-app help using the current interface. The Orchestrator approves three explicitly inventoried educational screenshots under `frontend/public/help/guide-{workspace,compare,spectrum}.png`, shared by all three guides. They show unchanged recorded real responses with numbered control/interpretation annotations; they are documentation, never observation inputs, fallback frames or proof of a new acquisition. Only these reviewed image paths and their hashes may be added to UI packaging approval; existing observation approvals remain unchanged. Frontend owns Help content/styles and its build allowlist; science owns capture scripts, these three public images, README and inventory verification; root owns video/policy and integration review. Historic captures and scientific record bytes remain unchanged. Main workspace layout, API 1.6.0 and image method 13 remain unchanged.

**v1.16 decision:** The user requests richer styling and animations with no layout changes. The Orchestrator approves layered navy surfaces, cyan/indigo accents, refined borders/shadows and restrained control/entrance animation while preserving existing geometry, responsive behavior, square edges, content and scientific image rendering. Reduced motion disables decorative animation. Frontend owns the stylesheet and its import; root owns independent browser geometry/visual verification and this policy note. API 1.6.0, image method 13, acquisition choices and all scientific semantics remain unchanged. The historical zero-glow palette and fixed control-transition prescription in section 5.7 do not constrain this authorized styling pass.

**v1.15 decision:** The user requests another attempt to restore archive discovery, followed by documentation organization. Renewed supported TAP and official Explorer routes returned upstream errors; no live-search repair is claimed and no speculative acquisition transport is adopted. The Orchestrator approves grouping supporting documentation into guides, plans, decisions, reference, verification, research and phase-organized evidence while retaining the two active planning paths. Scientific JSON and screenshot bytes remain unchanged; old paths inside immutable records resolve through `docs/reference/file-locations.json`. Root owns the coordinated file moves and repository/script/Docker reference updates; science independently verifies hashes, inventory and current readers. Only the mutable inventory's location references change; observation approval hashes are preserved. Documentation references in processing source may change its fingerprint, so restart the development API after the final source freeze. API 1.6.0 and image method 13 remain unchanged. Begin at [the documentation index](docs/README.md).

**v1.14 decision:** The user requests investigation and repair of repeated default archive-search failures. Independent SIA/TAP probes reproduce upstream discovery failure, which remains distinct from local acquisition behavior. A fresh known-exposure control exposed a second issue: missing partners exhausted an 18-second candidate round without receiving a second attempt despite remaining search time. The Orchestrator approves image method/cache revision 13 for one bounded completion pass over promising incomplete pairs after the initial candidate sweep, retaining at most two batch attempts per input and the existing overall search/processing reserve. Successful input bytes are reused only within that same fresh job; failed attempts and final missing inputs remain separately recorded. No complete scientifically rejected pair is retried to obtain a favorable result. Scientific thresholds, archive-first defaults, API 1.6 field types, explicit known/saved choices and legacy saved assets remain unchanged. Backend owns runtime and regression tests; science owns replay adapters and independent verification; root owns policy/docs and process integration. This change does not claim to repair live metadata discovery. See [decision](docs/decisions/phase6-pair-download-recovery-decision.md) and [current diagnosis](docs/verification/phase6-live-discovery-diagnosis.md).

**v1.13 decision:** The user authorizes Phase 6, catalog spectrum repair and a compact boxy workspace. The Orchestrator approves moving the target name and Observe/Compare/Spectrum/Evidence navigation into the left rail, retaining only source and position from the former Fields content, and restoring straight-edged workstation styling while preserving current accessibility, provenance, recovery and comparison controls. Frontend owns all application UI; backend owns spectrum/runtime fixes and targeted tests; science owns release scripts, packaging, independent QA, README and release verification documentation; root owns policy, integration and external release coordination. Reproduce retrieval failures separately from null/excluded photometry, and retain scientific eligibility and explicit source choices. Phase 6 requires measured current container/public-access evidence; historical successes are not certification. Missing hosting/project details may leave external gates open, which must be reported explicitly. API changes require a coordinated additive decision; existing API 1.6 remains until then.

**v1.13 integration scope:** The user explicitly defers publishing, public-host verification and submission. Local release work continues; an unavailable Docker engine must remain an unverified gate. Explicit spectrum-only recovery may set `spectrumDiscovery=known` in the view recipe while image acquisition retains its own mode; drawer, audio, report, URL and source labels must agree and never switch silently. API 1.6 field types stay unchanged. Root approves process-local admission for at most two distinct live builds, preserving same-query sharing, with typed busy/storage errors and retry guidance. Storage checks are conservative admission thresholds (8 GiB of runtime stores, 512 MiB reservation per active build, at least 1 GiB free), not a hard filesystem quota; immutable lineage is never deleted automatically.

**v1.12 decision:** The user requests repair of the reproduced all-catalog discovery outage. The Orchestrator approves explicit opt-in known-exposure retrieval under [API 1.6.0](docs/decisions/known-exposure-contract-decision.md). Default archive discovery stays live; no automatic fallback is allowed. Known mode uses a bounded verified metadata index and fresh upstream FITS downloads, preserves all processing gates, records partial historical discovery and distinct work/source identities, and supports only corrected catalog positions. Backend owns acquisition/routes/tests, frontend owns mode selection and consistent requests, science owns the real metadata index, packaging and validation, and root owns models/version/policy integration. Earlier complete-discovery results do not establish current upstream availability. See [outage evidence](docs/verification/phase5-discovery-outage-verification.md).

**v1.11 decision:** The user requests repair of repeated catalog single-epoch/incomplete-download responses, reconsideration of official acquisition alternatives, sidebar-local hamburger controls, compact acquisition notifications and a more prominent image. The Orchestrator approves diagnosis against the actual development server plus fresh-process verification, bounded acquisition fixes and measured use of official alternative transports when justified. Fresh archive acquisition, real-only inputs and measured compatibility/quality gates remain required; neither a spectral channel nor a mirrored copy is another temporal epoch. Any changed processing identity must be recorded. API 1.5 field types remain unchanged. For this task the discovery agent owns backend runtime acquisition and its targeted regression tests; frontend owns application UI; science owns validation scripts/browser QA and the dedicated verification report; root owns integration, policy and current-status documentation. Notifications may be dismissed/reopened outside the image, while essential single-epoch status and disabled-play reasons remain accessible. Current verification is recorded in `docs/verification/phase5-catalog-reliability-and-viewer.md`; this authorization is not a claim of completion.

**v1.10 decision:** The user requests a central blink viewer with useful sidebars and a clear account of remaining limitations beyond release/publication. The Orchestrator approves a responsive three-column observing workspace: field navigation at left, dominant image/comparison at center, interpretation and tools at right. Rails may collapse and a focus view may expand the image; these are presentation states, not scientific selection changes. Mobile must provide readable stacked/panel access rather than squeezing three columns. Source, dates, comparison limitations and essential playback controls remain visible; persistent canvas behavior, API 1.5 and image method 12 remain unchanged. The frontend agent owns this shell/components/styles work except spectrum internals; the science agent owns independent browser verification and capture evidence; the discovery agent owns the new limitations/next-steps document with read-only science review. Root owns integration, current-status clarification and the audit plan. New science improvements are proposals, not authorized scientific promotion.

**v1.9 decision:** The user authorizes a further visual/QoL refinement and repair of live single-epoch comparison failures. The Orchestrator approves retaining archive footprint metadata for candidate ranking and balanced cross-epoch download rounds, subject to the unchanged full-field wavelength/bandwidth and usable-pixel gates. Geometric similarity is never scientific acceptance. The backend agent owns services/core/routers/tests for this repair; the frontend agent owns the visual system, recovery/history and hooks/lib except spectrum semantics; the science agent owns spectrum components/semantics and independent browser verification. API 1.5 public field types and the real-only policy remain. New selection behavior receives a processing/cache revision; historical replay records retain their recorded source. Recent-query UI history contains query settings only, never automatically reused observation data.

**v1.8 decision:** The user authorizes Phase 5. The Orchestrator approves the task-oriented observing workspace in `docs/audit-and-remediation-plan-2026-11-14.md`, superseding the historical tiny uppercase typography, dense rails and HUD styling requirements in section 5.7 and the old frontend prompt. Initial and shared views are paused; essential navigation remains available through loading/failure; advanced tools use progressive disclosure. Source, comparison validity and measurement eligibility remain separate. API 1.5.0, science processing, real-only policy and persistent canvas rendering are unchanged. Frontend implementation ownership is subdivided for this phase: frontend agent owns shell/components/styles except spectrum; discovery agent owns hooks/lib except semantics; science agent owns spectrum components/semantics and independent browser QA. Root owns integration and documentation. Human usability and full accessibility acceptance must be reported separately from automated/internal checks.

**v1.7 decision:** The user explicitly requests upstream acquisition and broader scientific verification. The Orchestrator approves [API 1.5.0 source and eligibility semantics](docs/decisions/phase4-online-contract-decision.md), coordinated with backend/science/frontend. Archive is the default for all coordinates and named targets; it uses corrected astrometry and bypasses application product/input cache reads. Saved mode is explicit, catalog-only and retains historical coordinates. No automatic fallback. Partial discovery/downloads remain explicit; one real epoch may be displayed without differences when bounded comparison search cannot establish a pair. Current native eligibility requires a full clean aperture inside the image, at least ten clean local-annulus pixels, supported field background and a non-hard-bad center. Finite excluded sums remain exploratory. Center-pixel/constant-WCS integration remains; the proposed exact/SAPM refinement failed its primary gate and is not adopted. The secondary existing-method baseline passed six evaluable groups in four fields/two detectors; this is restricted evidence, not all-sky or crowded-source certification. Earlier conflicting cache-first, single-epoch and 0.5 eligibility rules below are historical. See [current evidence](docs/verification/phase4-online-verification.md).

**v1.6 decision:** The user authorized audit Phase 4. The Orchestrator approves additive API 1.4.0 fields and stored creation-time semantics in [the contract decision](docs/decisions/phase4-contract-decision.md); backend and frontend changes are coordinated. New products retain input hashes, exact extraction positions, actual UTC observation bounds, method/source/environment identity and immutable fingerprint-named lineage links. Corrected catalog solutions are staged explicitly and must not be paired with old assets. Independent holdout evidence is insufficient for fractional-aperture adoption or scientific promotion; the native center-pixel method remains. Replaying arithmetic does not validate astrophysical interpretation. See [Phase 4 verification](docs/verification/phase4-verification.md) and [result vocabulary](docs/guides/result-meaning.md). Golden revision 3 is unchanged and remains legacy/unvalidated.

**v1.5 decision:** The user authorized audit Phase 3. The Orchestrator approves separate display and measurement arrays: native hard-plus-warning pixels are excluded before measurement interpolation/coaddition, while warnings remain visible in display layers. Background estimation requires spatial support; a masked 2D plane is used only when the fixed held-out improvement gate passes, otherwise a supported scalar is used. Unsupported subtraction produces no usable measurement. New sky builds select one exposure per band/epoch, compatible wavelength and bandwidth over exact retained output pixels, with at most 30 days across bands in each epoch; output dates and internal lineage record the actual selection. This does not guarantee simultaneous bands, calibrated uncertainties, or astrophysical variability. Median-background uncertainty is included approximately. These changes preserve API fields/types; API 1.3.0 records the stricter unsupported-background eligibility rule. See `docs/decisions/phase3-contract-decision.md`. Saved revision-3 assets and query coordinates await the coordinated Phase 4 correction/rebuild; the API labels legacy comparisons unvalidated. WISE 0855 reference-epoch and R Draconis proper-motion discrepancies are documented in `docs/verification/phase3-calibration-audit.md`. See `docs/verification/phase3-verification.md` for measured acceptance, including failed and insufficient cases.

**v1.4 decision:** The user authorized audit Phase 2; the Orchestrator approves exact frontend TAN coordinates, complete bounded discovery with remaining-budget SIA fallback, and live candidate selection. Live sky defaults to searching the latest three full-set epochs and up to three visits per detector/epoch for a comparable pair. A single epoch is returned only when discovery finds one; incompatible samples return an explicit limitation. The visual wavelength gate samples nine field positions and is not scientific variability validation. Same-query concurrent builds share work within one server process. API field names/types and schema version are unchanged. See `docs/verification/phase2-verification.md` for measured results and outstanding live acceptance.

**v1.3 decision:** The user authorized audit Phase 1 on 2026-11-14; the Orchestrator approves removal of product fixtures and illustrative spectra. No API field is renamed, removed, or retyped. Historical task records below do not authorize reintroducing fixtures. Generated test inputs are isolated, inventoried, and excluded from runtime; see `docs/guides/real-data-policy.md`. This records the Phase 1 decision; the v1.4 decision above supersedes its Phase 2 status. Previous container verification predates this cleanup.

> **New to the project?** Start with `README.md` (especially “Start here”) and `docs/guides/contributing.md`. This file is the technical build contract for the multi-agent workflow; you do not need it to use the app.
**Current state (2026-11-15):** Policy v1.15 / API **1.6.0**, image method/cache **13**. Default discovery currently fails independently of the app; [current diagnosis](docs/verification/phase6-live-discovery-diagnosis.md) separates that unresolved failure from bounded incomplete-pair recovery. A new explicit known-mode WISE request returned a matched real pair; it does not establish live-search recovery. Earlier local Phase 6 production-serving, real-only, catalog-spectrum and browser checks retain their recorded scope in [Phase 6 verification](docs/verification/phase6-verification.md). Compact boxy UI, independent spectrum recovery and keyboard controls preserve source/measurement distinctions. The current container remains unverified; publishing/public-host/submission work is explicitly deferred. Scientific validation remains scoped and legacy saved assets are unchanged.

---

## 0. Read order and precedence

1. Read `ROADMAP.md` §1–§5 for product context.
2. Read this file completely before editing code.
3. Read `ROADMAP.md` §14 for unresolved data/submission questions.
4. If a task prompt conflicts with a guardrail in this file, **stop and ask the Orchestrator**.
5. If this file conflicts with the official NASA challenge or IRSA documentation, the official source wins; escalate so this file can be corrected.

**Precedence:** Official challenge/IRSA docs → `ROADMAP.md` → `AGENTS.md` task prompts. If an earlier draft is quoted, treat this file as authoritative.

---

## 1. Non-negotiable laws

Every agent MUST obey these laws. Violating any of them causes silent scientific corruption, erases the demo targets, or breaks the live submission.

### LAW 1 — Never read `hdul[0].data`

SPHEREx Level 2 and IRSA cutout MEFs have an empty `PrimaryHDU` at index 0. `hdul[0].data is None`.

Always access science extensions by name:

```python
hdul["IMAGE"]      # HDU 1
hdul["FLAGS"]      # HDU 2
hdul["VARIANCE"]   # HDU 3
hdul["ZODI"]       # HDU 4
hdul["PSF"]        # HDU 5 in QR2 (121 × 101 × 101 cube); QR3/DR1 use EPSF
hdul["EPSF"]       # HDU 5 in QR3/DR1 (binary table; 441 rows full frame, 33 × 33, 5× oversampled)
hdul["WCS-WAVE"]   # HDU 6
```

Never rely on numeric indices alone; `EXTNAME` is the contract. **DR1 replaces the PSF cube with an EPSF binary table.** The normal pipeline does not require HDU 5; code that reads it must branch on `EXTNAME` and must not assume `hdul["PSF"]` exists.

### LAW 2 — Never mask `BIT_SOURCE`

`BIT_SOURCE` (Bit 21, `1 << 21` = `2097152`) marks pixels containing known catalog stars, galaxies, and brown dwarfs. `BIT_FULLSAMPLE` (Bit 12, `4096`) is informational.

- **Never** use `flags > 0` or `flags != 0` as a bad-pixel mask.
- Mask only `HARD_BAD_MASK` (see §4.2) to `NaN`.
- Exclude `BIT_SOURCE` **only** when estimating the local sky background.
- Surface `ARTIFACT_WARNING_MASK` in the Artifact Shield; do not mask it from the displayed image by default.

### LAW 3 — Set `spectral_wcs.sip = None`

When reading the spectral WCS:

```python
spectral_wcs = WCS(hdul["IMAGE"].header, fobj=hdul, key="W")
spectral_wcs.sip = None  # MANDATORY
wave_um, band_um = spectral_wcs.pixel_to_world(x, y)
```

Without this, Astropy attaches the spatial SIP distortion to the spectral lookup and returns corrupted wavelengths.

### LAW 4 — Subtract `ZODI` and local sky background

`hdul["IMAGE"]` does **not** have zodiacal light subtracted. Before coaddition or difference:

1. `img = IMAGE - ZODI`.
2. Estimate the residual 2D background on pixels that are **not** hard-bad, **not** warning-flagged, and **not** `BIT_SOURCE`.
3. Subtract that background.

Skipping this causes full-frame flashing between epochs and gradients in difference images.

### LAW 5 — Query at Epoch 2025.8 coordinates

High-proper-motion targets have moved significantly since their reference epochs. For the five catalog targets, always center TAP/SIA2/cutout queries on the propagated **2025.8** coordinates in `backend/core/targets.py`. For arbitrary user coordinates, use the user-supplied position.

- Barnard's Star: ~10.39″/yr → ~4.45′ since J2000.
- WISE 0855: ~8.15″/yr → ~2.1′ since 2010.
- Epsilon Indi B: ~4.68″/yr → ~2.0′ since J2000.

Pass both the reference coordinates and the 2025.8 coordinates to the frontend so the proper-motion reticle can be drawn.

### LAW 6 — Never re-mount the canvas on blink ticks

`BlinkCanvas.tsx` MUST:

- Pre-decode frames into `ImageBitmap` objects.
- Render through a persistent `requestAnimationFrame` loop.
- Read mutable state from a `useRef` mirror.
- Avoid React tree re-mounts or per-tick state updates.

The Canvas is the performance-critical path. React owns the HUD; the Canvas owns the pixels.

### LAW 7 — Honesty, real data, and photosensitivity

- **Real data only in normal operation.** A live request that fails returns a clean error. The frontend must **never** automatically load `frontend/public/mock/`, `golden_cache/fallback_*`, or any other fixture.
- Product fixtures, mock loaders, and illustrative model spectra are forbidden, including development opt-ins. The app accepts only explicit `is_simulated_fallback: false` provenance. Isolated generated test inputs are documented in the data inventory and never shipped as observations.
- Never fabricate ML confidence scores, probabilities, or spectra.
- Cap automatic blink playback at **8 FPS** (default **4 FPS**).
- Honor `prefers-reduced-motion`.
- No full-screen white flashes.
- State known limitations: 6.15″ blending, low SNR, artifacts, sparse epochs.

### LAW 8 — Share flux normalization across epochs

For blinking, frames of the same band across epochs MUST share a common background/star-based flux normalization. Otherwise static stars flicker and the user mistakes scaling changes for astrophysical variability.

- Compute the scale from static background/star percentiles, not from the target.
- Keep the raw flux statistics for difference mode.
- Document the normalization in the manifest.

### LAW 9 — The API contract is immutable

`AGENTS.md` §3 is the contract between backend and frontend. Neither agent may rename, remove, or change the type of a field without:

1. A written proposal in the PR.
2. Orchestrator approval.
3. A contract version bump.
4. Both agents updating their code and tests.

### LAW 10 — No cross-agent writes

Each agent writes only within its owned paths (§2). Cross-boundary changes go through the Orchestrator. Never edit another agent's files to "make it work."

---

## 2. Repository layout and ownership

```text
.
├── AGENTS.md                     # Orchestrator / contract
├── ROADMAP.md                    # Orchestrator
├── README.md                     # Science/validation agent
├── Dockerfile                    # Science/validation agent
├── docker-compose.yml            # Science/validation agent
├── backend/
│   ├── app/                      # FastAPI app factory, main.py
│   ├── core/                     # config, targets, flags
│   ├── models/                   # Pydantic schemas (contract)
│   ├── routers/                  # API routes
│   ├── services/                 # IRSA client, pipeline, spectrophotometry
│   ├── tests/                    # Science/validation agent
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/           # BlinkCanvas, TimelineDock, ArtifactShield, ...
│   │   ├── hooks/                # useUrlState, useFrames
│   │   ├── lib/                  # WCS helpers, colormaps
│   │   └── styles/
│   ├── public/
│   ├── index.html
│   ├── package.json
│   └── tsconfig.json
├── scripts/
│   ├── build_golden_cache.py
│   └── verify_real_data.py          # real-only packaging/inventory gate
└── golden_cache/
    └── {target_id}/
        ├── manifest.json
        ├── spectrum.json
        ├── *.webp
        └── ref_*.webp
```

The retired fixture generator, `frontend/public/mock/`, and `golden_cache/fallback_*` must not be restored. Product builds and asset serving reject those paths.

### 2.1 Ownership matrix

| Agent | Owns | May read | Forbidden writes |
|---|---|---|---|
| **Agent 0 — Orchestrator** | `ROADMAP.md`, `AGENTS.md`, `backend/models/**`, `docs/**`, `agents/prompts/**`, `agents/README.md`, `.opencode/**`, integration branches | Everything | — |
| **Agent 1 — Astro-backend** | `backend/app/**`, `backend/core/**`, `backend/services/**`, `backend/routers/**`, `backend/requirements.txt` | `backend/models/**`, `AGENTS.md`, `ROADMAP.md` | `frontend/**`, `scripts/**`, `golden_cache/**` |
| **Agent 2 — Sky-frontend** | `frontend/**` | `backend/models/**`, `AGENTS.md`, `ROADMAP.md` | `backend/**`, `scripts/**`, `golden_cache/**` |
| **Agent 3 — Science/validation** | `scripts/**`, `backend/tests/**`, `golden_cache/**`, `Dockerfile`, `docker-compose.yml`, `README.md` | All backend/frontend code | `backend/app/**`, `backend/core/**`, `backend/services/**`, `backend/routers/**`, `frontend/**` |

**Rule:** if a change is needed outside your paths, open a PR comment or ask the Orchestrator. Do not edit another agent's files.

---

## 3. Immutable API contracts

Current API version is **1.5.0**; archive/saved and eligibility semantics are defined in `docs/decisions/phase4-online-contract-decision.md`. The original Phase 4 additions below describe 1.4.0. Phase 4 adds optional observation ranges, measurement availability, channel lineage/reasons, telemetry semantics and analysis identifiers/links; product creation times come from stored metadata. See `docs/decisions/phase4-contract-decision.md` for the field contract. Historical products retain unknown lineage rather than fabricated records. The historical examples below retain their shapes. The Phase 3 decision supersedes the original eligibility predicate: no supported background means null flux/error and false `is_used_in_photometry`, even when the pixel-based `clean_fraction` is positive. `is_flagged_bad` remains hard-mask only. See `docs/decisions/phase3-contract-decision.md`.

> **Pre-O1 note (2026-11-08):** The O1 contract decisions — including `clean_fraction`, `is_used_in_photometry`, per-epoch collection/release fields, and `flux_normalization` — are recorded in `docs/decisions/o1-contract-decisions.md`. They are incorporated into this section at the H+0 O1 freeze; no application code or models are published before then.

All endpoints are under `/api/v1`. JSON is UTF-8. Units are explicit in field names or documented. All timestamps are ISO 8601 UTC.

### 3.1 Conventions

- **Coordinates:** decimal degrees, ICRS.
- **Flux:** `flux_ujy` in microjanskys; images internally in MJy/sr.
- **Wavelength:** micrometers.
- **Angles:** arcseconds for aperture/pixel scale; degrees for sky coordinates.
- **Booleans:** `is_*` or `has_*`.
- **Errors:** standard error envelope (§3.7).
- **CORS:** same origin in production; allow the frontend dev origin in development.
- **Caching:** `Cache-Control: public, max-age=3600` for golden assets; `no-store` for live queries.

### 3.2 `GET /api/v1/health`

```json
{
  "status": "ok",
  "version": "1.2.0",
  "irsa_reachable": true,
  "cache_entries": 42
}
```

### 3.3 `GET /api/v1/targets`

```json
{
  "targets": [
    {
      "id": "wise_0855",
      "name": "WISE 0855",
      "category": "Y4 Sub-Brown Dwarf (~250 K)",
      "ra_ref": 133.79513,
      "dec_ref": -7.24515,
      "ref_epoch": "2010.0",
      "ra_epoch2025": 133.75921,
      "dec_epoch2025": -7.24216,
      "pm_ra_mas_yr": -8118.0,
      "pm_dec_mas_yr": 680.0,
      "recommended_bands": [5, 6],
      "story_headline": "Coldest Known Object Outside the Solar System",
      "story_body": "At ~250 K, WISE 0855 emits almost no optical or short-NIR light. It is invisible in Gaia and SPHEREx Bands 1-4, then emerges in Bands 5 & 6 while moving across epochs."
    }
  ]
}
```

`pm_ra_mas_yr` is `μ_α cos δ`. Target IDs: `wise_0855`, `barnards_star`, `eps_indi_b`, `rw_aurigae`, `r_draconis`. The other four records follow the same schema; use the values in `ROADMAP.md` Appendix A.

### 3.4 `GET /api/v1/sky`

Query parameters:

| Parameter | Type | Required | Default | Notes |
|---|---|---|---|---|
| `ra` | float | yes | — | Degrees, ICRS. |
| `dec` | float | yes | — | Degrees, ICRS. |
| `size` | float | no | `0.2` | Degrees; clamp 0.05–0.2. Catalog targets: client-side crop of the full 240×240 (0.205°) golden grid (assets are size-independent). Live positions: cutout size; `wcs` still describes the full 240×240 grid; `query.size_deg` echoes the clamped request; `size` is part of the cache key. |
| `target_id` | string | no | — | One of the five IDs; enables golden cache. Requires `ra`/`dec` within 1.0″ of the target's 2025.8 coordinate; otherwise 422. |
| `epochs` | string | no | `all` | Comma-separated epoch IDs; filters returned `epochs`/`differences` only. IDs, reference epoch, adjacent pairs, and normalization are computed on the full available set. |
| `bands` | string | no | `all` | Comma-separated 1–6, or `all`; filters only the six band keys. `all`, `thermal`, and `flag_overlay` are always returned when available; flag summaries use all bands. |
| `include_diff` | bool | no | `true` | Include difference frames. |

Response:

> **1.1.0 note:** this example keeps the 1.0.0 shape. The optional additive fields `epochs[].telemetry`, `epochs[].lvf_geometry`, `epochs[].candidates`, and `epochs[].core_inpainted` are defined in §3.9 and are omitted here for brevity.

```json
{
  "query": {
    "ra": 133.75921,
    "dec": -7.24216,
    "size_deg": 0.2,
    "target_id": "wise_0855"
  },
  "target": {
    "id": "wise_0855",
    "name": "WISE 0855",
    "category": "Y4 Sub-Brown Dwarf (~250 K)",
    "ra_ref": 133.79513,
    "dec_ref": -7.24515,
    "ref_epoch": "2010.0",
    "ra_epoch2025": 133.75921,
    "dec_epoch2025": -7.24216,
    "pm_ra_mas_yr": -8118.0,
    "pm_dec_mas_yr": 680.0,
    "recommended_bands": [5, 6],
    "story_headline": "Coldest Known Object Outside the Solar System",
    "story_body": "..."
  },
  "wcs": {
    "crval1": 133.75921,
    "crval2": -7.24216,
    "crpix1": 120.5,
    "crpix2": 120.5,
    "cdelt1": -0.0008541667,
    "cdelt2": 0.0008541667,
    "width": 240,
    "height": 240,
    "pixel_scale_arcsec": 3.075,
    "native_pixel_scale_arcsec": 6.15
  },
  "epochs": [
    {
      "epoch_id": "2025_E1",
      "label": "Survey Epoch 1 (2025)",
      "collection": "spherex_dr1",
      "release": "DR1",
      "mjd_mean": 60840.7788,
      "date_iso": "2025-06-14",
      "frames": {
        "1": "/api/v1/assets/wise_0855/2025_E1_D1.webp",
        "2": "/api/v1/assets/wise_0855/2025_E1_D2.webp",
        "3": "/api/v1/assets/wise_0855/2025_E1_D3.webp",
        "4": "/api/v1/assets/wise_0855/2025_E1_D4.webp",
        "5": "/api/v1/assets/wise_0855/2025_E1_D5.webp",
        "6": "/api/v1/assets/wise_0855/2025_E1_D6.webp",
        "all": "/api/v1/assets/wise_0855/2025_E1_ALL.webp",
        "thermal": "/api/v1/assets/wise_0855/2025_E1_B56.webp",
        "flag_overlay": "/api/v1/assets/wise_0855/2025_E1_FLAGS.webp"
      },
      "flag_summary": {
        "status": "NOMINAL",
        "source_bit_set": true,
        "artifact_pixel_fraction": 0.004,
        "active_warning_flags": [],
        "human_explanation": "Clean measurement. Bit 21 (SOURCE) confirms a cataloged object; no persistence or cosmic-ray contamination in the target aperture."
      }
    },
    {
      "epoch_id": "2025_E2",
      "label": "Survey Epoch 2 (2025)",
      "collection": "spherex_dr1",
      "release": "DR1",
      "mjd_mean": 61012.7201,
      "date_iso": "2025-12-03",
      "frames": {
        "1": "/api/v1/assets/wise_0855/2025_E2_D1.webp",
        "2": "/api/v1/assets/wise_0855/2025_E2_D2.webp",
        "3": "/api/v1/assets/wise_0855/2025_E2_D3.webp",
        "4": "/api/v1/assets/wise_0855/2025_E2_D4.webp",
        "5": "/api/v1/assets/wise_0855/2025_E2_D5.webp",
        "6": "/api/v1/assets/wise_0855/2025_E2_D6.webp",
        "all": "/api/v1/assets/wise_0855/2025_E2_ALL.webp",
        "thermal": "/api/v1/assets/wise_0855/2025_E2_B56.webp",
        "flag_overlay": "/api/v1/assets/wise_0855/2025_E2_FLAGS.webp"
      },
      "flag_summary": {
        "status": "NOMINAL",
        "source_bit_set": true,
        "artifact_pixel_fraction": 0.003,
        "active_warning_flags": [],
        "human_explanation": "Clean measurement."
      }
    }
  ],
  "differences": {
    "2025_E2_minus_2025_E1": {
      "1": "/api/v1/assets/wise_0855/diff_E2_E1_D1.webp",
      "5": "/api/v1/assets/wise_0855/diff_E2_E1_D5.webp",
      "6": "/api/v1/assets/wise_0855/diff_E2_E1_D6.webp",
      "all": "/api/v1/assets/wise_0855/diff_E2_E1_ALL.webp",
      "thermal": "/api/v1/assets/wise_0855/diff_E2_E1_B56.webp"
    }
  },
  "reference_overlays": {
    "optical_dss_gaia": "/api/v1/assets/wise_0855/ref_optical.webp",
    "mid_ir_wise": "/api/v1/assets/wise_0855/ref_wise.webp"
  },
  "provenance": {
    "source": "NASA/IPAC IRSA SPHEREx DR1",
    "collection": "spherex_dr1",
    "release": "DR1",
    "zodi_subtracted": true,
    "background_subtracted": true,
    "flux_normalization": {
      "method": "static_source_p99_5",
      "scope": "per_band_across_epochs",
      "reference_epoch": "2025_E1",
      "applied": true,
      "status": "ok",
      "clamped": false,
      "raw_stats_location": "server_only"
    },
    "is_simulated_fallback": false,
    "generated_at": "2026-11-13T20:00:00Z",
    "citation": "SPHEREx Data Release 1 (JPL/Caltech/IRSA)"
  }
}
```

**Rules:**

- `target` is `null` for an arbitrary RA/Dec with no target record. `query.target_id` is `str | null`; `null` for arbitrary positions.
- `epochs` contains only epochs with data; never fabricate an epoch.
- `epochs[].collection` / `release` are per epoch. **Current accepted values:** `spherex_dr1`/`DR1`, `spherex_qr3`/`QR3`, or `mixed`/`DR1+QR3` if any band falls back to a different release. Revision-3 saved data uses these values. Historical revision-2 saved data still carries `spherex_qr2`/`QR2` (and `mixed`/`QR2+QR3`); B10 implemented the **1.2.0** vocabulary without a schema change. Do not emit `release="unknown"` for `/dr1/` URIs.
- For catalog targets, `query.ra`/`dec` and `wcs.crval` are the target's 2025.8 coordinates; the request's `ra`/`dec` must match within 1.0″. `size` is a client-side crop of the full 240×240 (0.205°) golden grid; `query.size_deg` echoes the clamped request. `epochs` filters only the returned epochs/differences; IDs, adjacent pairs, and normalization are computed on the full set.
- `frames` keys are strings for JSON compatibility: `"1"`–`"6"`, `"all"`, `"thermal"`, `"flag_overlay"`.
- `frames` and `differences` may omit keys for missing bands; the frontend must disable or hide missing bands rather than assume all six exist. The `all` frame uses all available bands; the `thermal` frame uses bands 5 and 6, or whichever of the two is available.
- Difference keys are included only for bands present in both epochs; `all` uses the common bands; `thermal` only when both bands 5 and 6 are common; `include_diff=false` → `differences={}`; no `flag_overlay` in differences. `all`/`thermal` difference frames sum the per-band raw differences with the same band weights as the frame coadd.
- `provenance.flux_normalization` documents the pre-normalization: frames are pre-normalized; the frontend must not re-normalize; all/thermal coadds use the same per-band scales; difference frames use raw frames server-side. See `docs/decisions/o1-contract-decisions.md` §5.
- `bands` filters only the six band keys `"1"`–`"6"`; `all`, `thermal`, and `flag_overlay` are always returned when available. `flag_summary`, `source_bit_set`, and `artifact_pixel_fraction` use the full available band set. The `all`/`thermal` coadds are computed from the full available bands.
- `flag_summary.status` is one of `NOMINAL`, `CAUTION`, `ALERT`. `status`/`active_warning_flags` are target-aperture (12.3″) based; `artifact_pixel_fraction` and `flag_overlay` are frame-wide.
- `provenance.is_simulated_fallback` retains its boolean wire type for compatibility. The application requires it to be explicitly `false`; historical simulated payloads are rejected. A failed live request returns an error envelope.
- `reference_overlays` is always an object; individual keys are omitted when unavailable; use `{}` when none.

### 3.5 `GET /api/v1/spectrum`

Query parameters: `ra`, `dec`, optional `target_id`, optional `epoch_id`. The aperture is fixed at 12.3″ (2.0 native px); the annulus is 3.0–5.0 native px. There is no `aperture_arcsec` parameter in the MVP. `target_id` follows the `/sky` 1.0″ rule and is nullable in the response; `epoch_id` must be a full-set epoch ID (unknown → 422) and filters the returned `epochs[]` only. Spectra are extracted from **un-normalized**, ZODI/background-subtracted frames.

> **1.1.0 note:** channels may also carry the optional `photometry_method`, `aperture_mode`, and `aperture_radius_arcsec` fields defined in §3.9; they are omitted from the example below.

```json
{
  "target_id": "wise_0855",
  "ra": 133.75921,
  "dec": -7.24216,
  "aperture_radius_arcsec": 12.3,
  "wavelength_calibration": "WCS-WAVE (sip=None, ~1 nm)",
  "confidence": "high",
  "epochs": [
    {
      "epoch_id": "2025_E1",
      "label": "Survey Epoch 1 (2025)",
      "collection": "spherex_dr1",
      "release": "DR1",
      "channels": [
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
      ]
    }
  ],
  "molecular_features": [
    {"label": "H2O", "wavelength_um": 1.40, "band": 2},
    {"label": "CH4", "wavelength_um": 1.65, "band": 3},
    {"label": "H2O / CO", "wavelength_um": 2.35, "band": 3},
    {"label": "H2O Ice", "wavelength_um": 3.08, "band": 4},
    {"label": "CH4 Fundamental", "wavelength_um": 3.32, "band": 4},
    {"label": "CO2 Ice", "wavelength_um": 4.27, "band": 5},
    {"label": "CO Fundamental", "wavelength_um": 4.67, "band": 6}
  ],
  "provenance": {
    "source": "NASA/IPAC IRSA SPHEREx DR1",
    "collection": "spherex_dr1",
    "release": "DR1",
    "zodi_subtracted": true,
    "background_subtracted": true,
    "is_simulated_fallback": false,
    "generated_at": "2026-11-13T20:00:00Z",
    "citation": "SPHEREx Data Release 1 (JPL/Caltech/IRSA)"
  }
}
```

**Rules:**

- `channels` may be sparse; each channel is one detector/wavelength sample; missing channels are omitted, not represented as bad.
- `target_id` is `str | null`; if provided, `ra`/`dec` must match the target's 2025.8 coordinate within 1.0″ (same as `/sky`). `epoch_id` must be one of the full-set epoch IDs; unknown → 422; the response contains only that epoch.
- Spectra are extracted from **un-normalized**, ZODI/background-subtracted frames; the blink normalization is not applied.
- `flags` is the `FLAGS` value at the channel's **extraction center** (the native pixel at the target coordinate in that channel's exposure/epoch, along the source trace), **not** one pixel for all channels and **not** an aperture OR. `is_flagged_bad = ((flags & HARD_BAD_MASK) != 0)` for a present channel; warning bits never set it.
- `clean_fraction` (float 0–1) and `is_used_in_photometry` (bool) follow `docs/decisions/o1-contract-decisions.md` §1; `flux_ujy`/`flux_err_ujy` may be `null` when no clean pixels remain. `epochs[]` carries `collection`/`release`, and `provenance` adds `zodi_subtracted`; see `docs/decisions/o1-contract-decisions.md` §3/§6.
- `is_flagged_bad` is `true` only for `HARD_BAD_MASK`; warning bits do not make a channel bad.
- `confidence` is `"high"` for precomputed target spectra and `"low"` for best-effort arbitrary clicks. It describes extraction quality, not a discovery probability.
- For arbitrary clicks, `provenance.is_simulated_fallback` must be explicitly `false`; the application rejects simulated or missing provenance.
- Precomputed target spectra must include all available channels, not a subset.

### 3.6 `GET /api/v1/assets/{target_id}/{filename}`

Serves cached WebP/JSON assets from `golden_cache/` or the live cache. Validate the path; do not allow directory traversal. Catalog assets are size-independent (full 240×240, 0.205° golden grid); live assets are keyed by the canonical query, including `size`.

### 3.7 Error envelope

```json
{
  "error": {
    "code": "NO_DATA",
    "message": "No SPHEREx observations cover this position.",
    "detail": {
      "ra": 133.76,
      "dec": -7.24,
      "collections_tried": ["spherex_dr1", "spherex_qr3", "spherex_dr1_deep", "spherex_qr3_deep"]
    }
  }
}
```

| HTTP | Code | Meaning |
|---|---|---|
| 400 | `INVALID_COORDINATES` | RA/Dec out of range or unparsable. |
| 404 | `NO_DATA` | No overlapping observations. |
| 422 | `VALIDATION_ERROR` | Bad query parameter. |
| 503 | `UPSTREAM_UNAVAILABLE` | IRSA/TAP/SIA2 timeout or outage. |
| 500 | `INTERNAL_ERROR` | Unexpected server error. |

### 3.8 Contract change process

1. Open a PR with the proposed schema change and the reason.
2. Orchestrator reviews; both backend and frontend agents confirm.
3. Bump `API_CONTRACT_VERSION` in `backend/models/version.py` (Orchestrator-owned); import it as `from models.version import API_CONTRACT_VERSION` when running from `backend/`; `backend/core/config.py` may re-export it.
4. Update this file, the roadmap appendix, and tests in the same PR.
5. Never ship a breaking change during the final 6 hours.

### 3.9 Additive contract 1.1.0 (Phase 2) and 1.2.0 (DR1)

`API_CONTRACT_VERSION = "1.2.0"` (2026-11-13). The 1.1.0 additions (frozen
2026-11-09) are all optional; no 1.0.0 field changed type or meaning. All
existing 1.0.0/1.1.0 payloads and the revision-2 golden cache remain valid.
Contract 1.2.0 extends only the release vocabulary; the schema is unchanged.

- `epochs[].telemetry`: `{url, format: "float16_uint32_le_gzip", width, height, byte_size, flux_band: "thermal" | "all"}` or `null`. The sidecar is a gzipped little-endian `240×240 float16` MJy/sr plane followed by a `240×240 uint32` Table 16 flag plane.
- `epochs[].lvf_geometry`: list of `{detector: 1–6, pa_deg, grad_um_per_arcsec}` or `null`.
- `epochs[].candidates`: list of `{id, ra, dec, x_px, y_px, kind: "dipole" | "variable", snr, delta_flux_mjy_sr, is_artifact_clean, label}` or `null`. Objective SNR/flux only; never a confidence score or probability.
- `epochs[].core_inpainted`: boolean, default `false`. Display-only; it must never alter science arrays.
- `channels[].photometry_method`: `"aperture_12.3"` (default) or `"crowded_diff_6.8"`.
- `channels[].aperture_mode`: `"standard_12.3"` (default) or `"crowded_diff_6.8"`.
- `channels[].aperture_radius_arcsec`: float, default `12.3`.
- `reference_overlays` remains a string map; it may include `optical_dss2_red`, `mid_ir_wise_w1`, `gaia_sources_url`, and `attribution` in addition to the 1.0.0 keys.

`psf_wing_fit` is **not** part of 1.1.0: the W0 spike measured zero passing channels on Barnard’s Star and R Draconis. Do not add it without a new contract decision and measured data.

**Contract 1.2.0 (2026-11-13, implemented in B10):** data-value addition only. `epochs[].collection`/`release` and the top-level provenance accept `spherex_dr1`/`DR1` and `mixed`/`DR1+QR3` in addition to `spherex_qr3`/`QR3`; historical `spherex_qr2`/`QR2` and `QR2+QR3` remain valid for revision-2 saved data. No field type or schema changed.

---

## 4. Data and science guardrails

### 4.1 MEF HDU contract

| HDU | `EXTNAME` | Access | Notes |
|---|---|---|---|
| 0 | `PRIMARY` | **Never read `.data`** | Header only. |
| 1 | `IMAGE` | `hdul["IMAGE"].data` | MJy/sr; no ZODI subtraction. |
| 2 | `FLAGS` | `hdul["FLAGS"].data` | 32-bit bitmask. |
| 3 | `VARIANCE` | `hdul["VARIANCE"].data` | (MJy/sr)². |
| 4 | `ZODI` | `hdul["ZODI"].data` | MJy/sr; subtract. |
| 5 | `PSF` (QR2) or `EPSF` (QR3/DR1) | `hdul["PSF"].data` / `hdul["EPSF"].data` | QR2: 121 × 101 × 101 cube. QR3/DR1: binary table, 441 rows full frame (451 in the tested cutout), 33 × 33, 5× oversampled. Branch on `EXTNAME`; never assume `PSF`. |
| 6 | `WCS-WAVE` | `hdul["WCS-WAVE"]` | Table; use `WCS(..., key="W")`, `sip=None`. |

### 4.2 Bitmask policy

**Hard mask** (`HARD_BAD_MASK`): set to `NaN` before background/coadd.

```python
HARD_BAD_MASK = (
    (1 << 2) | (1 << 6) | (1 << 9) | (1 << 10) | (1 << 11) |
    (1 << 14) | (1 << 15) | (1 << 26) | (1 << 27) | (1 << 28) | (1 << 29)
)
```

**Warning mask** (`ARTIFACT_WARNING_MASK`): do not mask from the image; surface in the Artifact Shield.

```python
ARTIFACT_WARNING_MASK = (
    (1 << 0) | (1 << 1) | (1 << 7) | (1 << 17) |
    (1 << 19) | (1 << 20) | (1 << 22) | (1 << 23) | (1 << 24) | (1 << 25)
)
```

**Never mask:**

```python
BIT_SOURCE = 1 << 21       # known catalog object
BIT_FULLSAMPLE = 1 << 12   # informational
```

**Background estimation mask:** `HARD_BAD_MASK | ARTIFACT_WARNING_MASK | BIT_SOURCE`. This is the only place `BIT_SOURCE` may be excluded.

**Verification:** confirm the full Table 16 (Image pixel flags used in spectral images at Level 2) definitions against the Explanatory Supplement. Table 10 is a different table (Non-Overflow Bloom Pixel Candidates). Bit 23 (`GHOST_FPA`) is currently unused but is included in `ARTIFACT_WARNING_MASK` for forward compatibility. If a bit differs, update `backend/core/flags.py` and `backend/tests/test_bitmasks.py` in the same PR.

**Photometry nuance:** `DICHROIC` (bit 7) is a warning for the displayed image, but the supplement describes these pixels as low-throughput and not usefully calibrateable. For coadds and spectrophotometry, exclude them from flux measurements or apply the throughput correction.

**HALO nuance:** `HALO` (bit 28) is hard for photometry. If the R Draconis measurement in `docs/decisions/o1-contract-decisions.md` §9 triggers the display-only gate, use `DISPLAY_BAD_MASK = HARD_BAD_MASK & ~(1 << 28)` for displayed frames, include HALO in `flag_overlay`/`CAUTION`, and keep it in `PHOTOMETRY_EXCLUDE_MASK` (HALO remains hard for `is_flagged_bad`). Otherwise keep HALO `NaN` everywhere.

### 4.3 Coordinate propagation

- `backend/core/targets.py` stores `ra_ref`, `dec_ref`, `ref_epoch`, `ra_epoch2025`, `dec_epoch2025`, `pm_ra_mas_yr` (`μ_α cos δ`), `pm_dec_mas_yr`.
- Production propagation uses `astropy.coordinates.SkyCoord.apply_space_motion`.
- All IRSA queries for the five targets use the 2025.8 coordinates; arbitrary user coordinates use the supplied position.
- The frontend draws the vector from the reference epoch to 2025.8; label WISE 0855 as 2010.0, not J2000.

### 4.4 WCS and reprojection

- Build a north-up TAN WCS: 240 × 240, `cdelt1 = -3.075″/px = -0.0008541667°`, `cdelt2 = +3.075″/px = +0.0008541667°`, `crpix = (120.5, 120.5)`.
- Use `reproject_interp` for images and variance/weights.
- Interpolating variance underestimates noise because neighboring input pixels are correlated. For the MVP, treat the reprojected variance as approximate, apply a variance floor (e.g. the median native variance), and label uncertainties as approximate; do not claim calibrated error bars.
- Use nearest-neighbor for bitmask/flag layers.
- Preserve flux units through reprojection; do not apply surface-brightness corrections unless documented.
- Validate the WCS against at least three Gaia stars.

### 4.5 Zodiacal and background subtraction

The v1.5 implementation in `services/background.py` supersedes the minimal scalar illustration below: require at least 11 clean pixels, 5% clean fraction, three quadrants and half-field support on both axes. A fixed checkerboard holdout gate selects a robust 2D plane only when supported; otherwise retain a supported scalar. Insufficient support must be reported and cannot produce usable photometry.

```python
img = hdul["IMAGE"].data.astype(float) - hdul["ZODI"].data.astype(float)
flags = hdul["FLAGS"].data.astype(np.uint32)
bg_exclude = (flags & (HARD_BAD_MASK | ARTIFACT_WARNING_MASK | BIT_SOURCE)) != 0
valid = img[~bg_exclude & np.isfinite(img)]
local_bg = np.nanmedian(valid) if valid.size > 10 else 0.0
img = img - local_bg
```

- For larger cutouts, use `photutils.background.Background2D` or `sep.Background` with `bw=32, bh=32`.
- Never include `BIT_SOURCE` pixels in the background estimate.
- Document whether ZODI was subtracted in `provenance.zodi_subtracted`.

### 4.6 Flux conversion

```text
Ω_pix = (6.15″)² = 37.8225 arcsec² = 8.890e-10 sr
F_pix [μJy] = I_pix [MJy/sr] × Ω_pix [sr] × 1e12
```

Equivalent:

```text
F_pix [μJy] = I_pix [MJy/sr] × 23.50443 × Ω_pix [arcsec²]
```

Sanity check: 1 MJy/sr over one native pixel → ~889 μJy. Use the solid-angle pixel map if available; otherwise the nominal area is acceptable and must be documented.

### 4.7 Epoch grouping

- Primary: 6-month survey epochs (3–4 present for these targets). Use **DR1** for the reprocessed QR2 epochs and **QR3** for the later epochs; QR2 is superseded and is not used in revision 3. The current revision-3 cache uses DR1 for all epochs except the newest Barnard/Epsilon Indi B/R Draconis epochs (`DR1+QR3` mixed) and RW Aurigae's newest epoch (`QR3`).
- Optional: visit-level frames within an epoch, clustered by days; label them "visits."
- Never fabricate an epoch or interpolate a missing one.
- If only one epoch exists, return a single-epoch manifest with a `WARNING`-level note.

### 4.8 Spectra

- Use WCS-WAVE (`sip=None`) for MVP spectra; note the ~1 nm accuracy.
- Aperture: circular, fixed r = 2.0 native pixels = 12.3″; annulus r_in = 3.0 px, r_out = 5.0 px. Do not expose a variable aperture in the MVP; a larger aperture would overlap the annulus and change `N_aperture`.
- Propagate variance; mark hard-bad channels; do not mark warning bits as bad. `DICHROIC`/warning pixels reduce `clean_fraction`; exclude them from the flux or apply the throughput correction; use `is_used_in_photometry`. No blind aperture correction: when `clean_fraction < 1`, label the clean-pixel flux as relative photometry.
- Convert MJy/sr to μJy with §4.6.
- Precompute the five targets; live arbitrary clicks are best-effort and must carry a `confidence: "low"` field.
- `CWAVE`/`CBAND` are optional validation; do not download 32 MB calibration files in the MVP request path.

### 4.9 Golden cache and real-only packaging

- `scripts/build_golden_cache.py` generates `golden_cache/{target_id}/` during the hackathon from **real IRSA data** (current cache: revision 3, DR1+QR3).
- Normal operation is **real-data only**. `/sky` and `/spectrum` select the saved cache for catalog targets and the live pipeline for arbitrary coordinates; they never fall back to a fixture.
- No synthetic observation dataset, generator, mock loader, or model-spectrum comparator belongs in the product tree. Docker copies only the five approved real target datasets, and the build must pass the real-only packaging gate. Retired namespaces return 404 even on stale volumes.
- A failed live request returns the §3.7 error envelope and a clean UI error; it must not fetch `/mock`.
- Never commit secrets or large raw FITS files. Commit compressed real-derived products with provenance. Small real-derived test samples may be used with attribution; generated edge-case inputs stay test-only and inventoried.
- Current live arbitrary budget: `LIVE_TAP_TIMEOUT_SECONDS=60`, `LIVE_SKY_DEADLINE_SECONDS=120`, frontend arbitrary timeout **130 s**, `LIVE_REQUEST_TIMEOUT_SECONDS=20`. Catalog/golden targets are unchanged.

---

## 5. Frontend guardrails

### 5.1 Canvas performance

- Pre-decode frames with `createImageBitmap()` as soon as the manifest arrives.
- Use a persistent `requestAnimationFrame` loop; read mutable state from `useRef`.
- Do not call `setState` per blink tick.
- Use an offscreen canvas for compositing; draw only the active frame and overlays.
- Target 60 FPS rendering; blink at 1–8 FPS.

### 5.2 Stretch and colormaps

- Support grayscale, inferno, viridis, and a diverging cool-warm map for difference mode.
- Support linear, log, asinh, and zscale stretches.
- Apply LUTs client-side; do not re-request frames for contrast changes.
- Use shared cross-epoch normalization (LAW 8) so static stars do not flicker.

### 5.3 Overlays

- Proper-motion reticle: reference epoch vs. 2025.8, dashed vector, tick marks.
- 6.15″ native pixel box; scale bar in arcseconds; compass.
- Cursor loupe: RA/Dec, surface brightness (MJy/sr), active flag bits.
- Cross-mission curtain: use the precomputed real `ref_optical.webp` / `ref_wise.webp` cutouts; hide a side when its asset is absent (no invented reference).

### 5.4 URL state

- Encode `ra`, `dec`, `size`, `target`, `bands`, `epoch`, `mode`, `fps`, `diff`, `overlay`.
- Debounce updates; restore on load; provide Copy/Embed.
- Invalid URL values fall back to defaults with a non-blocking warning.

### 5.5 Accessibility

- WCAG AA contrast; visible focus rings; keyboard shortcuts.
- `prefers-reduced-motion`: disable autoplay/cross-fades.
- Photosensitivity: default 4 FPS; cap 8 FPS; warning.
- Alt text; spectrum data-table fallback.
- Do not encode meaning by color alone.

### 5.6 No fake data

- Never hardcode a light curve or spectrum and present it as real.
- Reject simulated or provenance-free payloads. There is no mock mode or illustrative spectrum comparator, including in development builds.
- A failed live request shows a clean error and offers a retry/benchmark target; it must not request a fixture or show automatic fallback text.
- No invented "AI confidence" or "discovery probability."

### 5.7 Scientific-workstation design contract

The UI is a **publication-grade scientific instrument**, not a generic AI dashboard. The binding spec lives in `agents/prompts/frontend.md` §"Design contract — scientific workstation (binding)". Hard requirements:

- **Canvas is the hero.** No raw text over star pixels; all on-canvas telemetry uses floating monospace HUD chips (`rgba(10,12,16,0.75)`, 8px blur, `rgba(255,255,255,0.1)` hairline border, 4px radius, 11px mono). Reticle readouts/flags sit in fixed top-left and bottom-right corners.
- **Palette:** `#08090b` canvas, `#0e1015` panels, `1px solid rgba(255,255,255,0.07)` borders, zero glow. One accent color, used sparingly.
- **Type:** Inter/system sans for UI; strict monospace for RA/Dec, flux, epoch, wavelength; uppercase 10px `0.12em` muted section headers.
- **Left rail:** one unified high-density telemetry rail with target header, two-column metric grid, compact collapsible Artifact Shield, and story/limitations in a drawer — not four stacked cards.
- **Right rail:** gradient colormap swatches with a sharp 1px active ring; 2px slider tracks with 10px white thumbs and aligned mono values; custom micro-switches, never default checkboxes.
- **Bottom deck:** one precision console with three segmented groups — transport, B1–B6 + Thermal, epoch timeline with playhead.
- **Motion:** hard-cut blinking; all control transitions `120ms ease-out`; `:active { transform: translateY(1px); }`.

No visual change may alter the API contract, frame normalization, flag semantics, provenance, or the honesty rules in §5.6.

---

## 6. Workflow and verification gates

### 6.1 Branches and commits

- Branches: `agent/backend-<topic>`, `agent/frontend-<topic>`, `agent/science-<topic>`, `agent/integration-<topic>`.
- Commits: `feat(backend): ...`, `fix(frontend): ...`, `test(science): ...`, `chore(infra): ...`.
- PRs target `main`; Orchestrator reviews and merges.
- Keep PRs small; one concern per PR.
- Rebase on `main` before requesting review.

### 6.2 Mandatory checks

Run before every merge:

```bash
# 1. Forbidden HDU[0] access
if grep -rn "hdul\[0\]\.data" backend/ scripts/; then
  echo "ERROR: forbidden hdul[0].data access"; exit 1
fi

# 2. Forbidden naive flag masking
if grep -rn -E "flags (>|!=) 0" backend/ scripts/; then
  echo "ERROR: naive flag masking"; exit 1
fi

# 3. Science and API tests
pytest backend/tests/ -v

# 4. Frontend typecheck and build
cd frontend && npm run typecheck && npm run build
```

If a check fails, fix it before merging. Do not add exceptions without Orchestrator approval.

### 6.3 Definition of done

**Backend:**

- Endpoint returns the exact contract JSON.
- No `hdul[0].data`; no naive flag masking.
- ZODI + background subtracted; `spectral_wcs.sip = None`.
- Cache works; provenance correct; errors use the envelope.
- Unit tests cover the pipeline and bitmask policy.

**Frontend:**

- `npm run typecheck` and `npm run build` pass.
- Canvas blinks at 60 FPS; no React re-mount per tick.
- URL state round-trips; keyboard shortcuts work.
- Reduced motion and photosensitivity rules honored.
- No fake data or confidence scores; no automatic fixture fallback; clean live-error state.

**Science/validation:**

- Golden cache for all five targets exists (or a documented failure).
- `pytest` passes; astrometry validated against Gaia.
- Each target's expected phenomenon is visible.
- README, Dockerfile, and attribution complete.

**Integration:**

- Public URL works in incognito.
- All five targets load within the demo budget.
- Demo video recorded; submission checklist complete.

### 6.4 Integration checkpoints

- **H+12:** one target blinking end-to-end.
- **H+24:** five targets + URL state + Artifact Shield.
- **H+32:** difference mode + spectrum (or explicit cut).
- **H+38:** arbitrary-coordinate hardening + cross-mission curtain (curtain may be cut; arbitrary RA/Dec is P0).
- **H+42:** feature freeze.
- **H+46:** submitted.

At each checkpoint, the Orchestrator runs the five-target smoke test and records pass/fail.

**Final status (2026-11-14):** all pre-event checkpoints are complete. Golden revision 3 (DR1+QR3) covers 5/5 targets, the five-target card is 5/5, `pytest` is 83/83, and `skyblink:final` passes the five-target container smoke at health version 1.2.0. B10/S7/D2/B12/F11 are done. Normal operation is real-data only with a 60 s TAP / 120 s sky / 130 s frontend live budget; a verified random field returned in 39.6 s. Remaining work is **I1** (public deployment), public-repo access, and **I2** (demo/submission). See `TASKS.md` and `STATUS.md`.

---

## 7. Task prompts

> **Historical prompts:** §7.1–§7.3 are the original Phase 1 task prompts (B1/F1/S1). They remain for context. The final implementation also completed B2–B8, S2–S5, F2–F6, O2, and W0; the authoritative task list and acceptance criteria are in `TASKS.md`. The measured scope decisions (PSF-wing NO-GO, R Dra NEP NO-GO, telemetry budget, real SkyView overlays) are in `docs/research/w0-feasibility-report.md`.
>
> **Phase 2 added:** O2 contract 1.1.0; B8 telemetry/LVF/dense spectra; S4 real overlays/Gaia + golden revision 2; F5 physical loupe/curtain/comparator; F6 trial-motion/LVF/sonification/triage; S5 final image/README. B9 (Deep blink) is deferred.
>
> **Phase 3 (2026-11-13):** B10 contract 1.2.0 (DR1 release detection) and S7 golden revision 3 (DR1+QR3). B10/S7/D2 are complete.
>
> **Phase 4 (2026-11-14):** B12 raised the live arbitrary budget (TAP 60 s, sky 120 s, frontend 130 s, cutout 20 s) and F11 removed the automatic fixture fallback, leaving a clean error path. Both are complete; the remaining work is deployment and submission.

### 7.1 Task Prompt A — `astro-backend-agent`

> Read `AGENTS.md` §0–§4 and §6, plus `ROADMAP.md` §5–§10. Implement `backend/core/flags.py`, `backend/core/targets.py`, `backend/services/irsa_client.py`, `backend/services/spherex_pipeline.py`, `backend/services/spectrophotometry.py`, and the FastAPI routers.
>
> Verify:
> 1. `hdul[0].data` is never accessed.
> 2. `BIT_SOURCE` (Bit 21) is preserved in images and only excluded from background estimation.
> 3. `spectral_wcs.sip = None` is set before `pixel_to_world` on WCS key `'W'`.
> 4. `ZODI` (HDU 4) + local background are subtracted before reprojection/coadd.
> 5. Cross-epoch frames of the same band share a flux normalization so static stars do not flicker.
> 6. Every response includes provenance and `is_simulated_fallback` (`false` for real data).
> 7. TAP is primary; SIA2 is fallback; errors use the §3.7 envelope, and a failure never returns a development fixture.

### 7.2 Task Prompt B — `sky-frontend-agent`

> Read `AGENTS.md` §0, §3, §5 and `ROADMAP.md` §7, §11. Build the React + TypeScript + Tailwind frontend in `frontend/src/`.
>
> Ensure:
> 1. `BlinkCanvas.tsx` pre-decodes frames into `ImageBitmap` objects and renders at 60 FPS with client-side LUT colormaps and contrast/bias sliders.
> 2. The HUD overlay draws the reference-to-2025.8 proper-motion vector, the 6.15″ pixel box, and live `tabular-nums` RA/Dec readouts.
> 3. `CrossMissionCurtain.tsx` provides a smooth split between optical (Gaia/DSS) and SPHEREx infrared, using the precomputed real reference cutouts; hide a missing side rather than inventing one.
> 4. `TimelineDock.tsx` includes six band pills, All Bands, Difference Mode, and the three smart presets.
> 5. `ArtifactShield.tsx` and `SpectrumDrawer.tsx` are linked to the active target and URL state.
> 6. `prefers-reduced-motion` and the 8 FPS cap are enforced.
> 7. No fake data or confidence scores.

### 7.3 Task Prompt C — `science-validation-agent`

> Read `AGENTS.md` §0, §4, §6 and `ROADMAP.md` §9–§12. Implement `scripts/build_golden_cache.py`, the optional `scripts/generate_fallback_fixtures.py`, `backend/tests/`, `Dockerfile`, `docker-compose.yml`, and `README.md`.
>
> Verify:
> 1. Golden cache for all five targets, generated during the hackathon from real IRSA data.
> 2. Any development fixture is explicit opt-in only and labeled `is_simulated_fallback: true`; normal operation never loads one.
> 3. Pytest covers astrometry, bitmasks, API contract, and spectral extraction.
> 4. The five-target test card in `ROADMAP.md` §10.3 passes.
> 5. Docker image serves the built frontend and API from one container.
> 6. README includes data attribution, SI disclosure, and limitations.

### 7.4 Task Prompt D — `integration-qa-agent` (Orchestrator or designee)

> Read all of `AGENTS.md` and `ROADMAP.md`. Run the mandatory checks in §6.2. Test the public URL in incognito. Load all five targets. Verify URL sharing, difference mode, Artifact Shield, and reduced motion. Record the demo video. Complete the submission checklist.

---

## 8. Out of scope / do not build

- Authentication, accounts, or a database.
- Full-sky HiPS tile generation or HEALPix/Zarr archive.
- ZOGY or optimal transient detection.
- Custom ML models or fake probabilities.
- 3D volumetric galaxy flythroughs.
- Planet Nine discovery claims.
- A separate mobile app.
- A production-grade multi-tenant service.
- Any feature that requires more than the P0/P1 scope in `ROADMAP.md` §5.

---

## 9. Event compliance

- **No pre-work:** do not build the project before the hackathon start. **Berlin Local Event exception (2026-11-09):** registered participants may start early, including programming; see `docs/reference/event-compliance.md`. Attendance on both event days and timely submission remain required.
- **Team size:** maximum 6; follow your Local Event rules.
- **One challenge:** this team works only on *Planet X and SPHEREx*.
- **SI disclosure:** describe how LLM/code-generation/image tools were used in the submission.
- **Open source:** include an MIT or BSD-3-Clause license; verify the November 13 guide.
- **Public URL:** no login, no API keys, no local server.
- **Data attribution:** SPHEREx acknowledgment + IRSA DOI; Aladin/Astropy/Gaia/WISE credits.
- **No secrets:** never commit API keys, tokens, or personal data.
- **Honesty:** product data is real-only; generated test inputs remain isolated and inventoried. State limitations and never claim that passing packaging checks proves scientific accuracy.

---

## 10. Stop conditions and escalation

Stop and ask the Orchestrator if:

- Table 16 bit definitions differ from §4.2.
- The TAP schema or cutout URL does not match `ROADMAP.md` §6.2.
- A target has no data in DR1 or QR3 and no real data path exists.
- A change would break the API contract.
- A file outside your ownership must be edited.
- A scientific claim cannot be verified.
- The public deployment is inaccessible or cold-starting.
- You are about to ship a feature after the H+42 freeze.

Escalation is not failure; silent workarounds are.

---

## 11. Pointers into `ROADMAP.md`

| Topic | Roadmap section |
|---|---|
| Official brief and rules | §2 |
| Science context and bands | §3 |
| Target coordinates | §4, Appendix A |
| Scope and non-goals | §5 |
| TAP/SIA2/cutout recipes | §6 |
| MEF structure and bitmask | §6.3–§6.5 |
| Flux conversion | §6.6 |
| Epoch policy | §6.7 |
| Architecture | §7 |
| Feature specs | §8 |
| 48-hour plan | §9 |
| Validation | §10 |
| UX/design system | §11 |
| Demo/submission | §12 |
| Risks | §13 |
| November 13 checklist | §14 |
| Sources | §15 |

### Current project docs (final state)

| Document | Purpose |
|---|---|
| `README.md` | Full project overview, feature tour, setup, API examples, validation, limitations, attribution |
| `docs/decisions/o1-contract-decisions.md` | O1 1.0.0, O2 1.1.0, and B10 1.2.0 contract reasoning and field tables |
| `docs/research/w0-feasibility-report.md` | Measured Phase 2 go/no-go decisions |
| `docs/guides/deployment.md` | Host requirements, build/publish, smoke test, rollback |
| `docs/verification/pre-event-verification.md` | Original IRSA/MEF/flag/coordinate verification + post-implementation update |
| `docs/reference/resource-release-2026-11-13.md` | Official Resources tab (NASA + CSA), DR1/QR3 verification, and the B10/S7 decisions |
| `docs/reference/event-compliance.md` | Berlin Local Event pre-event authorization and conditions |
| `STATUS.md` | Final state, checkpoint history, remaining submission work |
| `TASKS.md` | Completed task board, deferred B9, remaining submission checklist |
| `agents/README.md` | Multi-agent topology and operating procedure |
