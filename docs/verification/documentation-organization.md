# Documentation organization verification

2026-11-15. This change reorganizes documentation and its readers; it does not
repair the [current archive-search failure](phase6-archive-search-renewed.md).

127 supporting files moved from the top level and former record directory into
topic folders. The two active planning files keep their paths. The new
[documentation index](../README.md) points to current guides, decisions and
verification, with historical evidence identified separately. The
[location map](../reference/file-locations.json) records old/new paths and hashes
at relocation time; Markdown may subsequently change normally.

Scientific JSON and screenshot provenance retain their original bytes. Old
paths embedded in those records are historical identifiers; use the map to find
their new locations. The mutable real-data inventory's location references were
updated, while its approved observation hashes remain unchanged.

Independent verification compared **148 scientific JSON/screenshot files** and
**288 approved observation hashes/files** with a pre-move snapshot; all matched.
The real-only packaging gate passed with the existing frontend distribution.
The backend suite passed **321 tests in 51.36 seconds**, including readers of
the moved scientific evidence. The local Markdown destination checker reports
no missing files; it checks paths, not external URLs or section-anchor spelling.

Executable script paths, generated evidence filenames, the Dockerfile inventory
copy and `.dockerignore` exceptions were updated together. No current container
build is claimed: there is still no usable local Docker engine. Historical
screenshots were not recaptured or given new source identities.

Documentation references inside source files also change their source hashes.
The development API was restarted after this source freeze (PID 17976); health
and target-list requests returned HTTP 200, with all five catalog targets.
This is a local runtime check, not a successful archive search. Scientific
arithmetic, API 1.6.0 and image method 13 remain unchanged. Existing
strict replay records still require their recorded source/environment rather
than an undocumented override for a different checkout.

Validation receipts are retained in
`backend/.cache/phase6/docs-reorganization/`; the move plan and reference-update
log are in `backend/.cache/docs-reorganization/`. No observation data was deleted
or synthesized during the move.
