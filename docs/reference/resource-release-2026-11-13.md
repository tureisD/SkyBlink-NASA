# Official resources recheck — 2026-11-13

**Status:** Verified 2026-11-13. The challenge page was last published **2026-11-13 03:46 UTC**; its **Resources** tab is now populated. This document records what was released, what changed in the SPHEREx archive, and what SkyBlink did before the 14–15 November event. **B10 and S7 are complete:** contract 1.2.0 and golden revision 3 (DR1+QR3) are current. **B12/F11 (2026-11-14)** enforce the live arbitrary budget (TAP 60 s / sky 120 s / frontend 130 s / cutout 20 s) and real-data-only clean errors. The current suite is **83 tests**; normal operation is real-data only (no automatic fixture fallback).

**Scope:** Official challenge resources (NASA and CSA), live IRSA TAP/SIA/cutout checks, DR1 structure, and the resulting scope decisions. It records the decisions and their implementation; current counts are in `golden_cache/validation_report.json` and `README.md`.

---

## 1. Official Resources tab — complete list

Source: <https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/?tab=resources>

### 1.1 NASA data and resources

| Resource | Link | What it is | SkyBlink use / decision |
|---|---|---|---|
| **NASA/IPAC Infrared Science Archive — SPHEREx resources** | <https://irsa.ipac.caltech.edu/Missions/spherex.html> | The SPHEREx archive entry point: DR1, QR3, QR2, SPLICES, Comet 3I/ATLAS, cloud access, MOST, spectrophotometry/mosaic/cutout/source-discovery tools, documentation. | **Used.** TAP, SIA, cutouts, AllWISE/2MASS/Gaia catalogues, SkyView overlays. |
| **SPHEREx Tutorial Notebooks** | <https://caltech-ipac.github.io/irsa-tutorials/spherex/> | Example Jupyter notebooks for accessing SPHEREx data in Python. The intro notebook now uses **DR1** and documents the DR1 file layout. | **Used as the file-layout reference.** DR1 differences are recorded in §3. |
| **WiseView** | <http://byw.tools/wiseview> | A public WISE viewer used for hundreds of volunteer discoveries; the challenge names it as a model/inspiration. | **Already reflected** in the cross-mission curtain (SPHEREx vs. AllWISE) and blink model. |
| **Gaia Mission Data** | <https://archive.stsci.edu/missions-and-data/gaia> | Gaia mission data; the challenge says to use the latest release, **DR3**. | **Used.** Gaia DR3 pins and catalogue cross-matches; DR3 confirmed as current. |

### 1.2 Space Agency Partner resources — CSA (Canadian Space Agency)

| Resource | Link | What it is | SkyBlink use / decision |
|---|---|---|---|
| **NEOSSat: Observing Asteroids, Space Debris and Exoplanets** | <https://www.asc-csa.gc.ca/eng/satellites/neossat/> | Canada's near-Earth object surveillance satellite; asteroid/comet/space-debris context. | **Optional context only.** No critical-path dependency. |
| **Canadian Astronomy Data Centre (CADC)** | <https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/en/> | Canadian and international telescope/mission archive, including NEOSSat. | **Optional context only.** Could be linked as "other archives"; not ingested. |
| **NEOSSat Data Tutorial** | <https://github.com/asc-csa/NEOSSAT_Tutorial> | Python tutorial for opening and visualising NEOSSat observations. | **Optional context only.** |
| **NEOSSat Dataset** | <https://data.asc-csa.gc.ca/dataset/neossat> | NEOSSat astronomy images; Open Government Licence — Canada. | **Optional context only.** If cited, credit CSA/CADC and the Open Government Licence. |

The CSA block is the main partner material on the Resources tab. It does not change the core challenge: a public SPHEREx blink viewer with the five named targets. It is useful for the "what else can you cross-check?" story, not for the submission-critical path.

The same November 13 drop also includes **Global Offers** and the **Project Submission / Judging & Awards guides**. Those are program materials, not challenge data resources; the eight items above are the complete challenge Resources tab.

---

## 2. What changed in the SPHEREx archive

