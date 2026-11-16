# Explicit indexed archive recovery - API 1.7.0

Approved by the Orchestrator under policy v1.19 for the user-requested online
acquisition repair. Implementation is in the frontend integration worktree.

`discovery=indexed` is an additional accepted value for sky and spectrum query
and provenance fields. It requires `source=archive` and works for named targets
or arbitrary coordinates. Existing live/known/saved behavior remains. The UI
requires an explicit source choice and labels the limited index; failures never
silently select this or another acquisition source.

The index is metadata only, compiled from fresh AWS header scans and targeted
header reads whose addresses were selected from historical catalog records.
It is a bounded subset, not a complete/current all-sky inventory. Geometry
uses conservative spatial bounds followed by full TAN-SIP inverse containment.
Image processing still checks the entire retained field's spectral compatibility
and usable pixels. Index misses raise incomplete/unknown coverage, never NO_DATA.
All image bytes are fetched afresh, with indexed detector/time metadata checked.
No saved images or synthetic observations are substituted.

The reviewed compressed index is shipped with an approval hash, included in
processing identity, and checked before use. Analysis lineage records its hash,
creation time, query, method and incomplete scope. Wide/deep collection membership
is unknown. UI, URL/history, reports, spectra and audio retain the indexed mode.
Scientific thresholds and image method 13 remain unchanged. An accepted visual
pair is not proof of target detection, calibrated photometry or astrophysical
variability. Publishing and GitHub push remain separate, pending branch choice.
