# Phase 4 continuation: archive-first contract decision

The user explicitly requested fresh upstream acquisition, broader coordinate
support and resolution of the remaining scientific gates. The Orchestrator
approves API 1.5.0 with the following coordinated behavior. This supersedes the
historical cache-first requirement; it does not relax scientific acceptance.

- `/sky`, `/spectrum` and `/targets` accept `source=archive|saved`, default
  `archive`. Saved mode is explicit and catalog-only. It never automatically
  substitutes for a failed archive request. Historical revision-3 products and
  their original coordinates remain available only through saved mode.
- Archive mode uses the reviewed corrected catalog reference solutions and
  queries IRSA; arbitrary positions retain the supplied ICRS coordinates. All
  archive requests have bounded discovery/download/processing deadlines.
- An archive request bypasses precomputed products and the application cutout
  cache. Identical concurrent requests may share a running acquisition. Local
  retention of fetched bytes remains necessary for replay and is not an offline
  substitute for discovery. Archive-derived assets use distinct `live_` keys.
- Current image, difference and telemetry filenames include the exact content
  SHA256. Refreshing the same query cannot overwrite pixels referenced by an
  earlier response. Image method/cache version 11 records this publication
  correction; retained records still identify their original source revision.
- Optional provenance fields identify `data_access` (`archive` or `saved`),
  comparison status/reason and discovery limitations. A single real observation
  may be displayed when no compatible pair is found, including incomplete
  downloads. It has no difference products and makes no temporal-comparison
  claim. No usable downloaded observation still returns an explicit error.
- Both products expose `discovery_status` (`complete`, `partial`, `unknown`)
  and `missing_collections`. A successful subset of a partially unavailable
  archive may be displayed with that limitation beside it. This is not a
  complete/latest inventory. Partial empty discovery remains an upstream error,
  never proof of no coverage. Strict science validation/rebuild queries keep
  complete discovery as the default; the online viewer explicitly opts into
  displaying real partial results. All comparison and measurement gates remain.
- A successful request is not a claim of all-sky temporal coverage, calibrated
  variability or a detection. Universal coordinate handling means correct
  geometry, explicit coverage/quality/availability states and no fabricated
  observations; independent science checks define narrower measured scope.

The frontend must distinguish archive and saved mode, use corrected coordinates
only with archive products, allow the same online request budget for named and
arbitrary targets, and display the absence of an eligible comparison. Field/type
additions and validation results are recorded with the final implementation.
The Orchestrator approves a conservative eligibility correction, reviewed with
the science and frontend agents: current archive measurements require a full
clean centre-pixel aperture contained in the native image, at least ten clean
local-annulus pixels, supported field background and no hard-bad centre. Finite
partial sums and field-background-only estimates remain visible but are marked
ineligible. They are never corrected by inventing missing flux. The existing
centre-pixel weights, constant WCS pixel area and approximate errors remain;
the proposed exact-overlap/SAPM refinement failed its preregistered scatter gate
and is not adopted. Eligibility is necessary support screening, not proof of
isolation or calibrated variability. Saved products retain historical rules.
Native method version 2 / spectrum cache schema 6 records this distinction.

Live download stages reserve processing time and may retain completed real
inputs when the stage expires; every unavailable input is recorded. Image pair
selection has a bounded search stage; an exhausted search may display one
actual epoch with `COMPARISON_SEARCH_BUDGET_REACHED`, never a fabricated pair.
Strict rebuild/science mode keeps complete discovery and strict selection.

Old replay bundles retain their recorded source;
they are not relabeled as reproductions of the new implementation.