### 2.1 DR1 is now released (November 2026)

From <https://irsa.ipac.caltech.edu/Missions/spherex.html> and <https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_dr1.html>:

- **SPHEREx Data Release 1 (DR1) is available (November 2026).**
- DR1 contains **reprocessed versions of the QR2 spectral images**.
- DR1 is intended to be used **together with QR3** as a uniformly processed set.
- The tutorial states plainly: **"QR3 and DR1 supersede the earlier Quick Release 2 (QR2), and SPHEREx recommends using QR3 and DR1 over QR2."**
- DR1 also includes an **all-sky cube** with full-sky coverage in the **102 nominal SPHEREx spectral channels**.
- New DR1 DOIs: **10.26131/IRSA678** (spectral images) and **10.26131/IRSA679** (all-sky cube).
- The AWS Open Data mirror `nasa-irsa-spherex` (us-east-1) now has both `dr1/level2/` and `qr3/level2/` prefixes (verified 2026-11-13).

This supersedes the project's 2026-11-08 assumption that the 102-channel all-sky cube was a December 2026 item. The cube exists now; the app still does not claim a 102-band spectrum.

### 2.2 Live TAP coverage on 2026-11-13

Query: `spherex.artifact` joined to `spherex.plane`, `a.producttype='science'`, `a.contenttype='image/fits'`, position at each target's 2025.8 coordinate, `TOP 5000`.

| Target | DR1 artifacts | QR3 artifacts | QR2 artifacts returned | DR1 MJD range | QR3 MJD range |
|---|---:|---:|---:|---|---|
| WISE 0855 | 258 | 0 | 0 | 60800.7–61174.3 | — |
| Barnard's Star | 239 | 119 | 0 | 60902.9–61165.1 | 61268.6–61305.6 |
| Epsilon Indi B | 338 | 120 | 0 | 60789.9–61164.1 | 61305.2–61315.5 |
| RW Aurigae | 226 | 109 | 0 | 60919.4–61111.0 | 61285.1–61299.9 |
| R Draconis | 1,638 | 855 | 0 | 60789.9–61173.2 | 61176.4–61310.3 |

Notes:

- Counts are **artifacts** (detector/exposure rows), not unique visits; a visit usually contributes several detector rows.
- The TAP query returned **no `/qr2/` rows** on 2026-11-13. QR2 may still exist in other services, but it is no longer the current recommendation. Do not describe QR2 as the primary release.
- **WISE 0855 is no longer QR2-only.** It has DR1 coverage (258 artifacts) and no QR3 rows. Revision 3 now uses **DR1** for all three WISE 0855 epochs.
- The existing epoch sets remain valid: DR1 replaces QR2 for the same survey epochs; QR3 supplies the later 2026 epoch where present. The S7 rebuild reused those epochs and did not invent new ones.

### 2.3 DR1 file structure vs. QR2/QR3

Verified with a real DR1 cutout at WISE 0855 (`0.02°`, 2026-11-13):

```text
URL:  .../ibe/data/spherex/dr1/level2/2025W19_1B/l2b-v27-2026-197/3/level2_2025W19_1B_0116_1D3_spx_l2b-v27-2026-197.fits?center=133.75921,-7.24216&size=0.02
Size: 4,037,760 bytes; 8.6 s
HDU 0 PRIMARY   empty
HDU 1 IMAGE     float32
HDU 2 FLAGS     int32 (cutout service returns it decompressed)
HDU 3 VARIANCE  float32
HDU 4 ZODI      float32
HDU 5 EPSF      BinTableHDU, 451 rows × 11 cols, 33×33 ePSF, 5× oversampled
HDU 6 WCS-WAVE  BinTableHDU
```

Changes that matter:

