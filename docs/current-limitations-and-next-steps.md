# Current limitations and next steps

[Documentation home](README.md) · [Implementation plan](audit-and-remediation-plan-2026-11-14.md)

## Current repair: indexed online acquisition is integrated (November 16)

The new frontend and API **1.7.0** now support **Data source -> Online archive -
indexed coverage**. Open the local [WISE online comparison](http://127.0.0.1:5174/?target=wise_0855&source=archive&discovery=indexed).
The landing page also links to this explicit recovery choice. This searches a
reviewed spatial metadata index and downloads real FITS inputs afresh; it does
not load saved observation products. Image method 13 and scientific gates are unchanged.

Measured through the actual frontend proxy: **WISE 0855, Barnard's Star and
R Draconis returned two compatible epochs**. RW Aurigae returned one usable
epoch with incomplete partner downloads. Epsilon Indi B did not yield a usable
image: completed detector-2 inputs lack supported local background and other
inputs failed to complete. These are field-image results, not proof of target
detection or astrophysical variability. See the [runtime verification](verification/archive-recovery-execution-2026-11-15.md).

The index contains **5,223 exposure headers**, from three bounded directory scans
plus 21 fresh header reads at historically recorded addresses. It permits
coordinate searches within those footprints, but is neither all-sky nor a
complete current inventory. A miss explicitly means unknown coverage. Every
result carries the indexed mode, partial discovery status, index identity and
fresh-input lineage; source choices never change silently. The
[API decision](decisions/indexed-archive-contract-decision.md) records this scope.

**Still unresolved:** IRSA TAP/SIA live discovery and intermittent busy/incomplete
cutout transfers. The original **Online archive - fresh search** remains a
separate default choice and can still fail. Earlier attempts changed timeouts,
transports or pair downloads without providing a working spatial discovery
source; the first successful independent-index experiment was also outside the
app. This repair connects that separate metadata path to the real application.

**Next steps:** expand independently listed detector/period coverage around
unserved fields, preserve complete-enumeration receipts for each added scope,
and approve a new index hash only after footprint and fresh-download checks.
Seek an official bulk spatial manifest or restored TAP/SIA before claiming
all-sky/current discovery. Keep acquisition failures distinct from quality
rejections. No second-network test or current container/public-host acceptance
is claimed. The integrated work remains on the local integration branch; it
uses `integration/archive-and-frontend` for GitHub delivery and has not
been merged into `main`.

## Earlier investigation checkpoints (historical)

The following entries describe earlier states, including research-only results;
the integrated status above supersedes their next-step and runtime statements.

**Two-epoch recovery test (November 16 local):** the independent AWS index
now feeds the unchanged processing pipeline successfully: **two real WISE-field
epochs and a difference product in 30 seconds**, using fresh cutout downloads.
The targeted scan indexed 3,484 detector-3 exposures and discovered four
candidates. This is an isolated research result, not an integrated app mode or
proof of WISE target detection. Both local development servers were restarted;
TAP still times out. See [results and integration requirements](verification/archive-recovery-execution-2026-11-15.md).

**Independent search prototype (November 15 UTC / November 16 local):**
[the continuation results](verification/archive-recovery-execution-2026-11-15.md)
now include a working AWS-header coordinate index: 1,718 real exposures indexed
in 149 seconds, with seven accelerated searches matching exhaustive WCS results.
The positive control found eight exposures and a fresh 4.17 MB FITS cutout
was downloaded from one result. This one detector/period contains
none of the five catalog positions. Default archive search is **still unresolved**:
TAP/SIA fail, and the research index is not integrated into the app. The next
index milestone is measured multi-period/multi-detector coverage and a real
comparison through the unchanged scientific gates.

**New working metadata route (2026-11-15):** the documented IRSA Moving Object Search Tool (MOST) returned **66 SPHEREx observations** for Neptune during June 2025, including DR1 file paths, observation bounds and footprints. A returned DR1 file served a real FITS header range. This revises the broader suggestion that no current science-metadata route works. MOST searches solar-system trajectories; it has not restored fixed-coordinate discovery for our catalog targets. See the [resource recheck](research/challenge-data-sources-recheck-2026-11-15.md).

**Challenge-resource recheck (2026-11-15):** [provider review and measured downloads](research/challenge-data-sources-recheck-2026-11-15.md) found useful additional routes: direct SPHEREx spectral-cube tile access, an official static 3I/ATLAS observation list (259 legacy QR2 rows), and working independent unWISE W1/W2 cutouts. These enable separately labeled context or curated examples; none establishes restored arbitrary-coordinate SPHEREx temporal discovery. The challenge page itself could not be freshly retrieved, so the eight-link inventory remains grounded in the recorded November 13 check.

**Execution follow-up (2026-11-15):** [recovery execution and measured index feasibility](verification/archive-recovery-execution-2026-11-15.md) records the completed next steps. Native curl and the portable Python probe still reproduce discovery failures. The actual frontend proxy reaches API 1.6.0. No second machine is available, so independent-network verification remains open. An [IRSA incident draft](verification/irsa-incident-draft-2026-11-15.md) and [portable probe](research/archive-recovery/README.md) are prepared. AWS-only listing/header experiments recovered time and spatial metadata across both releases and all six detectors; a complete sample period contains 10,352 objects. This makes an independent index technically plausible, but no complete index or runtime search replacement has been built. **Default discovery remains unresolved.**

**Latest investigation — 2026-11-15, 22:04–22:06 UTC:** see the
[concrete archive recovery plan](plans/archive-recovery-plan-2026-11-15.md)
for the failure history, fresh probes, decision gates, owners and acceptance
criteria. Availability, schema, a non-SPHEREx catalog, ObsCore and the official
SIA example now return matching 502 proxy errors; one plane query times out.
Static documentation and a small AWS FITS range remain accessible. The local
API was also stopped; it has been started with API 1.6.0 / method 13. A fresh
default WISE request still returned 503 after 62.203 seconds. Search is **not
restored**. The next diagnostic is a controlled second-network comparison,
followed by service escalation or a demonstrated query/transport repair.
Earlier availability successes below describe their own recorded time windows.

**Renewed search attempt:** the official Explorer also reports TAP inaccessible;
its server-side search proxy returns a 502 error. Documented async GET, multipart
POST and the separate ObsCore table did not return science rows. Public cloud
listing works but exposes no independent coordinate index at the root/release
levels inspected. No working replacement for fresh discovery was established.
See [the renewed investigation](verification/phase6-archive-search-renewed.md).

## Historical diagnosis: default archive search — 2026-11-15 follow-up

**Default live search is currently failing in this environment; it is not a
completed reliability fix.** Direct SIA requests failed outside SkyBlink using
Windows curl, Python and Chromium, including the published SPHEREx example.
A direct spatial TAP query also timed out after 65.75 seconds with SIA bypassed.
A small TAP schema query did succeed, so this does not establish that every
IRSA service is down. The evidence points to the upstream discovery path;
the exact failing component and availability from other networks remain unknown.
The API health check only probes the availability endpoint and is not a
successful observation-search test.

**Immediate user action:** for a named catalog target, select **Data source →
Known exposures — fresh downloads**, or use **Fetch known exposures online**
on the failed-request screen. This explicitly bypasses discovery using the
bounded recorded exposure list, while still requesting real FITS inputs online.
It cannot find new exposures or support arbitrary-coordinate searches during
this failure. It is a workaround, not a repair of fresh archive search. Saved
catalog data is a separate historical option; no mode is substituted silently.

The baseline WISE control obtained fresh real inputs but returned only one
epoch: two partner downloads hit a short round deadline. A bounded second-attempt
repair is now implemented under [image method 13](decisions/phase6-pair-download-recovery-decision.md).
The restarted API returned a real two-epoch WISE comparison in 34.375 seconds
through explicit known mode. That run succeeded in its initial candidate round;
it does not measure the new retry's live benefit. Isolated regression checks
exercise the retry behavior. Do not infer a working blink from HTTP 200 alone
or present this acquisition repair as restored search.

Restoring and verifying default search is **P0 for any live-search demonstration**.
There is no defensible completion-time estimate for recovery of an external
service. Do not spend the remaining pre-video window repeatedly retrying targets
or assume that higher timeouts fix the problem. Demonstrate only a tested,
explicit acquisition mode and disclose its scope. Local release checks do not
certify upstream availability. See [the current diagnosis and receipts](verification/phase6-live-discovery-diagnosis.md).

## Three-hour pre-video plan — 2026-11-15

**Release status:** Phase 6 implementation and the recorded local release checks
are complete. This is not a fully verified deployment: the current container
build, Linux permissions and volume persistence have not run on a usable Docker
engine. Public hosting and submission remain deferred at the user's request.
The [Phase 6 report](verification/phase6-verification.md) supersedes the older interface and
retrieval checkpoints below for current local evidence.

**Completed UI change:** the Compare controls now sit in the left sidebar,
retaining A/B selection, layouts, keyboard access and the persistent image
canvas. Build and relevant frontend checks passed, as did six targeted browser
cases (Chromium, Firefox and WebKit at desktop and 320-pixel widths). This changes
presentation, not comparison eligibility.

**Recommended time budget:** spend at most 135 minutes on changes and checks,
then preserve 45 minutes for unexpected problems and preparation. Estimates
include review and verification; they are planning ranges, not promises about
upstream response times. The remaining rows are recommendations, not completed
work or new scientific acceptance evidence.

| Priority | Work before the video | Estimate / hard timebox | Completion condition |
|---|---|---|---|
| P0 — done | Move Compare into the left sidebar and check narrow screens | Planned 15–25 min / 25 min; completed this turn | A/B, layout selection, panel reopening and playback checked; image keeps its canvas. |
| P0 | Prepare two short evidence-backed demonstration stories | 30–45 min / 45 min | One real comparison and one limited measurement, each tied to an exact analysis, dates, acquisition mode and defensible conclusion. Review existing evidence; do not claim a new independent target validation. |
| P0 | Rehearse the exact recording path and an archive-failure recovery | 20–25 min / 25 min | Record the actual source choice, first attempt and recovery separately. Confirm blink, spectrum status and export/share behavior on the recording machine. Stop repeated requests at the timebox. |
| P1 | One-person comprehension check | 10–20 min / 20 min | A person unfamiliar with the app can explain what changed in the image, whether a plotted value is eligible, and what remains unknown. Fix only a demonstrated blocker. This is a quick check, not the planned user study. |
| P0 | Freeze the build and prepare recording materials | 15–20 min / 20 min | Save the tested source/build identity, actual analysis links/receipts, screenshots and a brief narration outline; verify the local startup command. Avoid new features after this point. |
| Buffer | Unexpected fixes and handoff to recording | 45 min reserved | Begin video work at the three-hour deadline even if optional work remains. |

For the stories, the latest WISE 0855 known-exposure spectrum returned four
recorded eligible samples; that supports demonstrating the extraction workflow,
not a complete calibrated spectrum, molecular detection or measured motion.
R Draconis returned three samples with unavailable flux; it can demonstrate
why an honest result sometimes contains no usable measurement. A field blink
shows a comparison of observations; target detection or variability needs its
own evidence. The other three catalog spectra had zero recorded eligible
samples in the final run, even where finite exploratory values were present.
See the exact [five-target results](verification/phase6-verification.md#runtime-and-retrieval).

Use the explicit known-exposure option if discovery fails, and name that choice
in the demonstration. It still downloads upstream FITS and can itself fail.
An explicitly selected saved example is available for demonstrating navigation,
but remains a legacy/unvalidated product. Do not present it as a fresh archive
success. A recording of a successful real run should retain its date, mode and
analysis identity. A share URL requests a view again; it is not an immutable
replay bundle.

### What should wait beyond these three hours

| Work | Priority after recording | Rough effort and constraint |
|---|---|---|
| Current container build, non-root runtime and volume restart checks | Release gate before deployment | 30–90 min with a working Docker runner, longer if failures need repairs; engine installation/reboots have no reliable short timebox. The workflow is prepared but has not run. |
| Five complete reviewed target evidence sheets | High | 4–8 focused hours for an initial evidence audit; independent scientific review and missing observations can take longer. The two short demo stories above do not replace this. |
| Broader reliability measurements over multiple time windows | High | 2–4 hours to organize and inspect a first matrix, then elapsed days of scheduled observations; a short successful run cannot establish an availability rate. |
| Current documentation consolidation | High | 3–6 focused hours for a concise current reference path; a complete scientific reference manual is larger. Existing guides and replay instructions already provide a starting point. |
| Full novice/expert and assistive-technology review | High | At least 1–2 working days plus participant scheduling and fixes. |
| Distinguish invalid pixels visually and preserve independent flag coverage | Medium | 0.5–2 working days including output, provenance and replay checks; keep the present explanation in the meantime. Do not fill holes with invented observations. |
| Calibrated wavelength integration, expanded controls and uncertainty validation | Research, required before broader scientific claims | Several days to weeks, with no guaranteed passing outcome. |
| Independent metadata index, full spectral assembly or measured motion | Later research/engineering | Multi-day to multi-week projects with new validation requirements; not pre-video polish. |

The immediate objective is a clear demonstration of a trustworthy exploratory
tool. The remaining discovery outages, sparse or excluded measurements, limited
scientific validation and unverified container should stay explicit in the
presentation. These estimates are project judgments based on the current
implementation, not evidence that the outstanding work has been performed.

**Phase 6 display finding (2026-11-15):** retained RW Aurigae and WISE 0855
examples show that the tested interior black/NaN holes touch hard-flagged native
pixels in the interpolation support. Conservative interpolation expands their
display footprint, and unsmoothed enlargement makes the edges blocky. Some
finite low intensities are also displayed as black. The rendered image alone
therefore cannot distinguish a missing pixel from a dark measurement. Exported
flag values can become zero where the science footprint is invalid; zero hover
flags at such holes must not be interpreted as clean data. The UI explains this
limitation; preserving independent flag coverage or adding a per-band missing
data layer is future work requiring new output/replay verification. No hole
filling or change to measurement eligibility is approved. See
[Phase 6 verification](verification/phase6-verification.md).

Reviewed 2026-11-15. The detailed backlog below retains the Phase 5 evidence and research scope; the pre-video plan above incorporates the subsequent Phase 6 local checkpoint. Publishing remains excluded. This is a proposed priority order, not a claim that the investigations below have been performed. API 1.6.0 adds explicit known-exposure recovery; image method 13 adds bounded missing-partner recovery while scientific gates remain unchanged.

**Current discovery limitation:** a later failure of both SIA and TAP was
reproduced with the correct runtime and outside the application. The explicit
known-exposure mode can bypass metadata discovery for the five recorded
catalog fields, while still downloading real FITS inputs from IRSA. It cannot
find new observations, support arbitrary positions during a discovery outage,
or survive an image-service outage. It uses a bounded historical metadata list,
so successful downloads do not mean complete discovery or a full spectrum.
See [outage verification](verification/phase5-discovery-outage-verification.md). A maintained
independent spatial metadata index would be a separate, substantial resilience
project requiring update/completeness checks and source lineage.

**Development-server follow-up:** recurrent catalog failures were traced to a
stale method-11 worker behind the user's UI. The worker was replaced and the
application now checks running-source consistency before fresh acquisition and
record creation. Sidebar controls and notifications were also revised to give
the image more space. Read [the follow-up verification](verification/phase5-catalog-reliability-and-viewer.md)
for its actual-server matrix and browser evidence; the earlier measurements
below remain historical evidence. This repair does not broaden scientific
validation or remove upstream availability limits.

SkyBlink now retrieves real observations, often constructs a wavelength-compatible blink comparison, explains unsupported results, and can reproduce recorded arithmetic. The main remaining work is to establish **what users can conclude from particular targets**, measure reliability more broadly, and test whether people understand the evidence. More elaborate photometry is a separate research task with an uncertain outcome.

## What has been fixed, and what those fixes establish

| Area | Current evidence | Boundary of that evidence |
|---|---|---|
| Live comparison retrieval | Pair-first acquisition replaced the large independently selected download batch. The final fixed run matched five of six fields on the first pass; Epsilon Indi B matched on one identical retry. All five named targets and the north Galactic pole therefore have a successful current-source comparison. | This is not six uninterrupted successes, an availability estimate, or proof that the named target is detected. |
| Wavelength compatibility | Geometry ranks downloads; measured WCS-WAVE values still determine acceptance. The dense image gate checks every retained output pixel. | The lookup is a visualization approximation. Matching it does not establish calibrated variability or identical spectral responses. |
| Honest failure states | Partial discovery, failed downloads, single epochs, unavailable measurements and explicit saved mode are represented separately. Retry does not silently load old data. | Honest output does not remove an upstream outage or produce a missing comparison. |
| Scientific method decision | The existing center-pixel method has restricted independent-control support. The proposed exact-aperture/SAPM refinement was not adopted after its primary failure. | Neither result establishes all-sky, crowded-source, saturated-source or all-detector performance. |
| Provenance and replay | The final Barnard analysis verifies nine retained inputs and reproduces all twelve image/difference/telemetry assets with matching source/environment. Earlier separate-reviewer fresh-environment image, finite-spectrum and null-spectrum checks also passed. | Current replay is tested on specified local environments and retained inputs. It does not validate the astrophysical model or every platform. |
| Interface | Current polish checks passed 38 browser cases; 36 axe scans reported no violations, with some checks incomplete. Signed spectra, exclusions, nulls, selected-pair exports and recovery were exercised. | Automated behavior checks are not human comprehension, comprehensive accessibility or photosensitivity certification. |

Evidence: [live comparison and replay](verification/phase5-live-comparison-verification.md), [independent science study](verification/phase4-science-online-verification.md), [Phase 4 replay scope](verification/phase4-verification.md), [interface verification](verification/phase5-verification.md), and [final polish checks](verification/phase5-polish-verification.md). Historical failures remain in these reports.

The subsequent [centered workspace revision](verification/phase5-centered-workspace-verification.md)
implements the requested left Fields / central image / right Inspector layout,
with collapsible panels and focus mode. Its browser evidence is recorded
separately. It changes navigation and presentation, not the scientific scope
or any of the remaining acceptance requirements below.

## Remaining engineering and product work

### 1. Review what each named example actually demonstrates

**Priority: first. Value: high. Feasibility: high for an honest evidence review; uncertain for obtaining a positive scientific result.**

A field can have two real, matched images while its named target is faint, blended, saturated, masked or absent from the usable aperture samples. The successful WISE 0855 or R Draconis field comparison therefore cannot by itself substantiate target visibility, a measured spectral feature, variability or motion. A null spectrum is not a zero flux or a calibrated upper limit. Saved spectra and their recorded eligibility must not be substituted for current archive measurements.

Create one reviewed evidence sheet for each of the five quick-test targets using a pinned current analysis. Record the exact source location at each exposure time, actual common wavelength samples and dates, target/aperture flags, support, eligible/null/excluded measurements, nearby sources, and the strongest defensible interpretation. Include a clearly inconclusive example. Have an independent reviewer inspect the native inputs and registration, rather than relying on the rendered image alone.

**Acceptance:** every target story links to its actual observations and explicitly separates “field comparison available” from “target measurement supported.” If a target-level claim lacks evidence, narrow the story. Do not search until a favorable flux appears or require all five examples to produce positive detections. A scientifically honest negative or inconclusive example is useful. [Result vocabulary](guides/result-meaning.md), [real evidence walkthrough](guides/phase4-evidence-walkthrough.md).

### 2. Measure and improve bounded live reliability

**Priority: first, alongside the target review. Value: high. Feasibility: medium; upstream availability remains outside the application.**

The final first-pass requests took approximately **33–71 seconds**. Epsilon Indi initially had three unavailable collections and only one epoch; its identical retry succeeded in 44 seconds. An earlier WISE request exceeded the nominal 120-second budget and returned 503 after 128 seconds. Synchronous processing checks deadlines at operation boundaries, so the budget is not hard wall-clock preemption. These are observed outcomes, not a service-level guarantee. [Measured requests](verification/phase5-live-comparison-verification.md).

The search is deliberately bounded: it considers a recent epoch subset and a limited set of proposed pairs, uses an approximate footprint-neighbor shortlist, and stops when a usable comparison is found. It can miss valid pairs outside that search. Missing collection metadata can hide an entire epoch. “No matched pair in this search” must remain distinct from “no compatible observations exist.” Valid arbitrary coordinates are supported geometrically; this does not guarantee coverage, full field containment, a usable source or a comparison at every coordinate.

Run a preregistered reliability matrix over repeated time windows: all five targets plus fixed sparse, crowded, wrap, pole and detector-edge positions. Retain every first attempt and retry separately. Measure discovery, download, processing and publication time, bytes, worker lifetime and memory, with cold application caches. Report the fractions of matched, single-epoch, complete-empty, partial and failed results; distinguish upstream outages from local failures. The existing six-field matrix is too small to infer universal success.

If profiling supports it, investigate smaller metadata-driven probe requests, more efficient processing, and an explicit longer-running job mode with progress and cancellation. These are proposals, not existing features. Browser cancellation currently prevents stale UI replacement; it does not promise to stop already-running shared server work. Any server cancellation must preserve work still needed by another subscriber. A longer search should be a visible choice with recorded bounds, not an unbounded hidden retry loop.

Preserve the user's **fresh archive default** and bypass of application product/input cache reads. A visible retry can target failed upstream work within the declared job; it must not silently replace the requested fresh result with a saved product. Reviewed snapshots and pinned replay remain explicitly selected sources.

**Acceptance:** set latency/resource and reliability targets before the repeat run; demonstrate them under declared concurrency and network conditions. Preserve complete-versus-partial status and strict science gates. Compare new ranking policies against a larger offline metadata search and real retained inputs. Do not use a weaker wavelength threshold, stale automatic fallback or an erased failure to improve the success rate.

### 3. Test human understanding and accessibility

**Priority: first. Value: high. Feasibility: medium because participants and specialist review are needed.**

The desktop/mobile browser matrix exercises actual products and behavior, but no novice/expert participant study, screen-reader evaluation, physical-device test, native 400% zoom certification or full flash analysis has been completed. Some automated contrast/SVG checks remain unresolved by automation. The eight-FPS ceiling and paused/reduced-motion defaults are protections, not a flash-safety certificate. [Recorded limits](verification/phase5-polish-verification.md#limits).

Carry out the planned five-novice/three-expert task study. Ask participants to find and explain an actual comparison, recognize the difference between finite and eligible flux, interpret a null result, recover from partial discovery, and share/export the chosen pair. Record comprehension errors and assistance, not only whether controls were clicked. Include assistive-technology users and a separate standards review; W3C recommends combining user evaluation with conformance assessment. [W3C user evaluation guidance](https://www.w3.org/WAI/test-evaluate/involving-users/).

Evaluate actual image sequences at supported display sizes and extreme user-adjustable contrast/color settings before claiming flash conformance. WCAG's flash criterion depends on frequency and flash thresholds, including affected area and luminance/color changes; an FPS number alone does not settle it. Avoid asking participants to assess potentially unsafe flashes before technical review. [W3C flash guidance](https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html).

**Acceptance:** define task/comprehension criteria in advance; resolve critical misunderstandings and keyboard/screen-reader barriers, then repeat affected tasks. Retain non-blinking comparison options. Document the actual assistive technologies, devices and remaining limitations without generalizing a small study to all users.

### 4. Consolidate documentation and maintain reproducible examples

**Priority: near term. Value: high. Feasibility: high for consolidation; medium for cross-machine replay.**

The observing guide, result meanings, evidence walkthrough, replay instructions and screenshots exist. The larger data dictionary, architecture/method explanations and current-versus-historical consolidation are not all complete. Older reports retain earlier method versions, test counts and blocked/pending statements. Dated navigation is being added, but a writing plan is not a finished reference manual. [Writing plan](plans/documentation-writing-plan.md), [observing guide](guides/observing-guide.md).

Finish one current reading path with the units, coordinate/time conventions, release/calibration mapping, masks, eligibility, uncertainty terms and display-versus-measurement transformations. Connect it to the reviewed target examples. Preserve historical reports with their original scope rather than rewriting failures as successes. Test documented commands and links.

Separately test pinned image, finite-spectrum and null-spectrum replay on another clean machine. Verify bytes before processing; report source/environment differences explicitly. A matching local environment can reasonably require exact asset hashes, while any proposed cross-platform numeric tolerances must be declared before results and distinguish array agreement from encoder-byte differences. An ordinary share URL requests data again and can return a different analysis; it is not a pinned replay bundle. [Replay instructions](guides/reproducibility.md).

**Acceptance:** a reviewer can trace a displayed sample to source bytes and reproduce each documented example without undocumented local files. Changed or missing upstream bytes fail explicitly. This work is offline reproducibility and documentation, not Phase 6 hosting or publishing.

### 5. Decide the future of the five saved datasets

**Priority: after the target review; optional while legacy status stays clear. Value: medium. Feasibility: medium.**

The five revision-3 saved datasets remain unchanged historical products with their original coordinates and processing. They are deliberately labeled legacy/unvalidated. A new interface, successful archive request or strict replay of a different analysis does not scientifically promote them. [Rollout boundary](verification/phase4-online-verification.md).

If refreshed saved examples are wanted, build a separate revision from corrected astrometry and pinned inputs, perform the same target-level review and applicable science checks, and compare outputs before an explicit promotion decision. Preserve the original revision and its rollback path. Never put corrected metadata around old image pixels or reconstruct missing provenance as if it had been recorded.

**Acceptance:** each replacement has coherent coordinates, observation bounds, source/calibration identity and replayable outputs; its permitted claims are reviewed. A supported null result can pass honest-product acceptance. It cannot pass a target-detection requirement.

## Remaining scientific validation

These tasks need new evidence and predefined acceptance rules. They should not be bundled into an interface polish change or treated as routine bug fixes.

### Restricted independent-control support

The completed study contains **32 source/detector repeat comparisons involving 27 distinct Gaia sources**, across four high-latitude fields and detectors **1 and 3**. Six of eight field/detector cells were evaluable. The other two were insufficient and do not count as passes. The existing center-pixel/constant-WCS integration passed all six evaluable secondary cells on the screened population.

The primary exact-aperture/SAPM method passed five cells and **failed one**: north-b60 detector 3 had robust scatter **2.14869**, above the fixed limit of 2. It was not adopted. Better geometric integration does not automatically yield better calibrated source photometry. Neither repeated use of the same 27 stars nor removing the failed cell would constitute a new independent validation. The catalog controls are candidate stable stars, not independently certified infrared standards. [Protocol and complete outcomes](verification/phase4-science-online-verification.md).

**Next investigation:** preregister independent controls spanning the untested detectors, brightness, detector position, background and crowding regimes. Keep development scenes separate from final holdouts. Require enough supported controls to evaluate each claimed regime; retain exclusions, transport failures and insufficient groups. Report sensitivity of the results to the small sample size. Expand the supported scope only for regimes that actually pass. Value is high for scientific claims; feasibility is medium to low because compatible, isolated repeat observations are limited.

### Science wavelengths and measurement uncertainties

Current runtime wavelength labels explicitly identify WCS-WAVE as an approximate visualization lookup. The control investigation separately checked release/detector/orientation-matched CWAVE/CBAND. Those local research checks do not turn every runtime channel into a science-calibrated wavelength. IRSA specifies CWAVE/CBAND for science analysis; cutout coordinates must map correctly to the parent detector. [Official data products](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/).

**Next investigation:** make a versioned science-calibration path that verifies the correct release, detector, orientation and original pixel mapping, then compares it to the existing lookup over independently chosen positions and edges. Fail explicitly when calibration identity is unavailable. Revalidate selected pairs and extraction wavelengths before changing scientific labels. This is a tractable calibration project, not permission to adopt the failed aperture/SAPM refinement at the same time.

Flux uncertainties currently combine input variance with an approximate shared-background term. Detector correlations, fitted-background covariance, calibration systematics, aperture loss, PSF differences and resampling correlations are not comprehensively calibrated. A residual divided by that error is not automatically a calibrated detection significance.

**Next investigation:** measure repeatability and error coverage on independent real controls, stratified by support and scene properties; compare alternative error models on development data and freeze them before holdout evaluation. Numerical noise experiments may test arithmetic only in isolated tests, never become observation products. Acceptance requires both bias and uncertainty-coverage checks, with the null/exclusion rules preserved. Do not inflate errors after seeing a failed holdout just to pass its gate.

### Blends, PSFs, saturation and backgrounds

The earlier crowded-field outlier remains unexplained uniquely. It had a neighbor only 13.80 arcseconds away and no clean annulus pixels; an isolated-source EPSF diagnostic predicted a much smaller aperture-response change than observed and fit poorly. That does not establish that a fractional aperture, PSF correction or one new background algorithm will fix the scene. [Historical diagnostic and limits](verification/phase4-science-online-verification.md#why-the-earlier-crowded-field-failure-is-not-an-aperture-only-diagnosis).

**Next investigation:** compare the same pinned observations with an independently executed, neighbor-aware reference extraction, validating the reference tool's release support, wavelength, position, PSF and background conventions first. IRSA's tool supports simultaneous fitting of specified companions and sky; its help includes older QR/PSF descriptions, so identical DR1 inputs and conventions must be verified rather than assumed. Jobs can take minutes to hours. Its output would be an independent comparison, not automatic ground truth. [Official spectrophotometry tool](https://irsa.ipac.caltech.edu/onlinehelp/spherex/spherex/sp.html).

If needed, prototype joint neighbor/sky modeling or a PSF-aware comparison on a separate research branch. Correct effective-PSF use depends on data version and parent-detector position. [Official EPSF tutorial](https://caltech-ipac.github.io/irsa-tutorials/spherex-psf/). Require independent crowded and isolated holdouts, residual/model diagnostics, and preserved saturation exclusions before adoption. This is high-effort research. Explicitly unusable output remains preferable when information is missing; fitting cannot recover an unobserved saturated core without additional assumptions and validation.

### Spectrum completeness, variability and motion

The plotted channels are sparse measurements at their actual wavelengths and dates. A larger channel count, or measurements from several detectors in one epoch, does not imply a complete, simultaneous 102-channel spectrum. The image composition permits up to 30 days across its selected bands. IRSA obtains spectra through multiple pointings; its separate 102-channel all-sky cube has a different grid and product meaning. Substituting that cube would require a distinct interpretation and would not establish time-resolved target flux. [Official product definitions](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/).

**Possible extension:** define a time-aware spectral assembly product only after calibrated extraction is validated. Preserve missing channels, actual bandwidths and times; test any binning/interpolation policy independently. Molecular guide markers must remain references until a separately validated feature analysis supports a claim.

No fitted SPHEREx proper motion, parallax solution, orbital trajectory or Planet X detection is currently established. Catalog propagation places the query/extraction, and trial overlays illustrate a hypothesis. Neither measures motion from the images. A future motion study would need repeat positional measurements, frame registration against independent references, time-dependent wavelength/PSF/blend controls, positional uncertainties, false-positive assessment and held-out recovery of known movers. It is a substantial research extension, not a required fix to the current exploratory viewer. [Interpretation contract](guides/result-meaning.md).

## Limits that cannot be removed by software alone

- **Spatial information:** native sampling is about 6.15 arcseconds; the 3.075-arcsecond display grid does not double resolving power. Sources blended in the observations may remain ambiguous even with better modeling.
- **Missing information:** no algorithm can supply an unobserved epoch, a missing spectral sample or an unsaturated measurement merely because the interface expects one. Nulls and omissions must remain possible.
- **Spectral/time sampling:** LVF position changes wavelength, and observations at different wavelengths need not be simultaneous. Exact dates and compatibility checks remain necessary even with better calibration.
- **Source and archive behavior:** true variability, unresolved companions, changing backgrounds, incomplete catalog information and upstream outages cannot be eliminated by a successful unit test.

These limits set the meaning of a result. They do not prevent a useful, trustworthy exploratory tool.

## Suggested stopping points

For a stronger **exploratory product**, complete the target evidence sheets, repeated reliability measurements, human/accessibility review and current documentation. Keep unsupported cases visible. These steps offer more immediate value than adding a new photometry method without a passing independent test.

For stronger **scientific measurement claims**, separately complete calibrated wavelength integration, broader independent controls, uncertainty validation and whichever scene-modeling tests the claimed targets require. Promote only the demonstrated regimes. Keep motion fitting, complete spectral assembly and general crowded-field photometry as explicit research extensions until their own acceptance evidence exists.

The recommendations above are project judgments based on the linked evidence. Official external references were checked on 2026-11-15; their methods describe possible routes, not work already performed in SkyBlink.
