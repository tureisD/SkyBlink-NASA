# ORCHESTRATOR DIRECTIVE v2.0: Moving SPHEREx SkyBlink from Top 5% to #1 Global Winner

> **Status: SUPERSEDED (2026-11-09; updated 2026-11-14).** This is the Phase 2 proposal that led to the W0 feasibility spike. It is retained for history only. **Any plan here for mock/synthetic/fallback data is superseded: the app uses real data only, and development fixtures are explicit opt-in only.** The measured outcome is in `docs/research/w0-feasibility-report.md`: PSF-wing recovery and R Draconis NEP re-clustering were **NO-GO**; dense spectra, telemetry sidecars, real SkyView/Gaia overlays, and the F5/F6 UI were **implemented**. The authoritative current scope and setup are in `README.md`, `AGENTS.md` §3.9, `docs/decisions/o1-contract-decisions.md` §12, and `STATUS.md`. Do not treat the claims below (e.g. 102-band spectra, ≥45 recovered channels, <15 s multi-epoch blink) as delivered features.

**Target Repository State Audited:** Commit `11ae030` / `5ff0840` (`O1`, `B1`–`B7.1`, `F1`–`F4`, `S1`–`S3` complete; `pytest` $40/40$; F4 Playwright $64/64$; `skyblink:final` container verified)  
**Compliance Context:** Berlin Local Event pre-event coding authorization confirmed (`docs/reference/event-compliance.md`), giving the team a multi-day engineering runway prior to the November 15 deadline.
**Audience:** `.opencode/agents/orchestrator` and worker worktrees (`agent/backend`, `agent/frontend`, `agent/science`).

---

## 0. Strategic Diagnosis: How to Beat Every Other Team in the World

Your engineering execution up to `S3` and `F4` is already in the top 5% of hackathon submissions: you have a verified single-origin container, strict `AGENTS.md` guardrails, real Table 16 bitmask handling, `ZODI` subtraction, LAW 8 cross-epoch normalization, and a cohesive F4 scientific-workstation UI (`#08090b` / `#0e1015` palette, $1\text{ px}$ hairlines, glassmorphic HUD chips).

To become the **#1 Global Winner** across Space Apps judging panels (which include NASA/IPAC archive scientists, Caltech/JPL astrophysicists, and UX/product judges), you must do two things:

1. **Part A — Eliminate the 8 Scientific & Technical Bottlenecks** currently admitted in `README.md` §5 and §10 (such as `0/60` and `1/54` usable spectral channels on saturated targets, black-hole donut cores, `LIVE_SKY_MAX_EPOCHS=1` preventing live searches from blinking, placeholder reference overlays, and $18$-channel sparse spectra).
2. **Part B — Ship 6 "Out-of-the-Ordinary" X-Factor Capabilities** that other strong teams will *not* think to build—transforming SkyBlink from a passive image viewer into an interactive **astrophysical discovery & instrument-physics workstation** that directly targets **Best Use of Science**, **Best Use of Data**, and **Art & Technology**.

---

## 1. PART A: Fixing the 8 Core Bottlenecks (The Foundation)

Every fix below is calibrated to your exact codebase, `docs/decisions/o1-contract-decisions.md`, and the live IRSA verification findings in `STATUS.md`.

