# Use SkyBlink to inspect a field

Choose a target or enter ICRS right ascension and declination. Archive mode
requests current DR1/QR3 observations. Saved mode is an explicit choice of
historical real examples; it does not refresh the archive. An unavailable
archive request never switches sources automatically.

If a catalog search fails because observation discovery is unavailable, choose
**Fetch known exposures online**. This explicitly uses a previously verified
list of exposure addresses and downloads the FITS images again. It reruns the
same comparison checks. “Known exposures — fresh downloads” is distinct from
a fresh archive search and from saved examples: it cannot discover newer
observations or establish complete coverage. Its spectrum is limited to that
small exposure list. Return to the fresh-search source option to search the
current archive. An arbitrary coordinate search always uses fresh discovery.

Begin with the field name, dates and limitation beside the image. The view
starts paused. One observation can be inspected, but cannot establish change
over time. A bounded search that found no compatible pair does not prove that
the entire archive lacks a pair.

The compact desktop workspace places the target name and Observe, Compare,
Spectrum and Evidence navigation in the left sidebar, the image in the center,
and the Inspector on the right. The remaining field controls are source
selection and field position. Use the top Search control for catalog targets,
coordinate entry and recent query settings. The Inspector separates
Evidence from Display controls. Use the hamburger button in either sidebar's
header to close it; the corresponding menu button beside the viewer title
reopens it. Focus image hides both. These controls change the layout, not the
selected observations, band or camera. The source and comparison limitation
stay beside the image. A compact notice button opens the comparison explanation
and recovery actions in the Inspector, outside the sky image. Dismiss the
notification or press Escape to return to its opener; the small comparison
status remains available even when the detailed notice is closed.

On a phone, open the panels with Show fields / Show inspector when needed;
they use the full available width. Source selection remains available in
Fields and during a pending/failed request. Scroll to reach controls below the
image. Focus mode expands the observing area; it is not scientific image
enhancement or additional resolution.

## Observe and compare

Use Observe to inspect an image and Compare to choose observations. The Compare
dates box is in the left sidebar, beneath the task buttons; reopen Fields if
the sidebar is closed. Read the actual A/B dates before stepping or playing.
Manual stepping avoids automatic
blinking. Side-by-side inspection keeps both observations available at once.
Display settings apply to both images; they do not change the native science
arrays. Difference imagery, where available, needs its subtraction order and
comparison limitation to be read together.

Saved comparisons are historical and unvalidated. An archive visual match is
also not a calibrated variability measurement: different wavelength sampling,
artifacts, blending and the PSF can change appearance. The available-band
composite is not necessarily all six detectors, and the B5/B6 product is not a
temperature measurement. Advanced controls expose display and catalog overlays;
trial motion or distance parameters are assumptions, not measured properties.

## Read a spectrum

If an archive spectrum request fails, **Fetch known spectrum online** explicitly
downloads measurements from the known catalog exposure list without reloading
the image. The spectrum source can therefore differ from the image source;
both are labeled and retained in sharing and exports. Returning to the image's
source clears that override. Reports never match epoch IDs across different
discovery inventories. A fetched response with no eligible measurements is
different from a failed request.

Read the counts of recorded, finite and eligible samples separately. A finite
number can be excluded by the measurement policy; a null value is unavailable,
not zero. R Draconis is a useful saved example of observations whose aperture
fluxes are unavailable. Inspect reasons and flags in the table, including when
there is no usable chart.

Select a plotted sample by pointer or touch, or focus the plot and use arrow
keys and Home/End. The table's Inspect buttons provide the same sample details
without relying on hover or distinguishing chart colors.

Use the table's epoch and measurement filters to narrow a large result, and
check the shown/total count before drawing conclusions. Signed-flux sorting
keeps negative estimates meaningful. Copying a selected sample preserves its
recorded metadata; filtering the table does not change the observations or
measurement eligibility.

Points and approximate errors represent sparse samples, not a continuous
measured spectrum. Negative flux estimates can occur after background
subtraction and must remain visible. Optional wavelength references mark
reference positions, not detected molecules. Full-aperture/background support
does not establish that the source is isolated or that errors are calibrated.

## Inspect and share evidence

Evidence separates source, comparison, measurements and validation. Expand
technical details for the method, provenance and analysis record when present.
Missing historical lineage stays unknown. The Phase 4 study supports a defined
screened population; it does not certify every field opened in this viewer.

A shared view link is a recipe for a query and selection. Opening it may query
the archive again; a changed or unavailable analysis must be explained. The
record's input hashes and pinned replay procedure provide the separate route
to numerical reproducibility. See [reproducibility](reproducibility.md).

An exported evidence report should describe the selected observations and band.
Its native spectrum is a separate extraction, not a measurement of the painted
display pixels. Preserve the limitations and source references when sharing it.

## When a request fails

Retry an unavailable archive, edit the coordinates or deliberately select a
saved example. Cancel stops browser waiting; shared server work may continue
until its own deadline. No observations, incomplete discovery, unsupported
measurements and failed network requests are different outcomes. None should
be interpreted as evidence that an astronomical source is absent.

If a request returns one epoch, the image is available but temporal comparison
is not. The recovery panel explains the recorded reason and offers a fresh
archive retry. For an incompatible bounded sample, an explicit smaller-field
request may help; it changes the field and does not guarantee a pair. Read
[why a live view has one epoch](why-a-live-view-has-one-epoch.md).

Search also lists recent successful fields. This browser-local history stores
coordinates, field size and the selected source, not observation data. Opening
an archive entry requests the archive again. Use Clear history to remove these
settings from this browser.

## Keyboard controls and dark pixels

Click or focus the image first. Space plays/pauses; Left/Right steps through
observations and pauses playback. R resets zoom/pan, D toggles an available
difference, A/T selects combined/thermal bands, and 1?6 selects an available
detector. Shift plus arrows pans the focused image. / opens Search and ? opens
the keyboard reference. Escape closes dialogs or the focused notification.
Native controls and text fields keep their own keys; dialogs own their keys.
Holding a shortcut does not repeatedly toggle playback. Single-epoch,
difference-view and reduced-motion playback restrictions remain in force.

Black patches can be hard-masked pixels, missing coverage, or valid low display
intensity. Conservative resampling can enlarge missing-pixel patches, and
unsmoothed enlargement makes them look blocky. Missing intensity is not zero
flux. Exported flag details may be incomplete at masked pixels, so zero hover
flags do not establish clean data. Adjusting contrast can reveal low valid
intensities, but cannot restore measurements that were masked or never recorded.
