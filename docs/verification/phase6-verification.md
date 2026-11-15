# Phase 6 local release verification

2026-11-15, API 1.6.0. Publishing, public-host checks and submission are explicitly deferred. Local checks below do not certify a current container or a public service. Scientific thresholds and the five revision-3 saved datasets remain unchanged.

**Later runtime follow-up:** [live-discovery diagnosis and method-13 bounded acquisition repair](phase6-live-discovery-diagnosis.md) records reproduced default-search timeouts, a failed-partner baseline, regression evidence and one strict-replayed fresh known comparison. Method 13 does not establish a repair of upstream metadata discovery. Earlier method-12 evidence below remains its historical checkpoint.

## Runtime and retrieval

The actual development API on port 8000 was restarted after the coordinated source freeze. The backend regression suite passed **316 tests in 79.87 s**. Five sequential explicit known-exposure spectrum requests succeeded on the current process, using fresh upstream FITS; live discovery still failed. These are different acquisition choices, never an automatic fallback.

| Target | Present samples | Finite | Recorded eligible | Result |
|---|---:|---:|---:|---|
| WISE 0855 | 4 | 4 | 4 | HTTP 200 |
| Barnard's Star | 4 | 2 | 0 | HTTP 200; two null fluxes |
| Epsilon Indi B | 4 | 2 | 0 | HTTP 200; two null fluxes |
| RW Aurigae | 7 | 7 | 0 | HTTP 200; one D6 download failed explicitly |
| R Draconis | 3 | 0 | 0 | HTTP 200; all fluxes unavailable |

Receipts and actual responses are retained under `backend/.cache/phase6/spectrum-final/`. A subsequent RW live-discovery request returned HTTP 503 after 90.125 s. Successful known acquisition does not repair live discovery, prove target detection or certify excluded measurements. Known exposures are a bounded older inventory; newer observations may exist.

Independent `scripts/verify_catalog_receipts.py` verification passed all five records and **22 actual retained input entries**, including fresh acquisition coverage, content hashes and current processing-source identity. `backend/.cache/phase6/spectrum-integrity-independent.json` retains the audit. Strict WISE spectrum replay passed input/source/environment verification and numerical comparison without override: analysis `sha256:2fda60f221e4d4d15ba4aad3311f880d1af40251fb9224224f2b6ccae7ed3b64`; report `backend/.cache/phase6/replay-wise/replay-report.json`. Arithmetic replay is not independent astrophysical validation.

## Production HTTP and packaging

The actual `scripts/serve.py` production entrypoint ran on loopback port 8177 with an isolated cache and both upstream discovery endpoints set to unreachable loopback port 9. `scripts/release_smoke.py --offline` passed:

- Built HTML, JavaScript and CSS served from the same origin and matched local build bytes.
- All five explicit saved sky views and spectra returned real-only provenance.
- **278 served assets** (frames, differences, references and telemetry) matched repository bytes exactly.
- Removed `/mock` and fallback namespaces, and an unknown API path, returned 404.

Evidence: `backend/.cache/phase6/production-http-pass.json`, repeated against the final shortcut build in `production-http-final-build.json`, now also asserting the exact OpenAPI version and explicit saved access. Two initial smoke-harness errors are retained separately: header dictionary casing and treating the reference attribution text as an asset URL. The corrected harness normalizes HTTP header names and excludes only the documented text field. No production behavior was changed to pass these checks.

Saved verification with telemetry requirements passed all five datasets. Revision-3 counts are 3/3/4/3/4 epochs, including the genuine missing bands in R Draconis. This verifies integrity and structural availability, not scientific promotion of legacy comparisons.

Docker, Podman, nerdctl and GitHub CLI were absent from PATH and the standard executable locations checked. No matching runtime service was found. `wsl --status` exited 50; `wsl --list --verbose` returned installer/help output, not a usable distribution. Evidence: `backend/.cache/phase6/wsl-status.json`. No engine was installed or reboot attempted. **The final container build, Linux runtime permissions, image resource use and named-volume restart persistence remain unverified locally.**

The Dockerfile now uses Node 24 and an unprivileged UID/GID 10001 runtime; `/data/cache` is owned by that identity in the image. Existing root-owned volumes need explicit ownership migration, not deletion. `serve.py` trusts forwarded headers only from loopback by default, with an explicit deployment override. The staged release workflow can execute the container gates on a Docker-capable runner; it was not pushed or run here. See [deployment instructions](../guides/deployment.md).

## Admission and retention

Two distinct live builds may run per process. Same-query sharing remains. Busy requests return typed retry guidance; storage admission refuses builds when the managed stores plus estimated reservations exceed 8 GiB or filesystem free space would fall below 1 GiB plus reservations. Each active/new build reserves an estimated 512 MiB. These are conservative admission checks, **not a hard filesystem quota** or distributed scheduler. No lineage or retained input is automatically removed. Browser cancellation may leave shared server work active.

At inspection, managed runtime stores used 4,859,551,764 bytes and the filesystem had 379,061,510,144 bytes free. Research folders were excluded. TTL expiration does not reclaim space; operators must monitor storage and deliberately preserve/export lineage. Isolated backend tests cover admission, reservation, symlink refusal and slot release; those generated protocol/storage inputs are not observations.

## Interface verification

The left sidebar contains the target title and Observe/Compare/Spectrum/Evidence tasks, with source and position controls. Search retains catalog and recent-query navigation. Sidebar collapse/focus keeps the canvas persistent. Spectrum recovery is an explicit independent `spectrumDiscovery=known` view choice: the image remains in its existing discovery mode. Shared URLs/history preserve that choice; reports do not join epoch labels across different discovery inventories.

