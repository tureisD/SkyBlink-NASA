# Current live-discovery diagnosis

2026-11-15. The user's repeated default archive-search failures are reproduced. **No repair of live discovery is established yet.** Explicit known-exposure acquisition is a bounded workaround, not a successful new archive search; it must never be reported as fixing the default path.

## Runtime and health are separate from discovery

The actual API listener on `127.0.0.1:8000` is PID 15352, API 1.6.0, with the correct repository working directory. Read-only inspection found no explicit backend setting overrides or proxy environment endpoints; the system proxy lookup was also empty. The health endpoint returned HTTP 200, `status=ok`, `irsa_reachable=true`.

That reachability field checks `TAP/availability` XML, cached for up to 60 seconds. It does **not** execute a science-table or spatial-discovery query. Healthy API/availability responses therefore do not contradict failed catalog searches. Runtime/configuration evidence is retained in `backend/.cache/phase6/discovery-diagnosis/runtime.json` and `summary.json`.

## Independent reproduction

These were bounded, read-only metadata requests, not full image builds or known-exposure requests:

| Request | Independent client | Observed outcome |
|---|---|---|
| SPHEREx DR1, WISE position, zero-radius circle, MAXREC=1 | Windows curl 8.13 / Schannel / HTTP 1.1 | Timeout at 20.016 s, zero bytes received; remote IP 134.4.54.42 |
| Exact same URL | Python httpx / OpenSSL / HTTP 1.1 | Read timeout at 20.719 s |
| Official ALLWISE example position, radius 0.01°, HTML output, no MAXREC | Python httpx | Read timeout at 20.625 s |
| Exact official SPHEREx archive-guide HTML example, RA 127.69444°, Dec −39.17760°, radius 0.01°, no MAXREC | Chromium navigation | Timeout at 20.010 s |