| ID | Current State in `STATUS.md` / `README.md` | Root Cause | Winning Upgrade |
| :--- | :--- | :--- | :--- |
| **BOTTLENECK 1** | **Barnard's Star has $1/54$ and R Draconis has $0/60$ usable spectrum channels**; display frames show black core holes. | Central pixels trigger `BIT_OVERFLOW` ($1 \ll 1$) and `BIT_SUR_ERROR` ($1 \ll 2$), which sets `clean_fraction < 0.8` and drops the channel. | **HDU 5 PSF Wing Fitting + Display Core Inpainting:** Fit the unsaturated airy wings ($1.2 \le r \le 4.2\text{ native px}$) using the $121 \times 101 \times 101$ `PSF` cube already inside every $5.06\text{ MB}$ cutout! Recovers $\ge 50$ channels on Barnard's Star and R Draconis. |
| **BOTTLENECK 2** | **Spectra are capped at $18\text{ channels/epoch}$** ($6\text{ detectors} \times 3\text{ visits}$). | `SPECTRUM_MAX_VISITS_PER_BAND=3` slices chronologically instead of sampling across the Linear Variable Filter (LVF) gradient. | **Wavelength-Stratified LVF Sampling:** For golden cache builds, sample up to $17\text{ visits/band/epoch}$ stratified by detector $Y$-coordinate / `WCS-WAVE` wavelength, unlocking **$60\text{–}95+$ spectral channels** per epoch. |
| **BOTTLENECK 3** | **WISE 0855 spectrum is contaminated in B1–B4** ($53/54$ channels used, but B1 flux is background star light). | Fixed $12.3''$ ($2.0\text{ native px}$) aperture is $492\text{ arcsec}^2$ in area and scoops up stationary neighbor stars in WISE 0855's crowded field. | **Epoch-Propagated Tight PSF Aperture ($r = 1.1\text{ px} = 6.76''$) + Cross-Epoch Static Star Subtraction:** Subtract the static background epoch where WISE 0855 has moved $>4''\text{–}8''$ away before measuring flux, proving $F_\nu \approx 0\ \mu\text{Jy}$ in B1–B3! |
| **BOTTLENECK 4** | **Live arbitrary RA/Dec `/sky` cannot blink** (`LIVE_SKY_MAX_EPOCHS=1`, $22\text{ s}$ cold). | Downloading $6\text{ bands} \times 3\text{ epochs}$ of $5.06\text{ MB}$ cutouts sequentially hits the $22\text{ s}$ deadline. | **Band-First Multi-Epoch Streaming (`LIVE_SKY_MAX_EPOCHS=3`):** Download smaller $0.08^\circ$ cutouts for Bands 3, 5, and 6 across $2\text{–}3$ epochs in parallel (`max_workers=10`) so arbitrary coordinates blink in $<8\text{ s}$, warming B1/B2/B4 asynchronously. |
| **BOTTLENECK 5** | **Cross-Mission Curtain uses placeholder fixtures on WISE 0855** and is hidden on the other $4$ targets. | No real optical/mid-IR reference cutouts were fetched during `S1`/`S2`. | **Real Co-Aligned DSS2/PanSTARRS Optical, AllWISE Mid-IR, & Gaia DR3 Astrometric Pins for All $5$ Targets:** Fetch real `hips2fits` $240 \times 240$ TAN cutouts and IRSA TAP `gaia_dr3_source` catalogs into `golden_cache/`. |
| **BOTTLENECK 6** | **Loupe reports uncalibrated `0–255` display values** and cannot name per-pixel flags. | Frontend only receives 8-bit WebP images and a scalar aperture summary. | **Compressed Float16 Telemetry Sidecar (`{epoch_id}_telemetry.bin.gz`):** Ship a $<45\text{ KB}$ gzipped sidecar containing the $240 \times 240$ `float16` $\text{MJy/sr}$ array and `uint32` Table 16 bitmask so the cursor HUD reads real $\text{MJy/sr}$ and per-pixel flag names, and LUT stretches operate on physical floats. |
| **BOTTLENECK 7** | **`all`/`thermal` coadds use equal band weights; differences lack PSF matching.** | B2 simplified multi-band weighting and difference subtraction. | **Inverse-Variance Multi-Band Coadds & Sub-Pixel Registered / PSF-Matched Differences:** Weight bands by $W_b = 1/\sigma_b^2$ and equalize epoch PSFs before subtraction so static stars cancel cleanly. |
| **BOTTLENECK 8** | **R Draconis `2024_E1` has only B3/B6** despite R Draconis having **$2,483$ science artifacts** in IRSA TAP! | Coarse calendar epoch bucketing misses the rich North Ecliptic Pole (NEP) orbital cadence of R Draconis. | **NEP High-Cadence Epoch Clustering for R Draconis:** Cluster R Draconis's $2,483$ exposures into $5\text{–}6$ well-populated, complete6-band epochs spanning its $245.6\text{-day}$ Mira pulsation cycle. |

### Technical Math & Implementation Details for Part A