Before the final keyboard enhancement, the production build passed ten workspace cases: Chromium at 1440/320 px, Firefox and WebKit at 1440/1024/390/320 px. They exercised panel focus restoration, outside-image notifications, persistent blink, A/B and differences, modal keyboard behavior, spectrum selection and reduced motion. Thirty axe scans reported zero violations. Receipts: `backend/.cache/phase6/viewer-matrix/` and `viewer-remaining/`.

Six independent recovery cases (three engines, desktop/320 px) replayed unchanged real live-error, sky and final spectrum responses with their real asset bytes. They verified no image reload or canvas replacement, seven finite excluded RW samples, three all-null R Draconis samples without a fabricated plot or transport error, and four eligible WISE samples. Six drawer axe scans reported zero violations. URL and history restore retained separate image/spectrum modes. The original case-sensitive label assertion failure is preserved in `spectrum-browser/`; the corrected case-insensitive assertion and all six passes are in `spectrum-browser-final/`. No application change was needed for that harness error.

Cancellation, late-response rejection, target-switch isolation and spectrum retry passed in all three engines using delayed unchanged real saved responses (`backend/.cache/phase6/browser-requests/`). Protocol tests additionally reject inappropriate known recovery for busy/storage/restart errors and preserve all native spectrum epochs when image/spectrum inventories differ.

The final keyboard build passed all three engines (`shortcuts-final/results.json`): Space play/pause; ignored held-key repeats; left/right steps; Shift+arrow pan; R reset; band keys; difference-mode playback guard; sidebar/native-control/editor/modal ownership; `?` help; an exact RA 359.9999999, Dec −90 search request with no catalog snapping; 8 FPS URL cap; and reduced-motion playback refusal. The arbitrary-coordinate test aborted transport intentionally and did not claim upstream coverage. For a shared missing R Draconis band, the app explicitly warns, removes the unavailable epoch from selection and displays a valid epoch with its actual date. An initial test incorrectly required a blank frame; that failure remains in `shortcuts/`, and the final assertion checks the actual documented warning/selection behavior.

The final build is `index-Bn097oJ0.js` / `index-D2F3SyWT.css`. Final production HTTP checks passed, and Chromium desktop/320 px independently repeated spectrum recovery plus real excluded/null/eligible states on those bytes (`spectrum-final-build/results.json`). The two additional drawer scans also reported zero axe violations: **38 scans total** across the initial workspace, recovery and final narrow rerun. Browser engines were Chromium 159.0.8154.6, Firefox 159.0 and WebKit 27.2.

Final captures: [desktop](../screenshots/phase6/workspace-1440.png), [390 px](../screenshots/phase6/workspace-390.png), [320 px](../screenshots/phase6/workspace-320.png), [shortcuts](../screenshots/phase6/shortcuts-1440.png), [excluded real spectrum](../screenshots/phase6/known-spectrum-320.png), and [all-null real spectrum](../screenshots/phase6/null-spectrum-320.png). [Origins](../screenshots/phase6/origins.json) records 60 source/build/script hashes and the real saved or unchanged retained observation inputs. Captures are documentation evidence, never runtime observation assets.

The root's retained-pixel investigation found 3,211 RW and 2,521 WISE interior nonfinite output pixels touching hard-flagged native bilinear support. Black display pixels can therefore denote masked/unavailable values; a smaller number of finite black pixels are below the display stretch. Exported nearest-neighbor flag values can be zero at an interpolation hole. The new readout explicitly states unavailable intensity and incomplete flag provenance rather than calling such a pixel clean. No interpolation fill, science mask or rendered observation bytes were changed for this explanation.

Final real-only verification passed with **288 original approved observation hashes unchanged**, and `git diff --check` passed (existing CRLF notices only). These are automated/internal checks, not participant research, screen-reader certification, a full flash-safety measurement or an all-device accessibility guarantee. No synthetic observations were added; historical science failures remain intact.

## Follow-up: comparison controls in the left sidebar

The A/B selectors, Side by side and Show A/B controls now sit beneath task navigation in the left sidebar. The central comparison box is removed. Mobile Compare keeps the sidebar open so its controls remain reachable; Observe closes it as before. This layout-only follow-up uses build `index-B6nUFx8T.js` / `index-D952MtbI.css`; the earlier production-build screenshots and broader checks above remain evidence for their recorded checkpoint.

The narrow `browser-compare-sidebar.mjs` check passed **6/6 cases**: Chromium, Firefox and WebKit at 1440 and 320 px. It used actual explicit saved Epsilon Indi B through the existing development origin `http://localhost:5173`, not the earlier production server. Checks covered left-panel containment with no central duplicate or horizontal overflow; A/B selection; keyboard Tab order and Enter activation; side-by-side and Show A/B; collapse/reopen focus; actual distinct-frame blinking; retained selections; and the same main canvas DOM node throughout Observe → Compare → Observe, layout changes and panel collapse. All sky requests remained `source=saved`; no archive acquisition was performed.

The first harness run used IPv4 `127.0.0.1` against a server listening only on IPv6 `::1`, so it failed before loading the app. That infrastructure failure remains under `backend/.cache/phase6/compare-sidebar/`; the correctly addressed passes are under `compare-sidebar-localhost/`. No server was restarted or stopped. Frontend typecheck/build, packaging guards, views and semantics tests also passed; no full backend/browser suite was unnecessarily repeated.

Follow-up captures: [desktop](../screenshots/phase6-compare/compare-1440.png), [320 px](../screenshots/phase6-compare/compare-320.png), and [exact source/build origins](../screenshots/phase6-compare/origins.json). These document the layout with real saved observations; they do not establish scientific validity.
