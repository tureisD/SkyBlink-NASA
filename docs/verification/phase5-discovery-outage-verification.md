# Discovery outage investigation and verification

2026-11-15. This investigation concerns the later all-collection SIA/TAP failures, not the earlier stale method-11 worker. Results below distinguish confirmed evidence from acceptance still pending. No saved observations are substituted for failed archive acquisition.

## Preserved baseline

The actual API8000 listener remained PID 7616, launched by the intended `scripts/dev_api.py --no-reload` process. Its current source whitelist exactly matched the preceding successful five-field run: `bf70342df924ecf5fff5af316fc943c885479620787553a04e7140ce921791c3`. Read-only process inspection confirmed expected repository/frontend working directories and no allowlisted backend configuration or proxy environment overrides in the API worker, its launcher or Vite5173.

The preserved stderr tail records 68 HTTP `502 Proxy Error` lines. At 13:56 local time, the RW Aurigae and Barnard requests failed for all four SIA collections, then failed through TAP despite bounded retries. This confirms failure along the upstream discovery transport path. It does not by itself distinguish an IRSA origin outage from an intervening gateway/proxy failure. It is not evidence of absent sky coverage, and restarting an unchanged worker is not established as a repair.

Bounded process/config/log receipts and their SHA-256 hashes are retained in `backend/.cache/phase5-discovery-outage/`, with summary `runtime-baseline-summary.json`. The original logs and previous successful/failed acquisition records remain unchanged. No additional archive query was issued during this initial read-only inspection.

After coordination, one direct Chromium 159.0.8154.6 navigation queried official SIA for the RW Aurigae coordinate, DR1 collection, zero-radius circle. At 13:06:20 UTC it returned **HTTP 502 in 0.717 seconds**, with a 341-byte HTML proxy error rather than a VOTable. The body reported that the proxy could not read a valid response from the upstream server; its SHA-256 is `6c5cbf315d1e65021bda341d39f2f9126b1e63d3099d07c315894bd11add085b`. The exact URL, headers and body are preserved under `browser-sia/`; `scripts/probe_discovery_browser.mjs` makes exactly one bounded navigation. This reproduces the failure outside Python and the application's API. It still does not identify which upstream server failed.

## Requirements for an alternative discovery transport

A usable fresh metadata response must retain the real artifact URI, detector, observation time bounds, release/collection identity and spatial coverage. Current SIA responses include `access_url`, `energy_bandpassname`, `t_min`, `t_max`, `obs_id` and `s_region`. Full-field spectral compatibility still requires the actual FITS content; polygon similarity alone cannot certify a matched comparison.

Current TAP parsing retains URI/detector/time/release but its query does not select the footprint polygon. A TAP-based alternative therefore needs measured consideration of method-12 footprint ranking, not an assumption that it behaves identically to SIA. File/object listing alone is not a coordinate-coverage catalog. Historical query responses cannot certify current complete discovery. Failed/overflowed collections must remain explicit; transport changes must retain source responses, request parameters, hashes and completeness semantics.

IRSA's current guide documents AWS as a mirror of the products and supplies `cloud_access` through the SIA result table. It also describes Astroquery and PyVO as clients of the same VO services. Consequently, changing the Python client or switching image storage alone is not an independently documented solution to failed coordinate discovery. The guide notes that SIA ingestion can lag directory/GUI/TAP availability by roughly a day; fresh transport does not imply zero publication lag. These distinctions come from the [official SPHEREx access guide](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access/), not an assumption that all access routes share the same availability.

