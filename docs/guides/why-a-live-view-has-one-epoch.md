# Why an online field can return one image

Blinking needs at least two usable observations of the same field. One returned
epoch cannot reveal temporal movement or change; the app should let you inspect
that image while explaining why comparison is unavailable.

`PARTIAL_DOWNLOAD_NO_MATCHED_PAIR` means some candidate downloads were missing
and the completed subset did not establish a compatible pair. It does **not**
mean the archive has only one observation, and it does not prove the missing
files would have supplied a valid comparison. The same response can arise from
upstream errors, a bounded request budget and incompatible completed visits.

Discovery can also be incomplete before any pair search starts. If
`discovery_status` is `partial`, `missing_collections` identifies searches that
did not complete. A successful collection can return one real epoch while
another collection is unavailable. The UI calls this "Archive search
incomplete", including when `comparison_reason` is null. A later retry may
recover the missing search, but the application cannot guarantee upstream
availability.

SPHEREx observations are not ordinary photographs through an unchanged filter.
The wavelength at a sky position changes with its location on the detector.
Two observations can therefore look different because of wavelength sampling,
even when the source has not changed. The app checks wavelength, bandwidth,
coverage and usable pixels before presenting a visual pair. See
[IRSA's product description](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/).
These are visual-comparison checks, not calibrated variability measurements.

The earlier retrieval strategy spread downloads across independently selected
visits and grouped the queue by epoch. It could spend the available time on
images that never formed a pair. The approved repair prioritizes candidates
across different epochs and downloads both sides together, using archive
footprints only to rank candidates. Actual spectral and image checks still
decide whether the pair is usable. The implementation and measured outcomes
are recorded in [the retrieval decision](../decisions/comparison-retrieval-decision.md).

When a single epoch remains, retrying online may recover a transient download
failure. Explicitly requesting a smaller field can help when wavelength or
coverage agreement fails across a wider image, but changes the field and does
not guarantee a comparison. Saved examples are a separate historical source;
they are never substituted automatically and retain their limitations.

Even with a passing pair, a visible difference is not automatically motion.
Artifacts, blending, spectral response and point-spread functions can also
change appearance. A source can be too faint or saturated for useful comparison.
Inspect the dates, actual bands and quality evidence before interpreting a
residual, and distinguish catalog reference markers from measured displacement.