1. **`PSF` became `EPSF`.** Full DR1 MEFs carry a binary-table `EPSF` extension (441 rows for the full detector, 451 in this cutout), not the QR2 `PSF` cube. Do not assume `hdul["PSF"]`. The W0 spike already has an EPSF branch; the normal pipeline does not require the PSF extension.
2. **`FLAGS` is Rice-compressed in full DR1 MEFs** (`CompImageHDU`). Astropy decompresses it transparently; the IRSA cutout service returns an ordinary `ImageHDU` for the cutout. `hdul["FLAGS"].data` remains the correct access path.
3. **URIs contain `/dr1/`.** At check time the release detector recognized only `/qr2/` and `/qr3/`; all **258** WISE 0855 DR1 records came back as `release="unknown"`, `collection="spherex"`. That was a correctness bug and a rebuild blocker. **B10 fixed it** (`3c642ef`): revision 3 now returns `DR1`/`spherex_dr1` and mixed epochs return `DR1+QR3`.
4. **SIA collections are now** `spherex_dr1`, `spherex_dr1_deep`, `spherex_qr3`, `spherex_qr3_deep` (from the DR1 tutorial). B10 updated the SIA fallback to this DR1/QR3 order; QR2 is no longer advertised as a primary fallback.
5. **Cutout service works for DR1** at the verified size; no blocker found.

---

## 3. New IRSA services and what they mean for SkyBlink

| Service | Link | Relevance | Decision |
|---|---|---|---|
| **Moving Object Search Tool (MOST)** | <https://irsa.ipac.caltech.edu/applications/MOST> | Finds IRSA images covering a solar-system object's predicted positions; useful for labelling known asteroids/comets. | **Optional.** Current app does not label solar-system objects; do not add in the critical path. |
| **Source Discovery Tool** | <https://caltech-ipac.github.io/irsa-tutorials/spherex-source-discovery-tool-demo/> | Detects and characterises sources in a SPHEREx region without positional priors. | **Optional.** The app is a viewer; it must not present automated detections as discoveries. |
| **Spectrophotometry Tool** | <https://irsa.ipac.caltech.edu/applications/spherex/tool-spectrophotometry> | Forced-photometry spectra from SPHEREx images. | **Optional validation reference.** Do not replace the measured dense spectra. |
| **Mosaic Tool** | <https://irsa.ipac.caltech.edu/applications/spherex/tool-mosaic> | Custom multiwavelength mosaics; larger fields. | **Optional.** The app's FOV is 0.05–0.20°; larger FOV is a known gap. |
| **Cutout Tool** | <https://irsa.ipac.caltech.edu/data/SPHEREx/docs/cutout_tool.html> | Spatial/spectral cutouts from SPHEREx MEFs. | **Already used** via the cutout URL pattern. |
| **HiPS all-sky cube** | <https://caltech-ipac.github.io/irsa-tutorials/spherex-hipscube/> | Explore the DR1 all-sky 102-channel cube. | **Optional stretch.** Could provide a 102-channel spectrum; not in the critical path. |

The challenge's "Potential Considerations" explicitly mention 102 bands, six detector arrays, spectra on the fly, add/subtract images, configurable FOV, Gaia/WISE overlays, URL coordinate queries, metadata/flags, and Astropy/Aladin. SkyBlink already covers most; the honest gaps are the full 102-band sampling, larger FOV, and solar-system object labelling.

---

## 4. Challenge considerations vs. current SkyBlink

| Consideration | Current state | Gap / action |
|---|---|---|
| Easy updates with the latest release | Golden cache revision 3 uses **DR1+QR3** (built 2026-11-13). | **Done:** B10 + S7; keep the cache-first design. |
| Display the 102 bands | Six detector coadds + dense spectra (24–72 channels/epoch). | No 102-band claim. DR1 all-sky cube is available; optional B11 stretch only. |
| Add the six detector arrays | B1–B6, `all`, `thermal` frames; LVF geometry. | Covered. |
| Spectra on the fly | `/spectrum` saved dense spectra + bounded live extraction (`confidence: "low"`). | Covered; live path stays bounded. |
| Add/subtract images at different times | Difference mode, adjacent pairs, epoch picker. | Covered; direct subtraction, no PSF matching. |
| Choose the field of view | 0.05°, 0.10°, 0.15°, 0.20° presets; client-side crop. | Larger FOV is a gap; Mosaic Tool not integrated. |
| Gaia/WISE overlays | SkyView DSS2/WISE reference layers + Gaia DR3 pins. | Covered. |
| Query by coordinates in the URL | Full URL state and copy link. | Covered. |
| Metadata / contamination flags | Artifact Shield, Table 16 names, telemetry sidecars. | Covered. |
| Astropy / Aladin | Astropy used server-side; custom Canvas, no Aladin. | Covered differently; explain in submission. |

