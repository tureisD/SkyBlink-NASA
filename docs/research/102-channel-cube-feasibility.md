# DR1 102-channel all-sky cube — feasibility (B11)

**Date:** 2026-11-14  
**Status:** **NO-GO for a live on-demand endpoint** and **not shipped** as a UI feature before submission. The existing per-epoch dense spectra remain the delivered product.

---

## 1. What was tested

The SPHEREx DR1 all-sky HiPS cube is documented in the IRSA tutorial:

- HiPS viewer: <https://irsa.ipac.caltech.edu/data/hips/SPHEREx/spherex_allsky_cube>
- FITS data root: <https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/hips5_cube/hips_20261026>
- Tutorial: <https://caltech-ipac.github.io/irsa-tutorials/spherex-hipscube/>

Measured properties:

| Item | Value |
|---|---|
| Cube depth | **102 layers** (0.753–4.988 µm) |
| Tile size | 512 × 512 pixels |
| HiPS order | 5 (nside 32) |
| Pixel scale | **0.0035786° = 12.88″/px** |
| Tile size on disk | **320,909,760 bytes (321 MB)** |
| FITS HDUs | `IMAGE` (102,512,512), `NHITS`, `FLAGS`, `SPECTRAL_CHANNELS`, `WCS-WAVE` |
| Five targets | each falls in a valid Norder5 tile; all five HEAD requests returned 200 and 320,909,760 bytes |

WISE 0855 test:

- HEALPix pixel: **10226**, tile `Norder5/Dir10000/Npix10226_cube.fits`
- Download: **320,909,760 bytes in 88.3 s**
- Extraction (5-pixel aperture, 20–30 pixel annulus, 102 planes): **0.1 s**
- Result: **100/102 finite channels**; the two blank dichroic layers are omitted/nulled.
- Wavelength coverage: **0.753–4.988 µm**, 102 channels with detector/subchannel metadata.

The extraction is a simple aperture sum with a median annulus, matching the IRSA tutorial's quick-look method. It is **not** a calibrated per-epoch spectrum.

## 2. Why it is not shipped

1. **Cost per position.** One 321 MB tile and ~88 s download sit at the edge of the app's **120 s live `/sky` budget** (130 s frontend) before any cache/extraction overhead, and are unsuitable for a public container.
2. **It is a mosaic, not an epoch.** The cube is an all-sky visualization product; the tutorial explicitly says to use the IRSA Spectrophotometry Tool for scientific measurements. It cannot replace the per-epoch 24–72-channel spectra that make the blink comparison meaningful.
3. **Spatial resolution is much coarser.** The cube is 12.88″/px; a 5-pixel aperture radius is ~64″ (about 129″ across), not the app's 12.3″ aperture, and would need its own caveat.
4. **Contract/UI risk.** Adding a 102-channel endpoint and a second spectrum mode before submission would require an API/contract change, caching design, and a careful UI distinction between mosaic quick-look and per-epoch spectra. The value does not justify the risk now.
5. **Honesty.** Shipping a 102-channel curve without the "mosaic quick-look, not per-epoch, not science-grade" caveat would overclaim. The current README correctly says there is no 102-band claim.

## 3. What would be reasonable later

A **precomputed static quick-look** is feasible:

- Five target tiles × 321 MB = **~1.6 GB** of downloads (~8 min at the measured rate).
- Store only ~102 points per target (JSON, a few KB), with wavelength, bandwidth, aperture sum, flags, and NHITS.
- Label it clearly as **all-sky mosaic quick-look** and keep it separate from the per-epoch dense spectra.
- Do **not** call it a 102-band per-epoch spectrum, and do not use it for discovery claims.

That is an optional future enhancement, not part of revision 3.

## 4. Decision

- **Live `/api/v1/cube-spectrum`:** NO-GO.
- **UI integration before submission:** NO-GO.
- **Existing per-epoch spectra:** unchanged; still 24–72 channels/epoch, measured from Level 2 cutouts.
- **B11 status:** evaluated and closed as NO-GO for the current build.

## 5. Reproducibility

The spike used `astropy_healpix` to map the target to Norder5 and `astropy.io.fits` memmap + NumPy aperture sums. The measured tile URL for WISE 0855 is:

```text
https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/hips5_cube/hips_20261026/Norder5/Dir10000/Npix10226_cube.fits
```

The other four targets map to pixels 7945 (Barnard's Star), 11391 (Epsilon Indi B), 277 (RW Aurigae), and 2928 (R Draconis); every tile is 320,909,760 bytes.
