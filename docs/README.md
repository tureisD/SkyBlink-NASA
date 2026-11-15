# SkyBlink documentation

Start with the current guides below. Dated verification reports describe what
was tested at that checkpoint; they are not promises about today's archive
availability or broader scientific accuracy.

**Current status — 2026-11-15:** API 1.6.0, image method 13. Fresh archive
discovery remains unavailable in the tested environment, including through the
official Explorer. Explicit known-exposure mode can download the five catalog
fields online, but cannot discover new coverage or serve arbitrary positions.
Publishing is deferred and the current container remains unverified.

## Start here

| What you need | Read |
|---|---|
| Prepare the video and two-speaker presentation | [Illustrated video guide and two recorded examples](video.md) |
| Use the interface, compare dates and inspect spectra | [Observing guide](guides/observing-guide.md) |
| Understand what a result does and does not establish | [Result meanings](guides/result-meaning.md) |
| See current blockers, priorities and time estimates | [Current limitations and next steps](current-limitations-and-next-steps.md) |
| Follow the implementation phases | [Audit and remediation plan](audit-and-remediation-plan-2026-11-14.md) |
| Trace inputs and reproduce recorded arithmetic | [Reproducibility](guides/reproducibility.md) and [real evidence walkthrough](guides/phase4-evidence-walkthrough.md) |
| Write the data, architecture and mathematics documentation | [Documentation writing plan](plans/documentation-writing-plan.md) |
| Run, contribute to or prepare a release | [Contributing](guides/contributing.md) and [deployment](guides/deployment.md) |
| Understand real-data requirements | [Real-data policy](guides/real-data-policy.md) |

## Current evidence

- [Renewed archive-search investigation](verification/phase6-archive-search-renewed.md): official Explorer, alternate TAP routes and remaining blockage.
- [Discovery diagnosis and download recovery](verification/phase6-live-discovery-diagnosis.md): method-13 scope, actual WISE acquisition and replay.
- [Local Phase 6 checks](verification/phase6-verification.md): production serving, spectra, keyboard and browser evidence, with release gates still open.
- [Scientific validation and its restricted scope](verification/phase4-science-online-verification.md): controls, exclusions and the rejected refinement.
- [Current illustrated guide screenshots](screenshots/guide-20261115/): numbered controls and evidence shared by the README, video guide and in-app Help; `origins.json` identifies the retained real responses and capture sources.

## Folder guide

| Folder | Contents |
|---|---|
| [guides/](guides/) | Instructions for users, contributors and operators |
| [plans/](plans/) | Documentation and interface design/acceptance plans |
| [decisions/](decisions/) | Versioned API, acquisition and processing decisions |
| [reference/](reference/) | Replay schema, release/event references and file-location map |
| [verification/](verification/README.md) | Human-readable test and investigation reports, current and historical |
| [research/](research/) | Feasibility studies and acquisition-source reviews |
| [evidence/](evidence/README.md) | Machine-readable evidence grouped by phase; immutable records retain their original bytes |
| [screenshots/](screenshots/) | Dated UI captures and their original provenance |

The two active planning files remain at this folder's top level to keep their
existing paths stable. Other files were relocated without deleting evidence.
[File locations](reference/file-locations.json) maps old paths to new paths and
records hashes before and after the move. Paths embedded inside historical JSON
are preserved as recorded; use that map when locating a referenced document.
See [organization verification](verification/documentation-organization.md) for
the evidence-preservation and reader checks.

The [repository README](../README.md) covers local startup. [AGENTS.md](../AGENTS.md)
is the engineering contract; [STATUS.md](../STATUS.md) retains checkpoint history.

Check local Markdown links with `python scripts/check_docs_links.py` from the
repository root. This checks file destinations, not external availability or
scientific claims.

Public release: [source snapshot and export scope](verification/public-snapshot.md).