#### A.1 HDU 5 PSF Wing Photometry (`backend/services/spectrophotometry.py`)
Every cutout you download already carries the $121 \times 101 \times 101$ `PSF` cube (`hdul["PSF"]`, HDU 5), representing $11 \times 11$ detector zones oversampled by $10\times$.
When a channel's standard $r = 2.0\text{ native px}$ ($12.3''$) aperture has `clean_fraction < 0.8` due to core saturation (`BIT_OVERFLOW = 1 << 1` or `BIT_SUR_ERROR = 1 << 2`):
1. Determine the target's detector zone index $z \in [0, 120]$ from its full-frame pixel coordinates (`CRPIX1`, `CRPIX2` offset in the cutout header) and downsample the $101 \times 101$ PSF plane by $10\times$ onto the cutout pixel grid centered at $(x_0, y_0)$, normalized so $\sum P_{i,j} = 1$.
2. Select pixels in the **Unsaturated Wing Annulus** $1.2 \le r \le 4.2\text{ native pixels}$ where:
   * `(flags & (HARD_BAD_MASK & ~BIT_HALO)) == 0` (note: `BIT_HALO` is expected in the wings of bright stars and is *not* a detector defect; `BIT_SUR_ERROR` and `BIT_OVERFLOW` are excluded from the wing fit).
3. Compute the inverse-variance weighted least-squares wing flux and uncertainty:
   $$F_{\text{wing}} = \frac{\sum_{i \in \text{Wing}} w_i \, (I_i - B_{\text{sky}}) \, P_i}{\sum_{i \in \text{Wing}} w_i \, P_i^2}, \qquad \sigma_{F_{\text{wing}}} = \left(\sum_{i \in \text{Wing}} w_i \, P_i^2\right)^{-1/2}$$
4. Convert $F_{\text{wing}}$ from $\text{MJy/sr}$ to $\mu\text{Jy}$ via $\Omega_{\text{pix}} = (6.15'')^2 \times 2.350443 \times 10^{-11}\ \text{sr}$ and emit `"photometry_method": "psf_wing_fit"` and `"is_used_in_photometry": true`.

#### A.2 Display Core Inpainting (`backend/services/spherex_pipeline.py`)
To eliminate the ugly black core holes on Barnard's Star, R Draconis, and RW Aurigae **without altering science arrays**:
* After computing raw coadds, difference frames, and flag summaries, create a copy of the array solely for **WebP display rendering**.
* Identify `NaN` pixels that were masked due to `BIT_SUR_ERROR` or `BIT_NONLINEAR` and are spatially adjacent (within $2\text{ px}$) to pixels carrying `BIT_OVERFLOW`, `BIT_HALO`, or `BIT_SOURCE`.
* Fill those saturated core pixels with the local $99.95\text{th}$ percentile peak display intensity and apply a $\sigma = 0.75\text{ output px}$ Gaussian reconstruction kernel over the core patch.
* Add a toggleable **"Saturated Core Ring"** indicator in the UI overlay so scientific honesty is 100% preserved while the visual star looks like a real astronomical point source.

---

## 2. PART B: 6 Creative "Out-of-the-Ordinary" X-Factor Features

Most top teams will build a FITS-to-PNG blinker and a basic spectrum chart. To make **SPHEREx SkyBlink** unforgettable and sweep the Global Award nominations (**Best Use of Science**, **Best Use of Data**, **Art & Technology**), add these six high-leverage, scientifically authentic features:

### 🚀 X-Factor 1: Interactive "Shift-and-Stack" Velocity & Parallax Sandbox (*The Planet X Hunter*)
* **The Scientific Hook:** The challenge is titled **"Planet X and SPHEREx"**. In real astrophysics, how do astronomers detect a moving object (an outer Solar System planet or ultra-faint brown dwarf) when it is near the noise limit in individual epochs? They use **Synthetic Tracking (Shift-and-Stack)**: shifting multi-epoch images along a trial motion vector $(\mu_{\alpha*}, \mu_\delta)$ or orbital parallax reflex curve before coadding!
* **How It Works in SkyBlink (Pure Client-Side Canvas / Float32 Math):**
  1. In the precision media deck or left telemetry rail, add a **" Reference Frame: [Sky-Fixed (ICRS)] vs. [Target Co-Moving (Track & Stack)]"** micro-switch plus a draggable **Trial Velocity Vector**.
  2. In **Sky-Fixed Mode** (default), background stars remain stationary while **Barnard's Star** or **WISE 0855** hops across the screen.If stacked without shifting, the moving target smears into a trail.
  3. When the user switches to **Target Co-Moving Mode**, the canvas dynamically shifts each epoch $k$ by $(-\Delta x_k, -\Delta y_k)$ calculated from the target's proper motion $(\mu_{\alpha*}, \mu_\delta)$ and $\Delta\text{MJD}_k$:
     $$\Delta x_k = \frac{\mu_{\alpha*} \, \Delta t_k}{\text{scale}_{\text{px}}}, \qquad \Delta y_k = \frac{\mu_\delta \, \Delta t_k}{\text{scale}_{\text{px}}}$$
  4. **The Visual "Wow" Moment:** Suddenly, **WISE 0855 / Barnard's Star locks dead-center in the crosshairs and stacks to $\sqrt{N}\times$ higher SNR**, while the entire background starfield streaks past!
  5. **Bonus — The "Planet X vs. Brown Dwarf Parallax Comparator":** A toggle on the reticle overlays the 6-month **parallactic reflex ellipse** ($\pi = 1/d$) alongside the linear proper-motion vector, visually demonstrating why SPHEREx's 6-month cadence ($2\text{ AU}$ Earth-orbit baseline) is uniquely suited to separate nearby brown dwarfs from a distant Solar System Planet X ($d \sim 400\text{ AU} \Rightarrow \pi \approx 515''$ reflex shift every 6 months!).