The [official IBE search API documentation](https://irsa.ipac.caltech.edu/ibe/ibe_search_api.html) explicitly limits `/ibe/search` to WISE/NEOWISE, 2MASS and PTF. SPHEREx's presence under `/ibe/data` therefore does not establish a supported SPHEREx metadata-search endpoint. No guessed `/ibe/search/spherex/...` route was adopted or presented as an alternative.

## Final verification

An explicit recovery mode has been authorized for implementation under API 1.6: `discovery=known` with archive acquisition and a named catalog target. Default `discovery=live` remains unchanged; no automatic metadata or product fallback is approved. `data/catalog-exposure-index.json` contains only metadata from previously verified final analysis records: WISE 0855 4 exposures, Barnard 4, Epsilon Indi B 4, RW Aurigae 8 and R Draconis 3. Every full-MEF URL, detector, observation bounds, release and footprint is copied exactly from recorded discovery metadata and joined to a hash-verified retained input. The prior selected pairs are included. The index records source analysis identities, original record hashes/times and exact query coordinates; it does not contain FITS bytes or rendered products.

`scripts/build_catalog_exposure_index.py` validates original records and input hashes before extraction. Initial index SHA-256: `b2221a76bd2edb73ac3621f8487c3c09c8f0b89aa44a002b19b82e1465b5215b`. A known lookup deliberately cannot establish new/missing epochs or all-sky coverage. Its fresh downloads must pass the same current compatibility/background/usability checks, and sparse known spectra are not equivalent to complete archive spectra.

After the API 1.6 source freeze and one restart, all five explicit known-mode sky requests on actual API8000 returned HTTP 200 and matched visual pairs. Every response retains `discovery_mode=known` and `discovery_status=partial`: the list is deliberately bounded, not a claim of failed live collections or complete current coverage.

| Field | Elapsed seconds | Newly retained FITS inputs | Actual UTC dates shown |
|---|---:|---:|---|
| RW Aurigae | 49.782 | 8 | 2025-09-03 / 2026-09-09 |
| WISE 0855 | 44.297 | 4 | 2025-05-05 / 2026-05-11 |
| Barnard's Star | 34.796 | 2 | 2026-03-19 / 2026-05-04 |
| Epsilon Indi B | 41.468 | 3 | 2025-10-06 / 2026-10-01 |
| R Draconis | 33.110 | 2 | 2025-05-01 / 2026-04-17 |

The index has 23 entries, but these builds retained **19 fresh input entries** in total; bounded acquisition can stop after establishing a usable pair. Independent verification passed for all five source whitelists, known-index/source-record identities, fresh FITS receipts and **59 served image/difference/telemetry assets**. Arbitrary-coordinate known mode returned HTTP 422 in 0.078 seconds, retained separately and never counted as a successful observation. Raw results are in `backend/.cache/phase5/discovery-outage/recovery-final/`; independent results are in `backend/.cache/phase5-discovery-outage/known-integrity.json`.

Epoch IDs are inventory-dependent. For example, the same March 2026 Barnard observation had `2025_E2` in the broader prior live inventory but `2025_E1` in the bounded known inventory. The actual UTC date/MJD bounds and exposure identity must be compared; IDs alone are not equivalent across modes. Shared views preserve the mode, and the report exporter was checked against the actual new Barnard response for mode, dates and MJD.

Two subsequent attempts stalled during a host/tool interruption: the initial known-spectrum request returned no captured HTTP result after 627.375 seconds, and the arbitrary live query returned none after 2612.813 seconds. Their original matrix entries remain intact. They are not passes, and their elapsed times do not by themselves establish a normal API deadline failure. Only these incomplete checks were followed up; the five successful sky cases were not repeated. The failed live-discovery path remains explicit; saved mode is never an automatic recovery path.

The bounded follow-ups completed: RW Aurigae known spectrum returned HTTP 200 in **57.453 seconds**, with eight fresh retained inputs and eight finite channels, **zero eligible for photometry**. Exclusions were preserved; successful acquisition does not make those measurements usable. The independent source/index/input audit passed for this spectrum as well as the five sky products (27 input entries across these six builds). The arbitrary live request still returned **503 in 24.766 seconds**. The outage was not repaired or hidden; explicit catalog recovery was added alongside it. Follow-up receipts are retained in `recovery-final/post-stall-retries.json`.

The runtime package explicitly copies the index. The packaging gate requires its approved metadata hash and rejects changed/missing metadata or additional unapproved `data/` files. The local runtime-shaped copy check passed, as did 11 real-only regressions; this is not a newly verified Docker image. All 288 approved observation hashes remain frozen.

The integration backend suite produced 307 passes and one outdated API-version assertion. After updating that test expectation to API 1.6, the focused contract suite passed 19 tests, including the prior failure. Thus all 308 cases passed across the full and focused runs; a single pristine 308-pass run is not claimed. The frontend real-data, WCS, semantics and view suites passed, including new protocol-only known-mode URL, source-mismatch, history and wording boundaries.

Strict offline replay of the new known Barnard record (`sha256:6ac557e948a283957ce4a400bfabbab6b514c43fd59d4f1badd4820598bd096b`) passed with source/environment/input identity and exact numerical agreement, without drift overrides. Receipt: `backend/.cache/phase5-discovery-outage/replay-known-barnard/replay-report.json`. This validates reproducibility of the recorded arithmetic, not target detection or astrophysical variability.

## Browser acceptance and remaining boundaries

The actual user path on `localhost:5173` through API8000 was verified without interception. RW Aurigae live discovery returned 503. Only after clicking **Fetch known exposures online** did the known request begin; it returned 200 in **49.089 seconds**, two matched epochs and explicit `known`/`partial` provenance. Blink produced three distinct real renders through the same persistent canvas. The network trace records the initial development StrictMode request as aborted, the subsequent live503, then the known200. No saved fallback occurred. Current fresh receipts, served assets and source/index identity passed a separate integrity check under `backend/.cache/phase5-discovery-outage/user-known/`.

An isolated browser matrix used the unchanged real503, known sky and known spectrum receipts with their exact real asset bytes. All **six cases passed** across Chromium, Firefox and WebKit at1440/320 pixels. Checks include the loading source selector within the phone width, no automatic recovery, explicit known action/label, actual A/B dates, query-only history including discovery mode, and same-mode spectrum. All six axe scans reported zero violations; incomplete checks remain manual. The original harness initially asserted URL state before the existing debounced URL write; those six failures remain in `browser-known/`. Replacing that immediate assertion with a bounded `waitForURL` yielded the final six passes in `browser-known-final/`, with no application change. This timing correction is separate from the earlier genuine spectrum-state race.

Representative [actual desktop](../screenshots/known-recovery/desktop-actual.png) and [phone](../screenshots/known-recovery/phone-320.png) captures have [exact response/source/build origins](../screenshots/known-recovery/origins.json). Final frontend build: `index-CKPlCg3C.js`, `index-B5hed_lE.css`. API8000 and the user's Vite5173 remain running; no temporary server was needed for this verification.

This is bounded catalog recovery, not universal fresh discovery. Arbitrary fields still require working SIA/TAP. A known list may miss newer epochs; a matched field does not establish detection, motion, variability, calibrated source flux or scientific target validity. Human comprehension, assistive-technology usability and quantitative flash safety are not certified by these automated checks. Historical failed reports and all 288 saved observation assets remain unchanged.
