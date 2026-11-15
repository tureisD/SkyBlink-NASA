# Live comparison retrieval and visual refinement

Authorized 2026-11-15 following reports that all quick-test targets returned a
single epoch with `PARTIAL_DOWNLOAD_NO_MATCHED_PAIR`.

The previous path selected visits independently in each epoch, then queued
downloads grouped by epoch. A bounded download stage could therefore spend its
budget on one epoch or on visits with incompatible wavelengths. Missing inputs
and failure to establish a pair do not prove the archive contains one epoch.

The approved repair ranks cross-epoch candidates using real archive footprint
metadata, downloads both sides in balanced rounds and checks for a usable pair
before spending the remaining budget on more candidates. Footprint geometry is
only a search heuristic. The existing measured spectral-WCS gate over retained
output pixels, usable background/pixel checks, common-band composition and
within-epoch time-span constraints remain authoritative. A passing pair can
contain fewer bands; the UI must show actual available bands. No missing image
or epoch may be invented and no failed request may substitute saved data.

Image processing/cache revision 12 searches a maximum of 24 proposed pairs.
Each round requests both sides of up to two pairs, with an 18-second download
stage bounded by the remaining overall budget. It checks for a passing pair
after each round and reserves processing time for the resulting images. The
search can stop with fewer available bands; it does not promise a full spectrum.
Ranked candidates, completed inputs and round outcomes are retained in lineage.

For large inventories, an eight-neighbor detector-corner shortlist avoids
materializing every possible exposure pair. The shortlist is reranked by mean
corner separation; its ordering is approximate, not a proof of the best possible
archive match. Invalid/missing polygons use bounded time-sampled candidates.
Deadline checks and reserved fallback slots keep these cases explicit. This
changes acquisition efficiency, not the measured acceptance thresholds.

SPHEREx's linear-variable filters sample different wavelengths at different
detector positions. Comparing arbitrary visits can confuse spectral differences
with temporal change. The [official product documentation](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/)
also distinguishes the visualization spectral WCS from calibrated CWAVE/CBAND
science products. This repair improves visual-pair retrieval, not calibrated
variability or discovery significance.

The public API remains 1.5.0; optional internal footprint metadata and updated
selection/cache version document processing behavior. Receipts must retain all
completed/failed rounds, and older input records must remain readable with
missing footprint metadata. Final verification must use fresh acquisition for
all five quick-test targets and preserve failures as well as successes.

The UI refinement provides a consistent type/spacing/chart system, readable
comparison limitations and explicit recovery actions. A smaller-field retry
changes the requested field visibly; it does not guarantee a pair. Recent
queries are browser-local settings, not an offline data cache. Scientific
warnings, signed fluxes, exclusions and the persistent canvas remain intact.

The measured fresh-target matrix, original failures and final-source replay
are in [live comparison verification](../verification/phase5-live-comparison-verification.md).
UI evidence and capture origins are in
[polish verification](../verification/phase5-polish-verification.md).