### 🌈 X-Factor 2: "LVF Curtain & Focal-Plane Visualizer" (*How SPHEREx Actually Sees*)
* **The Scientific Hook:** Almost no general audience (or competing hackathon team) understands that SPHEREx has **no moving filter wheel**—it uses a **Linear Variable Filter (LVF)** where wavelength changes continuously along the detector axis, requiring the spacecraft to step across the sky over multiple visits to build a spectrum.
* **How It Works in SkyBlink:**
  1. Each channel in `spectrum.json` records the exact detector (`1`–`6`), `mjd_obs`, and the LVF wavelength gradient direction (`PA_LVF` from the cutout WCS rotation matrix `CD` / `PC`).
  2. When the user opens the Spectrum Drawer and hovers over any spectral data point (e.g., $\lambda = 4.27\ \mu\text{m}$ $\text{CO}_2$ ice), the main sky canvas renders a subtle, translucent **LVF Iso-Wavelength Band Overlay** across the starfield showing the exact orientation of the SPHEREx detector strip and wavelength gradient that captured that measurement!
  3. Clicking **"▶ Play LVF Spectral Sweep"** animates the LVF passband sweeping across the target from $0.75\ \mu\text{m}$ to $5.00\ \mu\text{m}$ while building the spectrum point-by-point in real time.
  4. **Why Judges Will Love It:** Any SPHEREx scientist on the NASA judging panel will immediately recognize that your team truly understood the instrument physics.

### 🔬 X-Factor 3: "1-Pixel Binary Spectral Decomposer" (*Solving the $\varepsilon\text{ Indi Ba + Bb}$ Blend*)
* **The Scientific Hook:** Because SPHEREx pixels are $6.15''$ wide, the brown dwarf binary **Epsilon Indi Ba (T1, $T_{\text{eff}} \approx 1280\text{ K}$) + Bb (T6, $T_{\text{eff}} \approx 850\text{ K}$)** separated by $0.6''$ is completely unresolved in the image. Right now, your `README.md` treats this purely as a limitation.
* **How It Works in SkyBlink:** Turn spatial blending into a **spectrophotometric discovery feature** inside `SpectrumDrawer.tsx`!
  1. Bundle lightweight, normalized empirical standard template curves ($0.75\text{–}5.00\ \mu\text{m}$, $102$ points, $< 8\text{ KB}$ JSON total) for spectral types `M4V`, `L5`, `T1`, `T6`, `Y1`, `Y4` ($250\text{ K}$), and `AB Aur / T Tauri Disk`.
  2. In the Spectrum Drawer, add a **"Blend & Template Lab"** toggle:
     * Users can overlay a single template (e.g., `T1 Standard` or `T6 Standard`) and see the reduced $\chi^2_{\nu}$ / correlation score.
     * Clicking **"Decompose Sub-Pixel Binary (A + B)"** fits a two-component linear combination $F_{\text{model}}(\lambda) = a \, T_1(\lambda) + b \, T_2(\lambda)$ to the observed SPHEREx spectrum!
     * On **Epsilon Indi B**, the tool proves mathematically and visually that the single $6.15''$ pixel contains *both* a warmer T1 component (dominating the $1.0\text{–}1.3\ \mu\text{m}$ $J$-band peak) and a colder, methane-rich T6 component (carving deep $1.65\ \mu\text{m}$ and $3.32\ \mu\text{m}$ $\text{CH}_4$ troughs)—while the newly added **Gaia DR3 / HST reference pin** on the canvas shows the $0.6''$ sub-pixel pair!