---

## 5. Decisions and action plan

### 5.1 Scope lock

- **Do not add new features before the event freeze.** The code/data are complete; the remaining critical work is deployment and submission.
- **Refresh the data release, not the feature set.** DR1+QR3 is a data-source correction, not a new product.
- **Revision 3 is current; revision 2 is the rollback.** The old revision-2 cache remains valid as a fallback and is labeled honestly as QR2/QR3 (superseded but real).
- **No critical-path dependency on CSA/NEOSSat, MOST, Source Discovery, Mosaic, or the 102-channel cube.** They can be mentioned as related resources or future work.
- **Do not claim 102 bands.** The DR1 all-sky cube exists, but the app's spectra are still 24–72 channels/epoch until a separate integration is measured and documented.

### 5.2 Tasks

| ID | Owner | Task | Acceptance | Status |
|---|---|---|---|---|
| **B10** | backend | Recognize `/dr1/`; accept `DR1`/`QR3`/`DR1+QR3` in `collection`/`release`; update SIA fallback to `spherex_dr1` + `spherex_qr3` (and deep collections if safe); update source labels, error details, and tests. | A live DR1 response shows `release="DR1"`, `collection="spherex_dr1"`; mixed epochs show `DR1+QR3`; existing tests updated; contract version bumped to **1.2.0** (data-value addition, schema unchanged). | **Done** (`3c642ef`; 79 tests) |
| **S7** | science | Rebuild `golden_cache/` revision 3 from DR1+QR3; regenerate spectra/telemetry/overlays as needed; re-run verify, five-target card, and container smoke. | Five targets load; release labels are DR1/QR3; counts re-measured and recorded; no fabricated epochs; revision 2 kept as rollback. | **Done** (`664977e`; 5/5, 17/17) |
| **D2** | orchestrator | Update README, STATUS, TASKS, ROADMAP, AGENTS, pre-event verification, and this document with the revision-3 counts. | Docs match the committed manifests; no stale "QR2-only" or "PSF cube" claims. | **Done** |
| **I3** | orchestrator | Optional: add CSA/CADC/NEOSSat as "related archives" links/credits; no ingestion. | Links and licence credit present; no runtime dependency. | **Done** (Help + README) |
| **B11** | backend | Optional/timeboxed: evaluate the DR1 102-channel all-sky cube for a spectrum endpoint. | Only ship if measured and honest; otherwise record a NO-GO. | **Done — NO-GO** (`docs/research/102-channel-cube-feasibility.md`) |

### 5.3 Revision 3 result (2026-11-13)

- **Golden cache revision 3**, built from live **DR1+QR3**: **5/5** targets, **17** epochs, **17/17** telemetry sidecars, **0** failures. Wall clock **38 min 41 s**, **170** transient IRSA 503 retries; SkyView DSS2 Red / AllWISE overlays and Gaia DR3 pins reused SHA-256-verified.
- **Size:** **12,870,733 bytes across 442 files**; the five real target directories are **8.63 MB**; sidecars total **1,730,788 bytes** (82.6–111.4 KiB each).
- **Used/total spectra:** WISE 0855 **158/164** (43/46, 59/60, 56/58); Barnard's Star **2/215** (1/71, 1/72, 0/72); Epsilon Indi B **228/246** (50/55, 64/72, 67/69, 47/50); RW Aurigae **102/216** (23/72, 41/72, 38/72); R Draconis **0/240**.
- **Per-epoch releases:** WISE 0855 DR1×3; Barnard's Star DR1, DR1, DR1+QR3; Epsilon Indi B DR1, DR1, DR1, DR1+QR3; RW Aurigae DR1, DR1, QR3; R Draconis DR1, DR1, DR1, DR1+QR3. **No QR2.**
- **Verification:** `--verify-only --require-telemetry` 5/5; five-target card **5/5**; container `skyblink:final` **844 MB**, healthy at **105.7 MiB idle**, health version **1.2.0**, five-target smoke **5/5**.

