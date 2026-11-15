# Two evidence walkthroughs

These examples teach how to trace a result. They are not discovery claims or
scientific promotion approvals. The machine-readable records and replay procedure
are described in [reproducibility](reproducibility.md); the common definitions
are in [result meaning](result-meaning.md).

## Finite extraction and a comparable visual pair near Epsilon Indi

**Question:** can the recorded D3 images and native aperture calculations be
repeated from their actual inputs, and what would their difference mean?

The curated example uses the two real Phase 3 audit cutouts at the original fixed
ICRS query `(331.0962, -56.8005)` degrees. It is explicitly an arbitrary fixed
position (`target=null`), not a corrected-catalog or proper-motion-tracked target
measurement. The retained cutout width is `0.28625937914128574` degrees; the
compared field is 0.2 degrees. Both spectral samples are extracted directly from
these same padded bytes. This differs from an ordinary separately requested
0.2-degree spectrum cutout and is recorded as such.

| Property | First real exposure | Second real exposure |
|---|---:|---:|
| Observation date, UTC | 2025-04-29 | 2025-05-01 |
| Midpoint MJD, UTC | 60794.065478909 | 60796.581027231 |
| Detector / release | D3 / DR1 | D3 / DR1 |
| Sample wavelength, micrometers | 1.647095371211071 | 1.6472000526576556 |
| Sample bandwidth, micrometers | 0.03940473350857722 | 0.03940635548946218 |
| Native aperture flux, microjanskys | 32628.110570258857 | 32511.938241995605 |
| Approximate error, microjanskys | 194.04642653825385 | 195.47528090990542 |
| Clean / center-selected aperture pixels | 11 / 11 | 14 / 14 |
| Clean residual-annulus pixels | 0 | 0 |
| Field-background clean pixels | 6584 | 6620 |
| Field-background median, MJy/sr | 0.03372088074684143 | 0.03366576135158539 |
| Display normalization factor | 1.0 | 1.0016936743331213 |

These digits identify reproducible calculations, not physical measurement
precision. Both channel flags are `2097152` (`BIT_SOURCE`); this marks a catalog
source and is not a bad-pixel flag. Both channels are finite and eligible under
the current rules. Both carry `FIELD_BACKGROUND_FALLBACK`: the local annulus
has no clean sky pixels, so the supported field median supplies the background.
The field is crowded, and these numbers must not be described as isolated,
calibrated total fluxes for a particular resolved source.

The image matcher checks 54,756 retained output pixels, a wavelength separation
no larger than one quarter of the narrower bandwidth, and a bandwidth ratio of
at least 0.8. The separate exact D3 calibration-product comparison and independent
native-image astrometry pass their declared prerequisites; see
[the science report](../verification/phase4-science-verification.md). Those checks support using
this pair as a bounded visual/replay example. They do not repair the failed
Phase 3 control-star stability result or replace the missing Phase 4 holdout.

The historical bucket IDs are `2024_E1` and `2025_E1`; the actual exposure dates
are in 2025, about 2.52 days apart. IDs identify buckets, not observation years.
New display labels use the actual bounds. This is a concrete reason to avoid
inferring a six-month motion baseline from an old epoch name.

The raw input hashes are:

```text
9d4fb57bf944c155ca65c8885581cb2d36cb4152fe382ddf0980072c363a179c
730d8183e77882b0a37e61256250956d67b5b7730db465e402dbae4337e05661
```

The curated image analysis ID is
`sha256:ff6a61bd4ebab141f2bdaf8e7f6e92927b9412f5dca8adae6413c8264e750c75`.
Its native spectrum analysis ID is
`sha256:441f928c80516d19d068572041deafffb70474edb14494583e24e40a8e09e245`.
The spectrum record explicitly links the image analysis and shared input hashes.
Each contains source URLs, extraction coordinates, diagnostics and method identity.

**Supported conclusion:** these real images pass the implemented visual
comparability screen, and the recorded arithmetic can be replayed. The small
difference in aperture sums is not established astrophysical variability. The
changing number of center-selected pixels, crowding, background fallback and
uncalibrated systematic errors require caution. A more appealing plot does not
remove these limitations.

## Unavailable measurement: R Draconis

**Question:** does a blank/all-null spectrum mean the star is absent or has zero
flux? No. A present real exposure can fail measurement eligibility.

The unchanged revision-3 R Draconis product contains 240 channels with zero
usable measurements. API 1.4 reports the actual usable count and preserves null
flux/error values. It does not retrofit unknown extraction lineage or causal
reason codes into that legacy file. Its stored creation date remains stable
across requests. This legacy example explains the UI state, but a legacy JSON
hash alone does not establish native recomputation.

For a new native replay, inspect the retained record's `expected_channel`,
`diagnostics` and extraction position together. `NO_CLEAN_APERTURE_PIXELS`
means the pixel exclusions leave no valid measurement. A hard-bad extraction
center independently rejects eligibility. `UNSUPPORTED_BACKGROUND` means the
surrounding clean sky cannot support the subtraction, even when some aperture
pixels survive. The report must preserve nulls and these distinct reasons;
the renderer must not draw a zero-valued spectral curve or interpolate through
missing measurements.

The corrected-coordinate Phase 4 stage now supplies the native null replay case:
**34 present channels, zero finite fluxes and zero usable measurements**. Every
channel has `NO_CLEAN_APERTURE_PIXELS` and `HARD_BAD_EXTRACTION_CENTRE`; thirty
also have `UNSUPPORTED_BACKGROUND`. These counts concern the bounded retained
inputs, not every observation available in the archive.

For example, the real 2025-04-27 D6 sample has wavelength
`4.606672885238342` micrometers, bandwidth `0.03675064789231542` micrometers,
center flags `69206022`, twelve center-selected aperture pixels and **zero clean
pixels**. Its extraction position is
`(248.16724295699575, 66.75502266388264)` degrees, propagated to the exposure
time from the recorded corrected reference solution. The field background is
supported by 1,192 clean pixels, so this particular null is explained by the
aperture/center exclusions, not unsupported background. Both flux and error are
null, `clean_fraction=0`, and `is_used_in_photometry=false`.

The native routine only evaluates the residual annulus when it can compute a
flux. In a null extraction the internal zero annulus counter means no annulus
pixels were used; it must not be interpreted as an independently measured lack
of surrounding sky support. Inspect the field-background diagnostics separately.

This input's SHA-256 is
`39d42265c6b9a7d9ef4714ecd3fe67aed57d9a99960de30bf61e7e0d89af3d65`.
The complete null analysis ID is
`sha256:c4b8656866e0e7d9e028c14a862aafc82fe5870c220b759e060a6e1953833e34`.
Its separate retained bundle is indexed in
[the null bundle manifest](../evidence/phase4/phase4-null-bundle-index.json). The four selected
epoch groups span actual dates from 2025-04-27 through 2026-09-27; samples within
a spectrum group are not asserted simultaneous. This is a real quality-failure
example, separate from the unchanged legacy product. See
[verification](../verification/phase4-verification.md) for the strict replay result.

**Supported conclusion:** this extraction cannot provide a usable measurement
under the declared method. It provides no numerical upper limit and does not
establish that the object is faint, absent, variable or scientifically detected.
The next scientific action is to inspect the actual masks, sky support and other
observations, not to fill the gap with a model or simulated spectrum.
