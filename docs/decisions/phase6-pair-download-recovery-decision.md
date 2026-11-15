# Bounded recovery of incomplete comparison downloads

2026-11-15. Orchestrator-approved implementation scope; API 1.6.0 remains unchanged.

The user's default archive requests fail during live metadata discovery. Direct
requests outside SkyBlink reproduce the failure; this decision does not repair
or conceal that upstream problem.

A separate explicit known-exposure WISE control returned one epoch in 25.875
seconds. Two real FITS inputs completed, but each belonged to a different
detector/date pair. Their partners hit the 18-second candidate-round deadline.
The bounded candidate list had only two pairs, so the existing second-attempt
allowance was never exercised through a later overlapping proposal. The search
ended despite time remaining within its overall budget. Baseline receipts are
preserved under `backend/.cache/phase6/discovery-diagnosis/known-control/`.

## Approved change

- Image processing/cache revision 13 identifies the changed acquisition policy;
  the native image arithmetic and scientific eligibility gates remain unchanged.
- After the initial candidate sweep, allow one completion pass over promising
  incomplete pairs with an already downloaded usable partner.
- Retry only missing inputs, with at most two batch attempts per input across
  the search. A batch retains the existing bounded transport retry policy.
- Respect the existing absolute request/search deadline and reserve for producing
  an observed image. Exhausted time must still produce an honest limited result
  or error, not an unbounded retry loop.
- Retain successful bytes within the same job; do not reread a saved product or
  local input cache in fresh archive mode.
- Keep failed-attempt lineage and final missing-input accounting distinct. A
  successful later download does not erase an earlier failure.
- Do not retry fully downloaded pairs rejected by the wavelength/support gates
  in an attempt to change the scientific answer.

## Verification required

Regression checks must exercise a missing partner recovered on its second
attempt, the attempt cap, exhausted budgets, no duplicate successful download,
and no retry of complete rejected pairs. Independent validation must retain the
original failed control, verify a new actual-server response and its fresh input
receipts, and replay an accepted method-13 product if available. Any remaining
single-epoch or transport failures stay visible.

Default live discovery requires its own successful current search and image
build before it can be called repaired. Known-mode success alone cannot satisfy
that requirement.

## Recorded outcome

Implemented and loaded on the actual development API. The backend suite passed
319 tests; two additional test-only deadline cases then passed in a focused
20-test run. These checks cover a recovered and unrecovered missing partner,
retained failure history, no duplicate successful input, no retry of a complete
rejected pair, no completion after the search deadline, and clamping a retry to
five seconds when only five seconds remain.

One fresh method-13 WISE known-mode request returned a matched two-epoch D6
comparison in 34.375 seconds. Two D3 download failures remain recorded. That
request succeeded in its initial round; it is not a live measurement of the
completion pass's benefit. Independent verification passed for two fresh inputs
and twelve served assets; strict replay passed without an override. Live metadata
discovery remains unresolved. See [the complete diagnosis](../verification/phase6-live-discovery-diagnosis.md).