The [IRSA SIA guide](https://irsa.ipac.caltech.edu/ibe/sia.html) documents the endpoint, positional intersection, output formats and optional row limits. The [SPHEREx archive guide](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access/) supplies the exact SPHEREx example tested in the browser. Reproduction with that example means SkyBlink's zero-radius or MAXREC choices are not a sufficient explanation for the observed SIA failure. Independent clients also show that the symptom is not confined to the application's Python transport.

Receipts: `backend/.cache/phase6/discovery-diagnosis/independent-transport.json`, `official-spherex-browser.json`, curl headers, and the combined `summary.json`. A bounded timeout does not establish permanent downtime, global unavailability to every network, or the precise failing upstream component. No successful metadata body was fabricated or substituted.

## TAP distinction and remaining diagnosis

The backend agent independently received HTTP 200 in 0.797 s for a tiny TAP schema query using the documented `REQUEST=doQuery`, `LANG=ADQL`, `QUERY`, `FORMAT=votable` and `MAXREC=1` parameters. This proves some TAP requests can execute; it does not establish availability of the SPHEREx science tables, spatial predicates or artifact joins. Direct SPHEREx artifact queries using both documented uppercase and existing lowercase parameters timed out after 20.719 and 20.641 s; a single-plane query timed out after 20.750 s. A constrained one-detector spatial join with a 65-second read budget also timed out after 65.750 s. Changing only parameter casing therefore has not demonstrated a repair.

An asynchronous TAP job was accepted, but remained `QUEUED` throughout 12 bounded polls over approximately 43 seconds, returning no science rows. Abort/delete responses did not establish removal: subsequent state remained queued, so cleanup was explicitly unconfirmed. These targeted failures and the job receipts are retained under `backend/.cache/phase6/live-discovery-repair/`, including `tap-data-probes.json`, `tap-spatial-long.json` and `async-current/`.

No broader probe matrix, runtime workaround or permanent-outage claim is justified by these observations alone. The next decision depends on an actual successful science-metadata query or a meaningful longer/alternative response. Until then, default live acquisition remains unreliable in this environment; named catalog users may explicitly choose known exposures with fresh FITS downloads, and arbitrary coordinates still require working live discovery. Saved data remains a separate explicit historical mode.

## One fresh known-exposure control

After coordination confirmed no other API build was active, one WISE 0855 `source=archive&discovery=known&size=0.2` sky request was made to the actual port 8000, with a 150-second caller timeout and no retry. It returned HTTP 200 in **25.875 seconds**, but only **one epoch**, explicitly labeled `unmatched_single_epoch` / `PARTIAL_DOWNLOAD_NO_MATCHED_PAIR`.

Two fresh FITS downloads succeeded (a 2025 D3 exposure and a 2026 D6 exposure); both counterpart downloads recorded deadline exhaustion. These different detectors did not establish a comparable same-band pair. The result therefore confirms that fresh file acquisition can still work, **not** that known mode reliably restores blinking and certainly not that live discovery works. No missing epoch or matched comparison was invented.

The independent integrity check passed the retained input, current source identity and served output hashes. Response, immutable record, timing and audit are retained in `backend/.cache/phase6/discovery-diagnosis/known-control/`; analysis ID is `sha256:01fe8b44b8c1a63809bf05ea7924fa152063b9db75b147891073d7c6c0afba76`. This single attempt was not repeated to obtain a more favorable outcome.

## Separate bounded acquisition repair

The baseline exposed a local scheduling limitation: after a short download round failed, missing partners could remain marked attempted even though substantial request budget remained. Image/cache method 13 adds one completion batch after the ranked sweep, for at most two missing partners of otherwise usable downloaded candidates, with no more than two attempts per input. The extra batch is capped at 30 seconds within the original search deadline. Successful fresh input bytes remain within the same job; the wavelength, background, mask and comparison gates are unchanged.

This is a repair to bounded file acquisition, **not** to metadata discovery. Focused regressions cover controlled first-round failures, at-most-once partner retry, reuse of successful bytes, retention of failure history, and no retry of a completed science-rejected pair. Such isolated tests are not fresh archive acceptance. The full backend suite passed 319 tests with one warning in 50.11 seconds on the frozen runtime source. Two subsequent test-only additions verify that an expired search budget prevents completion and five seconds remaining clamps the retry window to five seconds; the focused rerun passed 20 tests. This is **321 distinct passing cases across the full and focused runs**, not one full 321-test execution.

## Single post-fix runtime check

After restarting the actual API on port 8000 (PID 7496), one request with the **same** WISE known query returned HTTP 200 in **34.375 seconds**, with two epochs and `matched_visual`. Two fresh D6 files produced the comparison; both D3 downloads returned HTTP 503 and remain explicitly recorded. The resulting analysis is `sha256:62409c5a0cd88218662d3420d60ae677366da90d5e66d6d37f21218c9ab625fb`, method `matched_image_comparison/13`.

The real request succeeded in its initial ranked round. **It did not enter the completion retry batch**, so its success cannot be attributed experimentally to that new branch. The branch has deterministic regression evidence; this single runtime request establishes a fresh known-mode comparison under the new implementation, without promising repeat reliability. No automatic caller retry or extra build was used to obtain this result.

Independent integrity verification passed both retained fresh input hashes, current processing-source identity and all **12 served output asset hashes**. Strict offline replay passed source/environment/input checks and numerical comparison without drift overrides. Evidence: `backend/.cache/phase6/discovery-diagnosis/known-postfix/control.json`, `integrity.json`, immutable response/analysis files and `replay/replay-report.json`.

Default live discovery remains unresolved: none of these known-mode checks performs a current spatial archive search. The failed baseline, upstream timeout/error receipts and successful post-fix known result are preserved together. Final real-only verification with the built frontend passed; all 288 approved observation hashes match and there is no diff in the five real golden directories. `git diff --check` passed with existing CRLF notices only. No scientific gate was relaxed and no missing data was invented. The actual API remains running on port 8000; the development frontend was untouched.
