# Phase 3 independent astrometry measurements

Generated: 2026-11-14T18:58:01.327956+00:00

First and last available recorded D1 exposures per target; independent peak centroids vs fresh Gaia DR3, native and reprojected. Not validation of golden coadds.

Threshold: robust RMS including bias <= 1.5375 arcsec, with at least three suitable stars per exposure. No residual clipping or target-driven threshold tuning.

| Target | Exposure | Stars | Native robust RMS (arcsec) | Output robust RMS (arcsec) | Status |
|---|---|---:|---:|---:|---|
| wise_0855 | level2_2025W19_1B_0241_1D1_spx_l2b-v27-2026-197.fits | 16 | 0.280 | 0.663 | pass |
| wise_0855 | level2_2026W18_2A_0264_1D1_spx_l2b-v27-2026-244.fits | 10 | 0.325 | 0.592 | pass |
| barnards_star | level2_2025W35_1A_0432_4D1_spx_l2b-v27-2026-230.fits | 18 | 0.352 | 0.552 | pass |
| barnards_star | level2_2026W34_2A_0757_1D1_spx_l2b-v27-2026-243.fits | 19 | 0.168 | 0.674 | pass |
| eps_indi_b | level2_2025W17_4B_0077_3D1_spx_l2b-v27-2026-196.fits | 3 | 0.135 | 0.589 | pass |
| eps_indi_b | level2_2026W18_2A_0819_1D1_spx_l2b-v27-2026-244.fits | 5 | 0.182 | 0.464 | pass |
| rw_aurigae | level2_2025W36_1A_0095_1D1_spx_l2b-v27-2026-232.fits | 9 | 0.251 | 0.599 | pass |
| rw_aurigae | level2_2026W36_1A_0476_1D1_spx_l2b-v27-2026-252.fits | 18 | 0.230 | 0.784 | pass |
| r_draconis | level2_2025W23_2B_0206_1D1_spx_l2b-v27-2026-201.fits | 5 | 0.267 | 0.818 | pass |
| r_draconis | level2_2026W28_1A_0104_1D1_spx_l2b-v27-2026-275.fits | 2 | n/a | n/a | insufficient_stars |

## Method and limits

Detection uses image local maxima without Gaia coordinates. Elliptical Gaussian fits use IMAGE minus ZODI, native variance weights, and the conservative hard-plus-warning mask. SOURCE remains usable. Fits with flagged cores, close image peaks, poor shapes, close Gaia neighbors, missing proper motions, or poor Gaia astrometric quality are excluded. Gaia ICRS positions are propagated from J2016.0 TCB to the FITS observation MJD/time scale with SkyCoord.apply_space_motion. Every accepted star's source ID, proper motion, fit, and native/output residual vector appears in the JSON report. Native and output coordinates are measured independently; the output fit is on the reprojected real exposure, not on a rendered WebP.

- Gaussian centroid model is approximate for undersampled asymmetric SPHEREx PSFs.
- No distance/radial velocity or observer parallax correction; candidates with absolute parallax >10 mas excluded.
- Gaia G<=18 neighbors do not rule out all infrared blends.
- No passing-star selection uses the 1.5375 arcsec acceptance threshold.
- Representative individual exposures cannot certify all golden coadds.

The JSON records source URLs, exact query, local download SHA-256, exclusions, bias, robust scatter, raw radial RMS, maximum residual, and above-threshold count. FITS and query responses remain in ignored local cache; saved observations are unchanged.

References: [Gaia DR3 reference epoch](https://www.cosmos.esa.int/web/gaia/dr3), [SPHEREx Explanatory Supplement](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp.pdf).