### 5.4 Submission-critical reminder

The resource review does not change the submission deadline or deliverables:

- Public HTTPS URL (none yet).
- Public repository (currently present at <https://github.com/tureisD/SkyBlink> but **private**; make it public or grant judge access before judging if required).
- ~2-minute demo video.
- Submission through the team project page by **2026-11-15 23:59 local time**.
- SI disclosure.

The public URL remains **P0** and is still missing.

---

## 6. Verification log (2026-11-13)

- Challenge page HTML fetched from `https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/`; embedded payload last published `2026-11-13T03:46:20Z`.
- Resources tab extracted: 4 NASA resources + 4 CSA resources (see §1).
- IRSA SPHEREx page fetched; DR1 release line confirmed.
- DR1 overview fetched; DR1 = reprocessed QR2, use with QR3; all-sky cube; DOIs confirmed.
- SPHEREx intro tutorial fetched; DR1 layout and EPSF/FLAGS details confirmed.
- TAP coverage query run for all five targets; counts in §2.2.
- Live `IrsaClient.tap_query` on WISE 0855 returned **258 DR1 records, all `release="unknown"`, `collection="spherex"`** — the B10 label bug is confirmed, not theoretical.
- Real DR1 cutout downloaded and inspected; HDUs in §2.3.
- SIA `COLLECTION=spherex_dr1` returned a valid VOTable; `/SIA2` is not a valid endpoint on this host (the project's `IRSA_SIA2` value points at `/SIA`).
- CSA NEOSSat page, CADC landing page, NEOSSat tutorial, and NEOSSat dataset page returned HTTP 200.
- **B10 merged (`3c642ef`):** `/dr1/` detection, `DR1`/`QR3`/`DR1+QR3` release values, contract 1.2.0; **79 tests passed at merge** (current suite: 83).
- **S7 merged (`664977e`):** revision 3 rebuilt from live DR1+QR3; 5/5 targets, 17/17 sidecars, 0 failures, 38 min 41 s, 170 transient IRSA 503 retries, **12,870,733 bytes / 442 files**, no QR2; verify 5/5 and five-target card 5/5.
- **Container rebuilt:** `skyblink:final` 844 MB, healthy under 2 GB at 105.7 MiB idle, `/api/v1/health` version 1.2.0, five-target smoke 5/5; asset/telemetry/Gaia checks pass.
- Participant FAQ confirms event dates, Nov 13 guides, submission deadline, and SI disclosure. The 2026 Submission/Judging guide files were not publicly retrievable at check time; recheck the Resources page before filling the submission form.

---

## 7. Sources

- Challenge Resources tab: <https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/?tab=resources>
- Participant FAQ: <https://www.spaceappschallenge.org/resources/participant-faqs/>
- IRSA SPHEREx: <https://irsa.ipac.caltech.edu/Missions/spherex.html>
- DR1 overview: <https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_dr1.html>
- SPHEREx tutorials: <https://caltech-ipac.github.io/irsa-tutorials/spherex/> and <https://caltech-ipac.github.io/irsa-tutorials/spherex-intro/>
- CSV/QR releases: <https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_qr.html>
- WiseView: <http://byw.tools/wiseview>
- Gaia at MAST: <https://archive.stsci.edu/missions-and-data/gaia>
- NEOSSat: <https://www.asc-csa.gc.ca/eng/satellites/neossat/>
- CADC: <https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/en/>
- NEOSSat tutorial: <https://github.com/asc-csa/NEOSSAT_Tutorial>
- NEOSSat dataset: <https://data.asc-csa.gc.ca/dataset/neossat>
- DR1 DOI (images): <https://doi.org/10.26131/IRSA678>
- DR1 DOI (all-sky cube): <https://doi.org/10.26131/IRSA679>
- QR3 DOI: <https://doi.org/10.26131/IRSA662>