### 🔊 X-Factor 4: Web Audio "Infrared Spectral & Blink Sonification" (*Accessibility + Art & Tech Award*)
* **The Scientific Hook:** Inspired by NASA's official **Chandra/JWST Sonification Project** and blind/low-vision (BLV) astronomy workflows (Wanda Díaz-Merced), sonification turns multidimensional light curves and spectra into auditory signatures using the browser's native **Web Audio API** ($0\text{ KB}$ external dependencies, respects `prefers-reduced-motion`).
* **How It Works in SkyBlink:**
  1. **Spectral Sweep Sonification (`SpectrumSonifier.ts`):** A micro-switch `[🔊 Sonify Spectrum]` in the Spectrum Drawer sweeps a playhead from $0.75\ \mu\text{m}$ to $5.00\ \mu\text{m}$ over $3.5\text{ s}$. Wavelength maps to base frequency (pentatonic harmonic scale from $660\text{ Hz}$ at $0.75\ \mu\text{m}$ down to warm $110\text{ Hz}$ bass at $5.00\ \mu\text{m}$, mirroring photon energy $E = hc/\lambda$!), while flux density ($\mu\text{Jy}$) controls gain and low-pass filter resonance.
     * On **WISE 0855**, the user hears near-total silence from $0.75\text{–}3.5\ \mu\text{m}$, followed by a dramatic warm bass chord swelling in Bands 5–6!
     * On **Epsilon Indi B**, the deep $\text{H}_2\text{O}$ and $\text{CH}_4$ absorption bands are heard as distinct rhythmic acoustic notches!
  2. **Blink Cadence Sonification:** When blinking epochs, an optional subtle telemetry tone shifts pitch by $\Delta f \propto \Delta\text{Flux}$ (for variable stars like **R Draconis**) or stereo-pans left/right proportionally to centroid displacement $\Delta\theta$ (for moving stars like **Barnard's Star**).

### 🎯 X-Factor 5: Automated Statistical Dipole & Variable Triage Boxes (*Backyard Worlds Assistant*)
* **The Scientific Hook:** When volunteers inspect difference frames ($E_B - E_A$), detector noise and imperfectly subtracted background stars compete for attention.
* **How It Works in SkyBlink:**
  1. During pipeline execution (`spherex_pipeline.py`), compute the SNR difference map $\text{SNR}_{\text{diff}} = (I_{E_B} - I_{E_A}) / \sqrt{\sigma_{E_B}^2 + \sigma_{E_A}^2}$ on pixels free of `ARTIFACT_WARNING_MASK`.
  2. Identify paired positive/negative extrema ($\pm 4.5\sigma$ within $1.5\text{–}6.0\text{ output px}$) as **`dipole` candidates** (calculating implied proper motion in $\text{arcsec/yr}$ and position angle in degrees!) and stationary high-significance residuals ($|\text{SNR}_{\text{diff}}| > 5.0\sigma$) as **`variable` candidates**.
  3. Render toggleable, precision monospace HUD targeting brackets (`[ DIPOLE: 10.3"/yr @ PA 356° ]` or `[ VARIABLE: ΔFlux +142% ]`) directly over the difference canvas.

### 📋 X-Factor 6: One-Click "Follow-Up Triage Card" Export (Zooniverse / Talk Board Ready)
* **The Scientific Hook:** Citizen science tools live or die by how easily a volunteer can report an interesting candidate to professional astronomers for follow-up telescope time.
* **How It Works in SkyBlink:**
  1. Add an **"Export Triage Card"** button next to `Copy Link`.
  2. Generates a downloadable **4-panel composite PNG finder chart** (Epoch 1, Epoch 2, Difference Dipole, and 102-Band Spectrum with Artifact Shield stamp) *and* copies a formatted **Zooniverse / Markdown Follow-Up Report** to the clipboard containing ICRS coordinates, epoch MJD baseline, measured centroid shift / flux ratio, active Table 16 bitflags, Gaia DR3 / AllWISE cross-match status, and the reproducible SkyBlink URL.

---

## 3. Additive Contract `1.1.0` Specification (`O2` Orchestrator Task)

Per `STATUS.md` (`API_CONTRACT_VERSION`: O1 = `1.0.0`, post-O1 additive changes = `1.1.0`), all new fields below are **100% optional/additive** so that all $40$ existing `pytest` tests and all $64$ F4 Playwright checks continue to pass without breaking.

### 3.1 Additions to `GET /api/v1/sky` (`backend/models/schemas.py`)
```python
class DetectedCandidate(BaseModel):
    id: str
    kind: Literal["dipole", "variable"]
    ra: float
    dec: float
    x_px: float
    y_px: float
    snr_diff: float
    pm_est_arcsec_yr: Optional[float] = None
    pa_deg: Optional[float] = None
    flux_ratio: Optional[float] = None
    epoch_pair: str
    artifact_clean: bool = True

class GaiaCatalogSource(BaseModel):
    source_id: str
    ra: float
    dec: float
    x_px: float
    y_px: float
    g_mag: float
    pmra_mas_yr: Optional[float] = None
    pmdec_mas_yr: Optional[float] = None
    label: Optional[str] = None
```
* In `EpochEntry.frames`, add optional key `"telemetry_sidecar": Optional[str] = None` pointing to `/api/v1/assets/{target_id}/{epoch_id}_telemetry.json` (containing base64-encoded `float16` surface brightness in $\text{MJy/sr}$ for the active coadd and `uint32` bitwise-OR `FLAGS` on the $240 \times 240$ grid).
* In `SkyResponse`, add:
  * `detected_candidates: list[DetectedCandidate] = []`
  * `gaia_sources: list[GaiaCatalogSource] = []`
  * `core_inpainted_for_display: bool = False`

### 3.2 Additions to `GET /api/v1/spectrum` (`backend/models/schemas.py`)
* In `SpectralChannel`, add:
  * `photometry_method: Literal["aperture", "psf_wing_fit", "diff_aperture"] = "aperture"`
  * `lvf_pa_deg: Optional[float] = None` (position angle of the LVF wavelength gradient for the X-Factor 2 visualizer)
  * `mjd_obs: Optional[float] = None`

---

## 4. New `TASKS.md` Work Packages (Ready to Claim)

Orchestrator: append these tasks (`O2` through `I2`) to `TASKS.md` and dispatch them to your agents in order.

| ID | Owner | Task | Acceptance Criteria | Depends On |
| :--- | :--- | :--- | :--- | :--- |
| **O2** | `orchestrator` | Bump `API_CONTRACT_VERSION` to `"1.1.0"`; add optional `photometry_method`, `lvf_pa_deg`, `detected_candidates`, `gaia_sources`, and `telemetry_sidecar` fields to `backend/models/schemas.py` and `openapi.json`. | All $40$ existing `pytest` tests pass; `openapi.json` updated. | `S3`, `F4` |
| **B8** | `backend` | **Saturated-Star PSF Wing Photometry & Stratified LVF Sampling:** Implement HDU 5 `PSF` wing fitting ($1.2 \le r \le 4.2\text{ px}$) in `spectrophotometry.py` when core pixels have `OVERFLOW`/`SUR_ERROR`; implement `WCS-WAVE`-stratified visit selection (up to $17\text{ visits/band/epoch}$) and tight $r=1.1\text{ px}$ difference-cleaned aperture photometry for `wise_0855`. | Barnard's Star usable channels jump from $1/54 \rightarrow \ge 45$; R Draconis jumps from $0/60 \rightarrow \ge 45$; WISE 0855 B1–B3 contamination eliminated; each target has $\ge 50$ total channels/epoch. | `O2` |
| **B9** | `backend` | **Display Core Inpainting, Inverse-Variance Multi-Band Coadds, Candidate Triage & Fast 3-Epoch Live Blink:** Inpaint saturated core `NaN` holes in display WebPs only; weight `all`/`thermal` coadds by inverse variance; compute `detected_candidates[]` on PSF-matched difference frames; update live arbitrary `/sky` to fetch $2\text{–}3$ epochs of $0.08^\circ$ cutouts (`Bands 3, 5, 6` first) within $12\text{ s}$. | Bright stars render without black core holes; `detected_candidates` populated; arbitrary RA/Dec `/sky` returns $\ge 2$ blinkable epochs in $<12\text{ s}$. | `O2` |
| **S4** | `science` | **Real Gaia/AllWISE Overlays, NEP R Draconis Clustering, Telemetry Sidecars & Golden Cache v2 Rebuild:** Fetch real $240 \times 240$ TAN optical (`DSS2`) and mid-IR (`allWISE`) WebPs via CDS `hips2fits` + real `gaia_dr3_source` astrometric pins (plus HST/literary $0.6''$ Ba/Bb pins for `eps_indi_b`); cluster R Draconis's $2,483$ NEP exposures into $\ge 4$ complete 6-band epochs; emit `{epoch_id}_telemetry.json` (`float16` $\text{MJy/sr}$ + `uint32` flags); rebuild `golden_cache/` and `validation_report.json`. | All $5$ targets have real `ref_optical.webp`, `ref_wise.webp`, `gaia_sources.json`, and telemetry sidecars; `pytest` passes $45+/45+$; `run_five_target_card.py` passes $5/5$ with zero $0/60$ or $1/54$ spectrum caveats. | `B8`, `B9` |
| **F5** | `frontend` | **Physical $\text{MJy/sr}$ Loupe, Real 5-Target Curtain + Gaia Pins, Wing-Fit & Multi-Epoch Spectrum Lab:** Decode telemetry sidecar so cursor HUD displays calibrated $\text{MJy/sr}$ and per-pixel Table 16 flag names; compute LUT stretches on float array; enable real `CrossMissionCurtain` + toggleable Gaia DR3 star/PM pins across all $5$ targets; add multi-epoch spectrum comparison + **1-Pixel Binary Spectral Decomposer (T1+T6 template lab)** in `SpectrumDrawer.tsx`. | Cursor shows $\text{MJy/sr}$ + flag names; curtain works on all $5$ targets; Spectrum Drawer shows wing-fit markers, multi-epoch overlay, and $\varepsilon\text{ Indi Ba+Bb}$ composite T1+T6 fit. | `O2`, `S4` |
| **F6** | `frontend` | **X-Factor Suite — Shift-and-Stack Velocity Sandbox, LVF Visualizer, Web Audio Sonification & Triage Card Export:** Add `[Sky-Fixed vs. Co-Moving Track & Stack]` + parallax ellipse toggle to `BlinkCanvas.tsx`; render LVF iso-wavelength passband strip on spectrum hover; add `[🔊 Sonify Spectrum & Blink]` via Web Audio API; add `[Export Triage Dossier]` (4-panel PNG + Markdown report). | All X-Factor controls match F4 workstation design contract (`#08090b`/`#0e1015`, $1\text{ px}$ hairlines, mono telemetry); `npm run typecheck && npm run build` and Playwright QA pass. | `F5` |
| **S5** | `science` | **Container Rebuild & README v2 Update:** Rebuild `skyblink:final` Docker image, update `README.md` §2–§10 to showcase the resolved limitations and new X-Factor features, and capture updated F6 QA screenshots. | Image $<900\text{ MB}$, 5-target container smoke $5/5$ in $<0.06\text{ s}$, `README.md` reflects v1.1 capabilities. | `S4`, `F6` |

---

## 5. Final Verification Commands for the Orchestrator

Before marking `S5` done, run these exact verification gates in the main worktree:

```bash
# 1. Guardrail check: no hdul[0].data, no naive flags > 0 masking
! grep -rn "hdul\[0\]\.data" backend/ scripts/
! grep -rn "flags > 0" backend/ scripts/

# 2. Rebuild & verify all 5 golden targets + five-target validation card
python scripts/build_golden_cache.py --target all --verify-only
python scripts/run_five_target_card.py

# 3. Verify Barnard's Star & R Draconis have >= 45 usable channels (no 1/54 or 0/60!)
python -c "
import json
for t in ['wise_0855', 'barnards_star', 'eps_indi_b', 'rw_aurigae', 'r_draconis']:
    s = json.load(open(f'golden_cache/{t}/spectrum.json'))
    used = sum(1 for e in s['epochs'] for c in e['channels'] if c.get('is_used_in_photometry'))
    total = sum(len(e['channels']) for e in s['epochs'])
    print(f'{t}: {used}/{total} usable channels')
    assert used >= 40, f'{t} has too few usable channels: {used}'
"

# 4. Run full backend test suite & frontend build + Playwright QA
pytest backend/tests -q
cd frontend && npm run typecheck && npm run build
```