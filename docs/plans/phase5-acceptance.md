# Phase 5 acceptance and review protocol

Approved 2026-11-15 before implementation validation. The user authorizes the
Phase 5 overhaul; repository policy v1.8 replaces the former dense HUD design
requirements. API 1.5 and all scientific processing remain unchanged.

The design must make the field, dates, spectral context and most consequential
limitation readable before specialist details. Evidence must distinguish origin,
comparison eligibility, measurement support and validation scope. A legacy
saved result cannot acquire scientific validation through a new visual style.

## Approved capability map (no API change)

| UI fact | Existing evidence | Missing/historical handling |
|---|---|---|
| Origin | `provenance.data_access`, release, explicit real-only guard | Unknown source is not proof of fresh acquisition |
| Comparison | `comparison_status`, `comparison_reason`, actual returned pair/bands | Saved/absent status is unvalidated; one epoch cannot support temporal comparison |
| Dates | Epoch observation range, with recorded date fallback | Never reinterpret an epoch ID as a date |
| Spectrum availability | Finite flux/error plus `is_used_in_photometry`, per-channel reasons | Null and finite-but-excluded are distinct; no counts inferred from chart visibility |
| Artifact scope | Aperture status versus frame-wide fraction | Explain the different scopes; no global trust score |
| Display quantity | Telemetry quantity, contributing band, normalization metadata | Unknown plane remains unknown; no raw-flux claim for normalized intensity |
| Technical lineage | Analysis ID/link and channel provenance where provided | Legacy missing record is explicit; no invented hash/receipt |
| Validation | Documented Phase 4 independent study and its tested scope | No response-level field certifies the selected arbitrary field; label not established |

Sharing may serialize a versioned query and selection, and retain the expected
analysis ID to detect changed results. It must not promise server replay simply
because a hash is in a URL. Re-query and pinned scientific replay remain distinct.

## Review tasks

Use real saved observations explicitly for repeatable UI checks. Any retained
archive response used in an isolated browser test must identify its original
record and interception; it must never become a product fallback.

1. Identify the field, source, dates and limitation before opening Help.
2. Select and step observations; verify the date labels and selected comparison.
3. Open a spectrum; distinguish present, finite and eligible samples. Inspect
   the all-null R Draconis case, partial samples and signed error extents.
4. Locate methods and lineage without losing the comparison.
5. Share and restore selection paused; disclose missing/revised analyses and
   unsupported display state. Export the same selected observations.
6. Recover from an archive failure with Retry, Search or explicit Saved mode;
   cancel a pending query and ensure stale completion cannot replace it.
7. Complete essential actions at 320/390 pixels without searching a horizontal
   ribbon. Check modal forward/backward focus, Escape and trigger restoration.

Measure controls and visible contrast. Follow the
[W3C dialog pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/)
for containment and inert background. The
[AA target criterion](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html)
uses 24 CSS pixels with defined exceptions; larger mobile targets are a design
goal. Initial pause, manual stepping and reduced-motion behavior are required.
An 8 FPS cap is not proof that actual image flashing passes WCAG thresholds.

## Evidence boundaries

Record browser/viewport, checks, actual failures and fixes, screenshots and
commands in `phase5-verification.md`. Typecheck/build, real-only packaging,
semantic/share tests and actual browser operation are engineering evidence.
They do not substitute for the plan's five novice/three expert participant
study, assistive-technology testing or quantitative flash analysis. Those
acceptance items must remain explicitly open when not performed.

The reviewer should reject a beautiful empty shell, a hidden limitation, a
success-looking all-null chart, inaccessible mobile navigation, unsupported
discovery claims or report/workspace disagreement. No invented observation or
confidence score is permitted. Screenshots and layout studies are UI evidence,
not new scientific datasets.
